from django.db import migrations, models


def populate_file_timestamps(apps, schema_editor):
    File = apps.get_model("stixify_core", "File")
    Job = apps.get_model("stixify_core", "Job")
    first_job_times = dict(
        Job.objects.filter(file_id__isnull=False)
        .order_by("file_id", "run_datetime", "id")
        .distinct("file_id")
        .values_list("file_id", "run_datetime")
    )
    files = list(File.objects.all())
    for file in files:
        timestamp = first_job_times.get(file.pk, file.modified)
        file.added = timestamp
        file.updated = timestamp
    File.objects.bulk_update(files, ["added", "updated"])


class Migration(migrations.Migration):
    dependencies = [
        ("stixify_core", "0026_file_pap_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="file",
            name="added",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="file",
            name="updated",
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(populate_file_timestamps, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="file",
            name="added",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="file",
            name="updated",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
