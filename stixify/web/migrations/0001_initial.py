# Generated by Django 5.1 on 2024-11-12 12:47

import django.contrib.postgres.fields
import django.db.models.deletion
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
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=128)),
                ('tlp_level', models.CharField(choices=[('red', 'Red'), ('amber+strict', 'Amber Strict'), ('amber', 'Amber'), ('green', 'Green'), ('clear', 'Clear')], default='red', help_text='This will be assigned to all SDOs and SROs created. Stixify uses TLPv2.')),
                ('description', models.CharField(blank=True, max_length=512)),
                ('created_by_ref', models.JSONField(default=stixify.web.models.default_identity, validators=[stixify.web.models.validate_identity])),
                ('labels', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256), default=list, help_text='These will be added to the `labels` property of the STIX Report object generated', size=None)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(max_length=250, unique=True)),
                ('extractions', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256), size=None)),
                ('whitelists', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256), default=list, size=None)),
                ('aliases', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256), default=list, size=None)),
                ('relationship_mode', models.CharField(choices=[('ai', 'AI Relationship'), ('standard', 'Standard Relationship')], default='standard', max_length=20)),
                ('extract_text_from_image', models.BooleanField(default=False)),
                ('defang', models.BooleanField(help_text='If the text should be defanged before processing')),
                ('ai_settings_relationships', models.CharField(max_length=256, null=True)),
                ('ai_settings_extractions', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256), default=list, size=None)),
            ],
        ),
        migrations.CreateModel(
            name='File',
            fields=[
                ('name', models.CharField(help_text='This will be used as the `name` value of the STIX Report object generated', max_length=256)),
                ('tlp_level', models.CharField(choices=[('red', 'Red'), ('amber+strict', 'Amber Strict'), ('amber', 'Amber'), ('green', 'Green'), ('clear', 'Clear')], default='red', help_text='This will be assigned to all SDOs and SROs created. Stixify uses TLPv2.')),
                ('confidence', models.IntegerField(default=0, help_text='A value between `0`-`100`. `0` means confidence unknown. `1` is the lowest confidence score, `100` is the highest confidence score.')),
                ('labels', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=256), default=list, help_text='These will be added to the `labels` property of the STIX Report object generated', size=None)),
                ('identity', models.JSONField(default=stixify.web.models.default_identity, help_text='This is a full STIX Identity JSON. e.g. `{"type":"identity","spec_version":"2.1","id":"identity--b1ae1a15-6f4b-431e-b990-1b9678f35e15","name":"Dummy Identity"}`. If no value is passed, [the Stixify identity object will be used](https://raw.githubusercontent.com/muchdogesec/stix4doge/refs/heads/main/objects/identity/stixify.json).', validators=[stixify.web.models.validate_identity])),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, unique=True)),
                ('file', models.FileField(help_text='Full path to the file to be converted. Must match a supported file type: `application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/vnd.ms-powerpoint`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`, `text/html`, `text/csv`, `image/jpg`, `image/jpeg`, `image/png`, `image/webp`. The filetype must be supported by the `mode` used or you will receive an error.', upload_to=stixify.web.models.upload_to_func)),
                ('mimetype', models.CharField(max_length=64)),
                ('mode', models.CharField(help_text='How the File should be processed. Generally the `mode` should match the filetype of `file` selected. Except for HTML documents where you can use `html` mode (processes entirety of HTML page) and `html_article` mode (where only the article on the page will be processed).', max_length=256)),
                ('markdown_file', models.FileField(null=True, upload_to=stixify.web.models.upload_to_func)),
                ('dossiers', models.ManyToManyField(help_text='The Dossier ID(s) you want to add the generated Report for this File to.', related_name='files', to='web.dossier')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='web.profile')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='FileImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.ImageField(upload_to=stixify.web.models.upload_to_func)),
                ('name', models.CharField(max_length=256)),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='web.file')),
            ],
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
