import os
from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db import models
from django.contrib.postgres.fields import ArrayField
import uuid, typing
import txt2stix, txt2stix.extractions
from django.core.exceptions import ValidationError
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

TLP_LEVEL_STIX_ID_MAPPING = {
    TLP_Levels.RED: "marking-definition--e828b379-4e03-4974-9ac4-e53a884c97c1",
    TLP_Levels.CLEAR: "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
    TLP_Levels.GREEN: "marking-definition--bab4a63c-aed9-4cf5-a766-dfca5abac2bb",
    TLP_Levels.AMBER: "marking-definition--55d920b0-5e8b-4f79-9ee9-91f868d9b421",
    TLP_Levels.AMBER_STRICT: "marking-definition--939a9414-2ddd-4d32-a0cd-375ea402b003",
}

def create_report_id():
    return ""

def default_identity():
    return settings.STIX_IDENTITY

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



def upload_to_func(instance: 'File|FileImage', filename):
    if isinstance(instance, FileImage):
        instance = instance.report
    return os.path.join(str(instance.identity['id']), str(instance.report_id), filename)

def validate_file(file: InMemoryUploadedFile, mode: str):
    _, ext = os.path.splitext(file.name)
    ext = ext[1:]
    if ext not in BaseParser.PARSERS[mode][2]:
        raise ValidationError(f"Unsupported file extension `{ext}`")
    return True

class File(CommonSTIXProps):
    id = models.UUIDField(unique=True, max_length=64, primary_key=True, default=uuid.uuid4)
    file = models.FileField(max_length=1024, upload_to=upload_to_func)
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    mimetype = models.CharField(max_length=512)
    mode = models.CharField(max_length=256)
    markdown_file = models.FileField(max_length=256, upload_to=upload_to_func, null=True)
    summary = models.CharField(max_length=65536, null=True, default=None)    
    
    # describe incident
    ai_describes_incident = models.BooleanField(default=None, null=True)
    ai_incident_summary = models.CharField(default=None, max_length=65535, null=True)
    ai_incident_classification = models.CharField(default=None, max_length=256, null=True)
    
    @property
    def report_id(self):
        return 'report--'+str(self.id)
    
    @report_id.setter
    def report_id(self, value):
        self.id = value

    def clean(self) -> None:
        validate_file(self.file, self.mode)
        return super().clean()
    
    def __str__(self) -> str:
        return f"File(id={self.id})"
    
    # @classmethod
    # def visible_files(cls):
    #     return cls.objects.filter(job__state=JobState.COMPLETED)

@receiver(post_delete, sender=File)
def remove_reports_on_delete(sender, instance: File, **kwargs):
    from .views import ReportView
    ReportView.remove_report(instance.report_id)


class FileImage(models.Model):
    report = models.ForeignKey(File, related_name='images', on_delete=models.CASCADE)
    file = models.ImageField(upload_to=upload_to_func, max_length=256)
    name = models.CharField(max_length=256)


class JobState(models.TextChoices):
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    COMPLETED = "completed"

class Job(models.Model):
    file = models.OneToOneField(File, on_delete=models.CASCADE)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    state = models.CharField(choices=JobState.choices, max_length=20, default=JobState.PENDING)
    error = models.CharField(max_length=65536, null=True)
    run_datetime = models.DateTimeField(auto_now_add=True)
    completion_time = models.DateTimeField(null=True, default=None)

    def save(self, *args, **kwargs) -> None:
        if not self.completion_time and self.state in [JobState.COMPLETED, JobState.FAILED]:
            self.completion_time = datetime.now(timezone.utc)
        return super().save(*args, **kwargs)
    
    @property
    def profile(self):
        return self.file.profile
