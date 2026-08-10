from django.db import migrations, models


def rename_reprocess_job_type(apps, schema_editor):
    Job = apps.get_model("stixify_core", "Job")
    Job.objects.filter(type="reprocess-posts").update(type="reprocess-files")


def restore_reprocess_job_type(apps, schema_editor):
    Job = apps.get_model("stixify_core", "Job")
    Job.objects.filter(type="reprocess-files").update(type="reprocess-posts")


class Migration(migrations.Migration):
    dependencies = [
        ("stixify_core", "0027_file_added_file_updated"),
    ]

    operations = [
        migrations.RunPython(rename_reprocess_job_type, restore_reprocess_job_type),
        migrations.AlterField(
            model_name="job",
            name="type",
            field=models.CharField(
                choices=[
                    ("import-file", "Import File"),
                    ("reprocess-files", "Reprocess Files"),
                    ("sync-knowledgebase", "Sync Knowledgebase"),
                    ("build-clusters", "Build Clusters"),
                    ("build-embeddings", "Build Embeddings"),
                ],
                default="import-file",
                max_length=64,
            ),
        ),
    ]
