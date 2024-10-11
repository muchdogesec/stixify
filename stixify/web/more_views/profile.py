from rest_framework import serializers
from ..models import Profile
from drf_spectacular.utils import extend_schema_serializer
from drf_spectacular.utils import extend_schema, extend_schema_view
from ..utils import Response, ErrorResp, Pagination, Ordering

from rest_framework import viewsets, generics, mixins
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, Filter, BaseCSVFilter
from ..autoschema import DEFAULT_400_ERROR, DEFAULT_404_ERROR

from drf_spectacular.utils import OpenApiResponse, OpenApiExample, extend_schema, extend_schema_view

import textwrap

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
                description=textwrap.dedent(
            """
            Add a new Profile that can be applied to new Files. A profile consists of extractors, aliases, and/or whitelists. You can find available extractors, aliases, and whitelists via their respective endpoints.\n\n
            The following key/values are accepted in the body of the request:\n\n
            * `name` (required - must be unique)
            * `extractions` (required - at least one extraction ID): can be obtained from the GET Extractors endpoint. This is a [txt2stix](https://github.com/muchdogesec/txt2stix/) setting.
            * `whitelists` (optional): can be obtained from the GET Whitelists endpoint. This is a [txt2stix](https://github.com/muchdogesec/txt2stix/) setting.
            * `aliases` (optional): can be obtained from the GET Whitelists endpoint. This is a [txt2stix](https://github.com/muchdogesec/txt2stix/) setting.
            * `relationship_mode` (required): either `ai` or `standard`. Required AI provider to be configured if using `ai` mode. This is a [txt2stix](https://github.com/muchdogesec/txt2stix/) setting.
            * `extract_text_from_image` (required - boolean): wether to convert the images found in a blog to text. Requires a Google Vision key to be set. This is a [file2txt](https://github.com/muchdogesec/file2txt) setting.
            * `defang` (required - boolean): wether to defang the observables in the blog. e.g. turns `1.1.1[.]1` to `1.1.1.1` for extraction. This is a [file2txt](https://github.com/muchdogesec/file2txt) setting.\n\n
            You cannot modify a profile once it is created. If you need to make changes, you should create another profile with the changes made.
            """
        ),
        responses={400: DEFAULT_400_ERROR, 200: ProfileSerializer}
    ),
    destroy=extend_schema(
        summary="Delete a profile",
        description=textwrap.dedent(
            """
            Delete an existing profile. Note, we would advise against deleting a Profile because any Files it has been used with will still refer to this ID. If it is deleted, you will not be able to see the profile settings used. Instead, it is usually better to just recreate a Profile with a new name.
            """
        ),
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
