# Generated by Django 5.1.1 on 2024-11-25 12:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0004_file_ai_summary_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='ignore_image_refs',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='ignore_link_refs',
            field=models.BooleanField(default=True),
        ),
    ]
