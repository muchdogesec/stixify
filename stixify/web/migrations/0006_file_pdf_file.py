# Generated by Django 5.1.5 on 2025-06-23 15:33

import stixify.web.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stixify_core', '0005_file_txt2stix_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='pdf_file',
            field=models.FileField(max_length=256, null=True, upload_to=stixify.web.models.upload_to_func),
        ),
    ]
