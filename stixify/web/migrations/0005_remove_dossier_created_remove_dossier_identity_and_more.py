# Generated by Django 5.1 on 2024-10-15 13:39

import stixify.web.models
from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0004_alter_file_defang_alter_profile_defang'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dossier',
            name='created',
        ),
        migrations.RemoveField(
            model_name='dossier',
            name='created_by_ref',
        ),
        migrations.RenameField(
            model_name='dossier',
            new_name='created_by_ref',
            old_name='identity'
        ),
        migrations.AlterField(
            model_name='dossier',
            name='created_by_ref',
            field=models.JSONField(validators=[stixify.web.models.validate_identity]),
        ),
        migrations.RemoveField(
            model_name='dossier',
            name='modified',
        ),
        migrations.AddField(
            model_name='dossier',
            name='tlp_level',
            field=models.CharField(choices=[('red', 'Red'), ('amber+strict', 'Amber Strict'), ('amber', 'Amber'), ('green', 'Green'), ('clear', 'Clear')], default='red', help_text='This will be assigned to all SDOs and SROs created. Stixify uses TLPv2.'),
        ),
        migrations.AlterField(
            model_name='dossier',
            name='description',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AlterField(
            model_name='dossier',
            name='name',
            field=models.CharField(max_length=128),
        ),
        migrations.AddField(
            model_name='dossier',
            name='created',
            field=models.DateTimeField(auto_now_add=True, default=datetime.datetime(2020, 1, 1, 0, 0)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='dossier',
            name='modified',
            field=models.DateTimeField(auto_now=True),
        ),
    ]