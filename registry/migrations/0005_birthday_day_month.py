from django.db import migrations, models


def copy_day_and_month(apps, schema_editor):
    Member = apps.get_model("registry", "Member")
    for m in Member.objects.exclude(date_of_birth=None):
        m.birth_day, m.birth_month = m.date_of_birth.day, m.date_of_birth.month
        m.save(update_fields=["birth_day", "birth_month"])


class Migration(migrations.Migration):
    """Birthdays are recorded as day and month only; the year of existing dates of birth is dropped."""

    dependencies = [
        ("registry", "0004_branch"),
    ]

    operations = [
        migrations.AddField(model_name="member", name="birth_day", field=models.PositiveSmallIntegerField(
            blank=True, null=True, choices=[(d, d) for d in range(1, 32)], verbose_name="Birthday (day)")),
        migrations.AddField(model_name="member", name="birth_month", field=models.PositiveSmallIntegerField(
            blank=True, null=True, verbose_name="Birthday (month)", choices=[
                (1, "January"), (2, "February"), (3, "March"), (4, "April"), (5, "May"), (6, "June"), (7, "July"),
                (8, "August"), (9, "September"), (10, "October"), (11, "November"), (12, "December")])),
        migrations.RunPython(copy_day_and_month, migrations.RunPython.noop),
        migrations.RemoveField(model_name="member", name="date_of_birth"),
    ]
