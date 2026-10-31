from django.db import migrations, models
import django.db.models.deletion


def assign_existing_to_kisaasi(apps, schema_editor):
    Branch = apps.get_model("registry", "Branch")
    kisaasi, _ = Branch.objects.get_or_create(name="Kisaasi Branch")
    for model in ("Member", "Visitor", "Service"):
        apps.get_model("registry", model).objects.filter(branch__isnull=True).update(branch=kisaasi)


class Migration(migrations.Migration):

    dependencies = [
        ("registry", "0003_rename_household_member_cell"),
    ]

    operations = [
        migrations.CreateModel(
            name="Branch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="As shown in the header, e.g. Kisaasi Branch", max_length=100, unique=True)),
            ],
            options={"verbose_name_plural": "branches", "ordering": ["name"]},
        ),
        # Added nullable, filled with Kisaasi, then made required
        migrations.AddField(model_name="member", name="branch", field=models.ForeignKey(
            null=True, on_delete=django.db.models.deletion.PROTECT, related_name="members", to="registry.branch")),
        migrations.AddField(model_name="visitor", name="branch", field=models.ForeignKey(
            null=True, on_delete=django.db.models.deletion.PROTECT, related_name="visitors", to="registry.branch")),
        migrations.AddField(model_name="service", name="branch", field=models.ForeignKey(
            null=True, on_delete=django.db.models.deletion.PROTECT, related_name="services", to="registry.branch")),
        migrations.RunPython(assign_existing_to_kisaasi, migrations.RunPython.noop),
        migrations.AlterField(model_name="member", name="branch", field=models.ForeignKey(
            on_delete=django.db.models.deletion.PROTECT, related_name="members", to="registry.branch")),
        migrations.AlterField(model_name="visitor", name="branch", field=models.ForeignKey(
            on_delete=django.db.models.deletion.PROTECT, related_name="visitors", to="registry.branch")),
        migrations.AlterField(model_name="service", name="branch", field=models.ForeignKey(
            on_delete=django.db.models.deletion.PROTECT, related_name="services", to="registry.branch")),
        migrations.RemoveConstraint(model_name="service", name="unique_service_per_day"),
        migrations.AddConstraint(model_name="service", constraint=models.UniqueConstraint(
            fields=("branch", "date", "service_type"), name="unique_service_per_day")),
    ]
