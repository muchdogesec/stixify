import logging
import os
from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Upper
import uuid, typing
from stixify.classifier.models import Cluster, DocumentEmbedding
from stixify.classifier.tasks import compute_embedding_for_document, create_embedding_text
import txt2stix, txt2stix.extractions
from django.core.exceptions import ValidationError
from datetime import datetime, timezone
from django.core.files.uploadedfile import InMemoryUploadedFile
import stix2
from file2txt.parsers.core import BaseParser
from dogesec_commons.stixifier.models import Profile
from dogesec_commons.identity.models import Identity

from sklearn.metrics.pairwise import cosine_similarity
from pgvector.django import CosineDistance


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
    tlp_level = models.CharField(choices=TLP_Levels.choices, default=TLP_Levels.RED, help_text="This will be assigned to all SDOs and SROs created. If no value passed, `TLP:Clear` will be assigned.")
    confidence = models.IntegerField(default=None, null=True)


    labels = ArrayField(base_field=models.CharField(max_length=256), default=list, help_text="These will be added to the `labels` property of the STIX Report object generated")
    identity = models.JSONField(default=default_identity, validators=[validate_identity], help_text="""This is a full STIX Identity JSON. e.g. `{"type":"identity","spec_version":"2.1","id":"identity--b1ae1a15-6f4b-431e-b990-1b9678f35e15","name":"Dummy Identity"}`. If no value is passed, [the Stixify identity object will be used](https://raw.githubusercontent.com/muchdogesec/stix4doge/refs/heads/main/objects/identity/stixify.json).""")
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



def upload_to_func(instance: 'File|FileImage', filename):
    if isinstance(instance, FileImage):
        instance = instance.report
    filename = str(instance.id) + '_' + filename
    return os.path.join(str(instance.identity.id), str(instance.report_id), filename)

def validate_file(file: InMemoryUploadedFile, mode: str):
    _, ext = os.path.splitext(file.name)
    ext = ext[1:]
    if ext not in BaseParser.PARSERS[mode][2]:
        raise ValidationError(f"Unsupported file extension `{ext}`")
    return True

class File(CommonSTIXProps):
    id = models.UUIDField(unique=True, max_length=64, primary_key=True, default=uuid.uuid4)
    file = models.FileField(max_length=1024, upload_to=upload_to_func)
    identity = models.ForeignKey(Identity, on_delete=models.CASCADE, default=None)
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    mimetype = models.CharField(max_length=512)
    mode = models.CharField(max_length=256)
    markdown_file = models.FileField(max_length=1024, upload_to=upload_to_func, null=True)
    pdf_file = models.FileField(max_length=1024, upload_to=upload_to_func, null=True)
    summary = models.CharField(max_length=65536, null=True, default=None)    
    
    # describe incident
    ai_describes_incident = models.BooleanField(default=None, null=True)
    ai_incident_summary = models.CharField(default=None, max_length=65535, null=True)
    ai_incident_classification = ArrayField(base_field=models.CharField(default=None, max_length=256, null=True), null=True, blank=True)

    txt2stix_data = models.JSONField(default=None, null=True)
    sources = ArrayField(base_field=models.CharField(default=None, max_length=256), null=True, default=None)
    embedding = models.OneToOneField(DocumentEmbedding, on_delete=models.SET_NULL, null=True)
    
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
    
    @property
    def archived_pdf(self):
        if self.mode == 'pdf':
            return self.file
        return self.pdf_file
    
    @property
    def process_file(self):
        f = self.file
        if self.mode == 'mhtml-pdf':
            f = self.pdf_file
        return f.open('rb')
    
    @property
    def process_mode(self):
        if self.mode == 'mhtml-pdf':
            return 'pdf'
        return self.mode
        
    def similar_posts(file, visible_to=None):
        if not file.embedding:
            return []

        files_qs = (
            File.objects.exclude(pk=file.pk, embedding=None)
            .select_related("embedding")
        )
        # get top 5 most similar posts based on embedding similarity, excluding self
        similar_files = files_qs.annotate(
            distance=CosineDistance("embedding__embedding", file.embedding.embedding)
        ).order_by("distance")[:100]  # get top 100 similar files to filter by permissions and shared topics before returning top 5

        results = []
        for sfile in similar_files:
            owners = visible_to or [file.identity_id]
            if sfile.tlp_level not in [TLP_Levels.GREEN, TLP_Levels.CLEAR] and file.identity_id not in owners:
                # skipping, user cannot see this file
                continue
            if len(results) >= 5:
                break
            similarity_score = cosine_similarity(
                file.embedding.embedding.reshape(1, -1),
                sfile.embedding.embedding.reshape(1, -1),
            )[0][0]
            results.append(
                {
                    "id": sfile.id,
                    "title": sfile.name,  # or get from related file
                    "score": similarity_score,
                    "tlp_level": sfile.tlp_level,
                    "owner": sfile.identity_id,
                    "added": sfile.created,
                }
            )
        return results

    def create_embedding(file, force=False, include_non_incident=False):
        should_embed = file.ai_describes_incident or include_non_incident
        if force or (file.embedding is None and should_embed):
            logging.info(f"creating embedding for file {file.id}")
            file.embedding, _ = DocumentEmbedding.objects.get_or_create(
                id=file.pk,
                defaults=dict(
                    text=create_embedding_text(
                        file.name, file.summary, file.ai_incident_summary
                    )
                ),
            )
            compute_embedding_for_document(file.embedding)
            logging.info(f"created embedding for file {file.id}")
            file.save(update_fields=["embedding"])


