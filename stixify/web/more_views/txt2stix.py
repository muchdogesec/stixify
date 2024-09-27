from rest_framework import serializers, viewsets, mixins
import txt2stix.extractions
import txt2stix.txt2stix
from urllib.parse import urljoin
from django.conf import settings
from ..utils import Response, ErrorResp, Pagination


from ..utils import ErrorSerializer
from drf_spectacular.utils import OpenApiResponse, OpenApiExample, extend_schema, extend_schema_view

from ..autoschema import DEFAULT_400_ERROR, DEFAULT_404_ERROR


class Txt2stixExtractorSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    type = serializers.CharField()
    description = serializers.CharField()
    notes = serializers.CharField()
    file = serializers.CharField()
    created = serializers.CharField()
    modified = serializers.CharField()
    created_by = serializers.CharField()
    version = serializers.CharField()
    stix_mapping = serializers.CharField()

    @classmethod
    def all_extractors(cls, types):
        retval = {}
        extractors = txt2stix.extractions.parse_extraction_config(
            txt2stix.txt2stix.INCLUDES_PATH
        ).values()
        for extractor in extractors:
            if extractor.type in types:
                retval[extractor.slug] = cls.cleanup_extractor(extractor)
                if extractor.file:
                    retval[extractor.slug]["file"] = urljoin(settings.TXT2STIX_INCLUDE_URL, str(extractor.file.relative_to(txt2stix.txt2stix.INCLUDES_PATH)))
        return retval
    
    @classmethod
    def cleanup_extractor(cls, dct: dict):
        KEYS = ["name", "type", "description", "notes", "file", "created", "modified", "created_by", "version", "stix_mapping"]
        retval = {"id": dct["slug"]}
        for key in KEYS:
            if key in dct:
                retval[key] = dct[key]
        return retval


class txt2stixView(mixins.RetrieveModelMixin,
                           mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = Txt2stixExtractorSerializer
    lookup_url_kwarg = "id"
    
    def get_queryset(self):
        return None

    @classmethod
    def all_extractors(cls, types):
        return Txt2stixExtractorSerializer.all_extractors(types)

    def get_all(self):
        raise NotImplementedError("not implemented")
    

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(list(self.get_all().values()))
        return self.get_paginated_response(page)

    def retrieve(self, request, *args, **kwargs):
        items = self.get_all()
        id_ = self.kwargs.get(self.lookup_url_kwarg)
        print(id_, self.lookup_url_kwarg, self.kwargs)
        item = items.get(id_)
        if not item:
            return ErrorResp(404, "item not found")
        return Response(item)

@extend_schema_view(
    list=extend_schema(
        summary="Search Extractors",
        description="Extractors are what extract the data from the text which is then converted into STIX objects.",
        responses={400: DEFAULT_400_ERROR, 200: Txt2stixExtractorSerializer},
    ),
    retrieve=extend_schema(
        summary="Get an extractor",
        description="Get a specific Extractor.",
        responses={400: DEFAULT_400_ERROR, 404: DEFAULT_404_ERROR, 200: Txt2stixExtractorSerializer},
    ),
)
class ExtractorsView(txt2stixView):
    openapi_tags = ["Extractors"]
    lookup_url_kwarg = "extractor_id"
    pagination_class = Pagination("extractors")

    def get_all(self):
        return self.all_extractors(["lookup", "pattern", "ai"])

@extend_schema_view(
    list=extend_schema(
        summary="Search for Whitelists",
        description="In many cases files will have IoC extractions that are not malicious. e.g. `google.com` (and thus they don't want them to be extracted). Whitelists provide a list of values to be compared to extractions. If a whitelist value matches an extraction, that extraction is removed. To see the values used in this Whitelist, visit the URL shown as the value for the `file` key",
        responses={400: DEFAULT_400_ERROR, 200: Txt2stixExtractorSerializer},
    ),
    retrieve=extend_schema(
        summary="Get a whitelist",
        description="Get a specific Whitelist. To see the values used in this Whitelist, visit the URL shown as the value for the `file` key",
        responses={400: DEFAULT_400_ERROR, 404: DEFAULT_404_ERROR, 200: Txt2stixExtractorSerializer},
    ),
)
class WhitelistsView(txt2stixView):
    lookup_url_kwarg = "whitelist_id"
    openapi_tags = ["Whitelists"]
    pagination_class = Pagination("whitelists")

    def get_all(self):
        return self.all_extractors(["whitelist"])

@extend_schema_view(
    list=extend_schema(
        summary="Search for aliases",
        description="Aliases replace strings in the text of a File with values defined in the Alias. Aliases are applied before extractions. For example, an alias of `USA` with a value `United States` will change all records of `USA` in the text with `United States`. To see the values used in this Alias, visit the URL shown as the value for the `file` key",
        responses={400: DEFAULT_400_ERROR, 200: Txt2stixExtractorSerializer},
    ),
    retrieve=extend_schema(
        summary="Get an Alias",
        description="Get a specific Alias. To see the values used in this Alias, visit the URL shown as the value for the `file` key",
        responses={400: DEFAULT_400_ERROR, 404: DEFAULT_404_ERROR, 200: Txt2stixExtractorSerializer},
    ),
)
class AliasesView(txt2stixView):
    openapi_tags = ["Aliases"]
    pagination_class = Pagination("aliases")

    lookup_url_kwarg = "alias_id"

    def get_all(self):
        return self.all_extractors(["alias"])
