# Generated by Django 5.1.1 on 2024-11-19 06:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0003_alter_file_file_alter_file_markdown_file_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='ai_summary_provider',
            field=models.CharField(default=None, max_length=256, null=True),
        ),
    ]
