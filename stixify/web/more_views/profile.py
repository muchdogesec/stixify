from rest_framework import serializers
from ..models import Profile
from drf_spectacular.utils import extend_schema_serializer
from drf_spectacular.utils import extend_schema, extend_schema_view
from ..utils import Response, ErrorResp, Pagination, Ordering

from rest_framework import viewsets, generics, mixins
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, Filter, BaseCSVFilter
from ..autoschema import DEFAULT_400_ERROR, DEFAULT_404_ERROR

from drf_spectacular.utils import OpenApiResponse, OpenApiExample, extend_schema, extend_schema_view

class ProfileSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Profile
        fields = "__all__"

@extend_schema_view(
    list=extend_schema(
        summary="Search profiles",
        description="Profiles determine how txt2stix processes the text in each File. A profile consists of an extractors, aliases, and/or whitelists. You can search for existing profiles here.",
        responses={400: DEFAULT_400_ERROR, 200: ProfileSerializer},
    ),
    retrieve=extend_schema(
        summary="Get a profile",
        description="View the configuration of an existing profile. Note, existing profiles cannot be modified.",
        responses={400: DEFAULT_400_ERROR, 404: DEFAULT_404_ERROR, 200: ProfileSerializer}
    ),
    create=extend_schema(
        summary="Create a new profile",
        description="Add a new Profile that can be applied to new Files. A profile consists of an extractors, aliases, and/or whitelists. You can find available extractors, aliases, and whitelists via their respective endpoints. Required fields are `name`, `extractions` (at least one extraction ID), `relationship_mode` (either `ai` or `standard`, defines how relationship between extractions should be created), and `extract_text_from_image` (boolean, defines if image text should be considered for extraction).",
        responses={400: DEFAULT_400_ERROR, 200: ProfileSerializer}
    ),
    destroy=extend_schema(
        summary="Delete a profile",
        description="Delete an existing Profile. Note, you cannot delete a Profile if it is linked to an existing File. Please delete all Files using this Profile in order to delete it.",
        responses={404: DEFAULT_404_ERROR, 204: None}
    ),
)
class ProfileView(viewsets.ModelViewSet):
    openapi_tags = ["Profiles"]
    serializer_class = ProfileSerializer
    http_method_names = ["get", "post", "delete"]
    pagination_class = Pagination("profiles")

    ordering_fields = ["name", "created"]
    ordering = "created_descending"
    filter_backends = [DjangoFilterBackend, Ordering]

    class filterset_class(FilterSet):
        name = Filter(
            label="Searches Profiles by their name. Search is wildcard. For example, `ip` will return Profiles with names `ip-extractions`, `ips`, etc.",
            lookup_expr="search"
            )

    def get_queryset(self):
        return Profile.objects
