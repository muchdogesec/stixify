import logging
from rest_framework import serializers, validators

from dogesec_commons.stixifier.serializers import ProfileSerializer
from dogesec_commons.stixifier.models import Profile
from .models import File, Dossier, FileImage, Job
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
import file2txt.parsers.core as f2t_core
from dogesec_commons.stixifier.summarizer import parse_summarizer_model

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

class FileSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    report_id = serializers.UUIDField(source='id', help_text="Only pass a UUIDv4. It will be use to generate the STIX Report ID, e.g. `report--<UUID>`. If not passed, this file will be randomly generated.", validators=[
        validators.UniqueValidator(queryset=File.objects.all()),
    ], required=False)
    mimetype = serializers.CharField(read_only=True)
    profile_id =  RelatedObjectField(serializer=serializers.UUIDField(help_text="How the file should be processed"), use_raw_value=True, queryset=Profile.objects)
    mode = serializers.ChoiceField(choices=list(f2t_core.BaseParser.PARSERS.keys()), help_text="How the File should be processed. Generally the mode should match the filetype of file selected. Except for HTML documents where you can use html mode (processes entirety of HTML page) and html_article mode (where only the article on the page will be processed)")
    download_url = serializers.FileField(source='file', read_only=True)
    file = serializers.FileField(write_only=True)
    ai_summary_provider = serializers.CharField(allow_blank=True, allow_null=True, validators=[parse_summarizer_model], default=None, write_only=True, help_text="AI Summary provider int the format provider:model e.g `openai:gpt-3.5-turbo`")


    class Meta:
        model = File
        exclude = ['profile', "dossiers", "markdown_file", "summary"]
        read_only_fields = ["dossiers"]

    def create(self, validated_data):
        validated_data = validated_data.copy()
        validated_data.pop('ai_summary_provider', None)
        return super().create(validated_data)


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


class DossierReportsRelatedField(RelatedObjectField):
    lookup_key = 'report_id'
    def __init__(self, /, **kwargs):
        super().__init__(serializers.CharField(), **kwargs)
    def get_queryset(self):
        return File.objects.all()
    def to_representation(self, value):
        return value.id

class DossierSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    report_ids = DossierReportsRelatedField(source='files', required=False, many=True)
    class Meta:
        model = Dossier
        fields = "__all__"


class JobSerializer(serializers.ModelSerializer):
    profile_id = serializers.UUIDField(read_only=True, source='file.profile_id')
    file = RelatedObjectField(read_only=True,  serializer=FileSerializer())
    class Meta:
        model = Job
        exclude = []

