# Generated by Django 5.1.7 on 2025-05-08 14:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stixify_core', '0004_alter_file_tlp_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='txt2stix_data',
            field=models.JSONField(default=None, null=True),
        ),
    ]
