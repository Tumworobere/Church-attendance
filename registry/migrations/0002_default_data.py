from django.db import migrations

SERVICE_TYPES = ["Sunday Service", "Midweek Service", "Prayer Meeting", "Youth Service", "Special Event"]
MINISTRIES = ["Choir", "Ushering", "Youth", "Children's Ministry", "Women's Fellowship", "Men's Fellowship",
              "Media", "Intercessors", "Hospitality"]


def add_defaults(apps, schema_editor):
    ServiceType = apps.get_model("registry", "ServiceType")
    Ministry = apps.get_model("registry", "Ministry")
    for i, name in enumerate(SERVICE_TYPES):
        ServiceType.objects.get_or_create(name=name, defaults={"order": i})
    for name in MINISTRIES:
        Ministry.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("registry", "0001_initial")]
    operations = [migrations.RunPython(add_defaults, migrations.RunPython.noop)]
