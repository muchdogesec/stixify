import logging
from rest_framework import serializers, validators

from dogesec_commons.stixifier.serializers import ProfileSerializer
from dogesec_commons.stixifier.models import Profile
from .models import File, FileImage, Job
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
import file2txt.parsers.core as f2t_core
from dogesec_commons.stixifier.summarizer import parse_summarizer_model
from rest_framework.exceptions import ValidationError

class RelatedObjectField(serializers.RelatedField):
    lookup_key = 'pk'
    default_error_messages = {
        'required': _('This field is required.'),
        'does_not_exist': _('Invalid {lookup_key} "{lookup_value}" - object does not exist.'),
        'incorrect_type': _('Incorrect type. Expected valid {lookup_key} value, received "{lookup_value}", type: {data_type}.'),
    }
    def __init__(self, /, serializer, use_raw_value=False, **kwargs):
        self.internal_serializer: serializers.Serializer = serializer
        self.use_raw_value = use_raw_value
        super().__init__(**kwargs)
        serializer.parent = self.root

    def to_internal_value(self, data):
        try:
            instance = self.get_queryset().get(**{self.lookup_key: data})
            if self.use_raw_value:
                return data
            return instance
        except ObjectDoesNotExist as e:
            self.fail('does_not_exist', lookup_value=data, lookup_key=self.lookup_key)
        except BaseException as e:
            logging.exception(e)
            self.fail('incorrect_type', data_type=type(data), lookup_value=data, lookup_key=self.lookup_key)
        
    def to_representation(self, value):
        return self.internal_serializer.to_representation(value)

class CharacterSeparatedField(serializers.ListField):
    def __init__(self, *args, **kwargs):
        self.separator = kwargs.pop("separator", ",")
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        retval = []
        for s in data:
            retval.extend(s.split(self.separator))
        return super().to_internal_value(retval)


class ReportIDField(serializers.CharField):
    def to_internal_value(self, data: str):
        if not data.startswith('report--'):
            raise ValidationError("invalid STIX Report ID, must be in format `report--{UUID}`")
        data = data.replace("report--", "")
        return serializers.UUIDField().to_internal_value(data)
    
    def to_representation(self, value):
        return "report--"+serializers.UUIDField().to_representation(value)
    
class FileSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    report_id = ReportIDField(source='id', help_text="If you want to define the UUID of the STIX Report object you can use this property. Pass the full report ID with UUIDv4, e.g. `report--26dd4dcb-0ebc-4a71-8d37-ffd88faed163`. This will be used in the STIX Report ID. If not passed, this UUID will be randomly generated. This UUID will also be assigned as the File ID. The `report_id` passed must not already exist in the database.", validators=[
        validators.UniqueValidator(queryset=File.objects.all()),
    ], required=False)
    mimetype = serializers.CharField(read_only=True)
    profile_id =  RelatedObjectField(serializer=serializers.UUIDField(help_text="The ID of the use you want to use to process the file. This is a UUIDv4, e.g. `52d95ee7-14a7-4b0d-962f-1227f1d5b208`"), use_raw_value=True, queryset=Profile.objects)
    mode = serializers.ChoiceField(choices=list(f2t_core.BaseParser.PARSERS.keys()), help_text="Generally the mode should match the filetype of file selected. Except for HTML documents where you can use html mode (processes entirety of HTML page) and html_article mode (where only the article on the page will be processed) to control the markdown output created. This is a file2txt setting.")
    download_url = serializers.FileField(source='file', use_url=True, read_only=True, allow_null=True)
    file = serializers.FileField(write_only=True, help_text="This is the file to be processed. The mimetype of the file uploaded must match that expected by the `mode` selected.")
    ai_describes_incident = serializers.BooleanField(required=False, read_only=True, allow_null=True)
    ai_incident_summary = serializers.CharField(required=False, read_only=True, allow_null=True)
    ai_incident_classification = serializers.ListField(required=False, read_only=True, allow_null=True)
    summary = serializers.CharField(read_only=True, required=False, allow_null=True)
    ai_summary_provider = serializers.CharField(source='profile.ai_summary_provider', read_only=True, required=False, allow_null=True)

    class Meta:
        model = File
        exclude = ['profile', "markdown_file"]
        read_only_fields = []

class ImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    class Meta:
        model = FileImage
        fields = ["name", "url"]

    @extend_schema_field(serializers.CharField())
    def get_url(self, instance):
        request = self.context.get('request')
        if instance.file and hasattr(instance.file, 'url'):
            photo_url = instance.file.url
            return request.build_absolute_uri(photo_url)
        return None


class JobSerializer(serializers.ModelSerializer):
    file = RelatedObjectField(read_only=True,  serializer=FileSerializer())
    class Meta:
        model = Job
        exclude = []

