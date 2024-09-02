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

if typing.TYPE_CHECKING:
    from .. import settings
# Create your models here.

class RelationshipMode(models.TextChoices):
    AI = "ai", "AI Relationship"
    STANDARD = "standard", "Standard Relationship"

def validate_extractor(types, name):
    extractors = txt2stix.extractions.parse_extraction_config(
            txt2stix.txt2stix.INCLUDES_PATH
        ).values()
    for extractor in extractors:
        if name == extractor.slug and extractor.type in types:
            return True
    raise ValidationError(f"{name} does not exist", 400)


class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=250, unique=True)
    extractions = ArrayField(base_field=models.CharField(max_length=256, validators=[partial(validate_extractor, ["ai", "pattern", "lookup"])]), help_text="extraction id(s)")
    whitelists  = ArrayField(base_field=models.CharField(max_length=256, validators=[partial(validate_extractor, ["whitelist"])]), help_text="whitelist id(s)", default=list)
    aliases     = ArrayField(base_field=models.CharField(max_length=256, validators=[partial(validate_extractor, ["alias"])]), help_text="alias id(s)", default=list)
    relationship_mode = models.CharField(choices=RelationshipMode.choices, max_length=20, default=RelationshipMode.STANDARD)
    extract_text_from_image = models.BooleanField(default=False)


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

def validate_identity(value):
    try:
        identity = stix2.Identity(**value)
        value["id"] = identity.id
    except BaseException as e:
        raise ValidationError(f"{e}")
    return True

class CommonSTIXProps(models.Model):
    name = models.CharField(max_length=256)
    tlp_level = models.CharField(choices=TLP_Levels.choices, default=TLP_Levels.RED)
    confidence = models.IntegerField(default=0)
    labels = ArrayField(base_field=models.CharField(max_length=256), default=list)
    identity = models.JSONField(validators=[validate_identity])
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



class Dossier(CommonSTIXProps):
    id = models.UUIDField(primary_key=True)
    desciption = models.CharField(max_length=65536)
    context = models.CharField(choices=DossierContextType.choices, max_length=64)
    created_by_ref = models.CharField(max_length=64)

    def save(self, *args, **kwargs):
        self.created_by_ref = self.identity['id']
        if not self.id:
            created = self.created or self._meta.get_field('created').pre_save(self, True)
            created = created.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            self.id = uuid.uuid5(settings.STIX_NAMESPACE, f"{created}+{self.created_by_ref}")
        return super().save(*args, **kwargs)

def upload_to_func(instance: 'File', filename):
    return os.path.join(str(instance.id), 'files', filename)

def validate_file(file: InMemoryUploadedFile, mode: str):
    _, ext = os.path.splitext(file.name)
    ext = ext[1:]
    if ext not in BaseParser.PARSERS[mode][2]:
        raise ValidationError(f"Unsupported file extension `{ext}`")
    return True

class File(CommonSTIXProps):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    report_id = models.CharField(unique=True, max_length=64, null=True)
    file = models.FileField(upload_to=upload_to_func)
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    dossier = models.ForeignKey(Dossier, on_delete=models.SET_NULL, null=True, related_name="files")
    mimetype = models.CharField(max_length=64)
    mode = models.CharField(max_length=256)
    defang = models.BooleanField(default=True)

    def clean(self) -> None:
        validate_file(self.file, self.mode)
        return super().clean()

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
