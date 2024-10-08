# Generated by Django 5.1 on 2024-09-02 15:50

import django.contrib.postgres.fields
import django.db.models.deletion
import functools
import stixify.web.models
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Dossier',
            fields=[
                ('name', models.CharField(max_length=256)),
                ('tlp_level', models.CharField(choices=[('red', 'Red'), ('amber+strict', 'Amber Strict'), ('amber', 'Amber'), ('green', 'Green'), ('clear', 'Clear')], default='red')),
                ('confidence', models.IntegerField(default=0)),
                ('labels', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256), default=list, size=None)),
                ('identity', models.JSONField(validators=[stixify.web.models.validate_identity])),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('desciption', models.CharField(max_length=65536)),
                ('context', models.CharField(choices=[('suspicious-activity', 'Suspicious Activity'), ('malware-analysis', 'Malware Analysis'), ('unspecified', 'Unspecified')], max_length=64)),
                ('created_by_ref', models.CharField(max_length=64)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(max_length=250, unique=True)),
                ('extractions', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256, validators=[functools.partial(stixify.web.models.validate_extractor, *(['ai', 'pattern', 'lookup'],), **{})]), help_text='extraction id(s)', size=None)),
                ('whitelists', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256, validators=[functools.partial(stixify.web.models.validate_extractor, *(['whitelist'],), **{})]), default=list, help_text='whitelist id(s)', size=None)),
                ('aliases', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256, validators=[functools.partial(stixify.web.models.validate_extractor, *(['alias'],), **{})]), default=list, help_text='alias id(s)', size=None)),
                ('relationship_mode', models.CharField(choices=[('ai', 'AI Relationship'), ('standard', 'Standard Relationship')], default='standard', max_length=20)),
                ('extract_text_from_image', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='File',
            fields=[
                ('name', models.CharField(max_length=256)),
                ('tlp_level', models.CharField(choices=[('red', 'Red'), ('amber+strict', 'Amber Strict'), ('amber', 'Amber'), ('green', 'Green'), ('clear', 'Clear')], default='red')),
                ('confidence', models.IntegerField(default=0)),
                ('labels', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256), default=list, size=None)),
                ('identity', models.JSONField(validators=[stixify.web.models.validate_identity])),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('report_id', models.CharField(max_length=64, null=True, unique=True)),
                ('file', models.FileField(upload_to=stixify.web.models.upload_to_func)),
                ('mimetype', models.CharField(max_length=64)),
                ('mode', models.CharField(max_length=256)),
                ('defang', models.BooleanField(default=True)),
                ('dossier', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='files', to='web.dossier')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='web.profile')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('state', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed')], default='pending', max_length=20)),
                ('error', models.CharField(max_length=65536, null=True)),
                ('run_datetime', models.DateTimeField(auto_now_add=True)),
                ('completion_time', models.DateTimeField(default=None, null=True)),
                ('file', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='web.file')),
            ],
        ),
    ]