@receiver(post_delete, sender=File)
def remove_reports_on_delete(sender, instance: File, **kwargs):
    from .views import ReportView
    ReportView.remove_report(instance.report_id)


class FileImage(models.Model):
    report = models.ForeignKey(File, related_name='images', on_delete=models.CASCADE)
    file = models.ImageField(upload_to=upload_to_func, max_length=1024)
    name = models.CharField(max_length=256)


class JobState(models.TextChoices):
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    COMPLETED = "completed"

class JobType(models.TextChoices):
    IMPORT_FILE = "import-file"
    SYNC_VULNERABILITIES = "sync-vulnerabilities"
    BUILD_CLUSTERS = "build-clusters"
    BUILD_EMBEDDINGS = "build-embeddings"


class Job(models.Model):
    file = models.OneToOneField(File, on_delete=models.SET_NULL, null=True)
    type = models.CharField(max_length=64, choices=JobType.choices, default=JobType.IMPORT_FILE)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    state = models.CharField(choices=JobState.choices, max_length=20, default=JobState.PENDING)
    extra = models.JSONField(default=None, null=True)
    error = models.CharField(max_length=65536, null=True)
    run_datetime = models.DateTimeField(auto_now_add=True)
    completion_time = models.DateTimeField(null=True, default=None)

    def save(self, *args, **kwargs) -> None:
        return super().save(*args, **kwargs)
    
    @property
    def profile(self):
        return self.file.profile


class ObjectValue(models.Model):
    """Store extracted values from STIX objects for efficient querying."""
    
    stix_id = models.CharField(max_length=256, db_index=True)
    type = models.CharField(max_length=256)
    knowledgebase = models.CharField(max_length=64, null=True, blank=True)
    values = models.JSONField()
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='object_values')
    created = models.DateTimeField(default=None, null=True)
    modified = models.DateTimeField(default=None, null=True)
    is_dupe = models.BooleanField(default=False)
    values_concat = models.GeneratedField(
        expression=models.Func(models.F("values"), function="jsonb_values_concat"),
        output_field=models.TextField(),
        db_persist=True,
        null=True,
        blank=True,
    )
    values_list = models.GeneratedField(
        expression=models.Func(models.F("values"), function="jsonb_values_list"),
        output_field=ArrayField(base_field=models.TextField()),
        db_persist=True,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = [('stix_id', 'file')]
        indexes = [
            models.Index(fields=['type', 'stix_id'], name='stixify_ov_type_stix_idx', condition=models.Q(is_dupe=False)),
            models.Index(fields=['created', 'knowledgebase'], name='stixify_ov_kbase_c_idx', condition=models.Q(is_dupe=False)),
            models.Index(fields=['modified', 'knowledgebase'], name='stixify_ov_kbase_m_idx', condition=models.Q(is_dupe=False)),
            models.Index(fields=['created', 'type'], name='stixify_ov_created_type_idx', condition=models.Q(is_dupe=False)),
            models.Index(fields=['modified', 'type'], name='stixify_ov_modified_type_idx', condition=models.Q(is_dupe=False)),
            models.Index(KeyTextTransform('kb_type', 'values'), 'type', name='stixify_ov_kb_type_idx', condition=models.Q(is_dupe=False)),
            models.Index('created', Upper(KeyTextTransform('kb_id', 'values')), 'type', name='stixify_ov_kb_id_cidx', condition=models.Q(is_dupe=False)),
            models.Index('modified', Upper(KeyTextTransform('kb_id', 'values')), 'type', name='stixify_ov_kb_id_midx', condition=models.Q(is_dupe=False)),
            models.Index('values_concat', 'type', name='stixify_ov_values_concat_idx', condition=models.Q(is_dupe=False)),
            models.Index('values_concat', 'knowledgebase', name='stixify_ov_values_c_kbidx', condition=models.Q(is_dupe=False)),
        ]

    def __str__(self) -> str:
        return f"ObjectValue(stix_id={self.stix_id}, type={self.type})"
