from rest_framework import serializers
from stixify.web.models import ObjectValue

class ObjectValueSerializer(serializers.Serializer):
    """Serializer for ObjectValue model with aggregated file_ids."""
    
    id = serializers.CharField(source='stix_id')
    type = serializers.CharField()
    knowledgebase = serializers.CharField(read_only=True, required=False)
    values = serializers.JSONField(read_only=True)
    created = serializers.DateTimeField(required=False)
    modified = serializers.DateTimeField(required=False)

    def to_representation(self, instance):
        """remove null fields from the output"""
        instance.created = self.remove_bad_date(instance.created)
        instance.modified = self.remove_bad_date(instance.modified)
        representation = super().to_representation(instance)
        representation = {k: v for k, v in representation.items() if v is not None}
        return representation

    @staticmethod
    def remove_bad_date(dt):
        """remove dates that are before the epoch, which can cause issues with some databases"""
        from stixify.web.models import DEFAULT_DT
        if dt == DEFAULT_DT:
            return None
        return dt