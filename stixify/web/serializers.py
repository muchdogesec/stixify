import logging
from rest_framework import serializers

from stixify.web.more_views.profile import ProfileSerializer
from .models import File, Dossier, Job
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
import stix2
from drf_spectacular.utils import extend_schema_field
import file2txt.parsers.core as f2t_core


class FileSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    report_id = serializers.CharField(read_only=True)
    mimetype = serializers.CharField(read_only=True)
    profile_id =  serializers.UUIDField()
    mode = serializers.ChoiceField(choices=list(f2t_core.BaseParser.PARSERS.keys()))
    class Meta:
        model = File
        exclude = ['profile']


class RelatedObjectField(serializers.RelatedField):
    lookup_key = 'pk'
    default_error_messages = {
        'required': _('This field is required.'),
        'does_not_exist': _('Invalid {lookup_key} "{lookup_value}" - object does not exist.'),
        'incorrect_type': _('Incorrect type. Expected valid {lookup_key} value, received "{lookup_value}", type: {data_type}.'),
    }
    def __init__(self, /, serializer, **kwargs):
        self.internal_serializer: serializers.Serializer = serializer
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        try:
            instance = self.get_queryset().get(**{self.lookup_key: data})
            return instance
        except ObjectDoesNotExist as e:
            self.fail('does_not_exist', lookup_value=data, lookup_key=self.lookup_key)
        except BaseException as e:
            logging.exception(e)
            self.fail('incorrect_type', data_type=type(data), lookup_value=data, lookup_key=self.lookup_key)
        
    def to_representation(self, value):
        return self.internal_serializer.to_representation(value)

class DossierReportsRelatedField(RelatedObjectField):
    lookup_key = 'report_id'
    def __init__(self, /, **kwargs):
        super().__init__(serializers.CharField(), **kwargs)
    def get_queryset(self):
        return File.objects.all()
    def to_representation(self, value):
        return value.report_id

class DossierSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    report_ids = DossierReportsRelatedField(source='files', required=False, many=True)
    class Meta:
        model = Dossier
        fields = "__all__"

@extend_schema_field(field=FileSerializer)
class FileRelatedField(RelatedObjectField):
    def __init__(self, **kwargs):
        super().__init__(FileSerializer(), **kwargs)

class JobSerializer(serializers.ModelSerializer):
    profile = RelatedObjectField(read_only=True, source='file.profile', serializer=ProfileSerializer())
    file = RelatedObjectField(read_only=True,  serializer=FileSerializer())
    # file_id =  serializers.PrimaryKeyRelatedField(source='file', read_only=True)
    class Meta:
        model = Job
        exclude = []

