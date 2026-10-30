from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registry", "0002_default_data"),
    ]

    operations = [
        migrations.RenameField(model_name="member", old_name="household", new_name="cell"),
        migrations.AlterField(
            model_name="member",
            name="cell",
            field=models.CharField(blank=True, help_text="The cell group this member belongs to", max_length=100),
        ),
    ]
