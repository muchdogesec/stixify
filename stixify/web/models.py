import os
import sys
from typing import Iterable
from django.conf import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField
import uuid, typing
from django.utils.text import slugify
from urllib.parse import urlparse
from functools import partial
import txt2stix.common
import txt2stix, txt2stix.extractions
from django.core.exceptions import ValidationError
from django.db.models import F, CharField, Value
from django.db.models.functions import Concat
from datetime import datetime, timezone
from django.core.files.uploadedfile import InMemoryUploadedFile
import stix2
from file2txt.parsers.core import BaseParser
from dogesec_commons.stixifier.models import Profile


if typing.TYPE_CHECKING:
    from .. import settings
# Create your models here.

def validate_extractor(types, name):
    pass


class TLP_Levels(models.TextChoices):
    RED = "red"
    AMBER_STRICT = "amber+strict"
    AMBER = "amber"
    GREEN = "green"
    CLEAR = "clear"

class DossierContextType(models.TextChoices):
    SUSPICIOUS_ACTIVITY = "suspicious-activity"
    MALWARE_ANALYSIS =  "malware-analysis"
    UNSPECIFIED = "unspecified"

def create_report_id():
    return ""

def default_identity():
    return settings.STIX_IDENTITY

def validate_identity(value):
    try:
        identity = stix2.Identity(**value)
        value["id"] = identity.id
    except BaseException as e:
        raise ValidationError(f"Invalid Identity: {e}")
    return True

class CommonSTIXProps(models.Model):
    name = models.CharField(max_length=256, help_text="This will be used as the `name` value of the STIX Report object generated")
    tlp_level = models.CharField(choices=TLP_Levels.choices, default=TLP_Levels.RED, help_text="This will be assigned to all SDOs and SROs created. Stixify uses TLPv2.")
    confidence = models.IntegerField(default=0, help_text="A value between `0`-`100`. `0` means confidence unknown. `1` is the lowest confidence score, `100` is the highest confidence score.")
    labels = ArrayField(base_field=models.CharField(max_length=256), default=list, help_text="These will be added to the `labels` property of the STIX Report object generated")
    identity = models.JSONField(default=default_identity, validators=[validate_identity], help_text="""This is a full STIX Identity JSON. e.g. `{"type":"identity","spec_version":"2.1","id":"identity--b1ae1a15-6f4b-431e-b990-1b9678f35e15","name":"Dummy Identity"}`. If no value is passed, [the Stixify identity object will be used](https://raw.githubusercontent.com/muchdogesec/stix4doge/refs/heads/main/objects/identity/stixify.json).""")
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



class Dossier(models.Model):
    id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=128)
    tlp_level = models.CharField(choices=TLP_Levels.choices, default=TLP_Levels.RED, help_text="This will be assigned to all SDOs and SROs created. Stixify uses TLPv2.")
    description = models.CharField(max_length=512, blank=True)
    created_by_ref = models.JSONField(default=default_identity, validators=[validate_identity])
    labels = ArrayField(base_field=models.CharField(max_length=256), default=list, help_text="These will be added to the `labels` property of the STIX Report object generated")
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)


    def save(self, *args, **kwargs):
        if not self.id:
            created = self.created or self._meta.get_field('created').pre_save(self, True)
            created = created.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            self.id = uuid.uuid5(settings.STIX_NAMESPACE, f"{created}+{self.created_by_ref['id']}")
        return super().save(*args, **kwargs)

def upload_to_func(instance: 'File|FileImage', filename):
    if isinstance(instance, FileImage):
        id = instance.report.id
    else:
        id = instance.id
    return os.path.join(str(id), 'files', filename)

def validate_file(file: InMemoryUploadedFile, mode: str):
    _, ext = os.path.splitext(file.name)
    ext = ext[1:]
    if ext not in BaseParser.PARSERS[mode][2]:
        raise ValidationError(f"Unsupported file extension `{ext}`")
    return True

class File(CommonSTIXProps):
    id = models.UUIDField(unique=True, max_length=64, primary_key=True, default=uuid.uuid4)
    file = models.FileField(upload_to=upload_to_func, help_text="Full path to the file to be converted. Must match a supported file type: `application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/vnd.ms-powerpoint`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`, `text/html`, `text/csv`, `image/jpg`, `image/jpeg`, `image/png`, `image/webp`. The filetype must be supported by the `mode` used or you will receive an error.")
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    dossiers = models.ManyToManyField(Dossier, related_name="files", help_text="The Dossier ID(s) you want to add the generated Report for this File to.")
    mimetype = models.CharField(max_length=64)
    mode = models.CharField(max_length=256, help_text="How the File should be processed. Generally the `mode` should match the filetype of `file` selected. Except for HTML documents where you can use `html` mode (processes entirety of HTML page) and `html_article` mode (where only the article on the page will be processed).")
    markdown_file = models.FileField(upload_to=upload_to_func, null=True)

    @property
    def report_id(self):
        return 'report--'+str(self.id)
    
    @report_id.setter
    def report_id(self, value):
        self.id = value

    def clean(self) -> None:
        validate_file(self.file, self.mode)
        return super().clean()
    
    


class FileImage(models.Model):
    report = models.ForeignKey(File, related_name='images', on_delete=models.CASCADE)
    file = models.ImageField(upload_to=upload_to_func)
    name = models.CharField(max_length=256)


class JobState(models.TextChoices):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"

class Job(models.Model):
    file = models.OneToOneField(File, on_delete=models.CASCADE)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    state = models.CharField(choices=JobState.choices, max_length=20, default=JobState.PENDING)
    error = models.CharField(max_length=65536, null=True)
    run_datetime = models.DateTimeField(auto_now_add=True)
    completion_time = models.DateTimeField(null=True, default=None)

    def save(self, *args, **kwargs) -> None:
        if not self.completion_time and self.state == JobState.COMPLETED:
            self.completion_time = datetime.now(timezone.utc)
        return super().save(*args, **kwargs)
    
    @property
    def profile(self):
        return self.file.profile
