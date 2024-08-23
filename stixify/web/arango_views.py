from .arango_helpers import ArangoDBHelper
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets, decorators, exceptions
import typing
from .utils import Response

from django.conf import settings
if typing.TYPE_CHECKING:
    from .. import settings

@extend_schema_view(
    scos=extend_schema(
        summary="Get a STIX Cyber Observable Object",
        description="Search for observable objects.",
    ),
    retrieve=extend_schema(
        summary="Get an object",
        description="Get an Object using its ID. You can search for Object IDs using the GET Objects SDO, SCO, or SRO endpoints."
    ),
    sdos=extend_schema(
        summary="Get a STIX Domain Object",
        description="Search for domain objects.",
    ),
    sros=extend_schema(
        summary="Get a STIX Relationship Object",
        description="Search for relationship objects. This endpoint is particularly useful to search what other Objects an SCO or SDO is linked to.",
    ),
)
class ObjectsView(viewsets.ViewSet):
    openapi_tags = ["Objects"]
    lookup_url_kwarg = "id"

    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters(),
    )
    @decorators.action(detail=False, methods=["GET"])
    def scos(self, request, *args, **kwargs):
        return ArangoDBHelper(settings.VIEW_NAME, request).get_scos()

    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters(),
    )
    @decorators.action(detail=False, methods=["GET"])
    def sdos(self, request, *args, **kwargs):
        return ArangoDBHelper(settings.VIEW_NAME, request).get_sdos()

    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters(),
    )
    @decorators.action(detail=False, methods=["GET"])
    def sros(self, request, *args, **kwargs):
        return ArangoDBHelper(settings.VIEW_NAME, request).get_sros()

    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters(),
    )
    def retrieve(self, request, *args, **kwargs):
        return ArangoDBHelper(settings.VIEW_NAME, request).get_objects_by_id(
            kwargs.get(self.lookup_url_kwarg)
        )


class ReportView(viewsets.ViewSet):
    openapi_tags = ["Objects"]
    lookup_url_kwarg = 'report_id'
    @extend_schema()
    def retrieve(self, request, *args, **kwargs):
        report_id = kwargs.get(self.lookup_url_kwarg)
        reports = ArangoDBHelper(settings.VIEW_NAME, request).get_report_by_id(
            report_id
        )
        if not reports:
            raise exceptions.NotFound(detail=f"report object with id `{report_id}` - not found")
        return Response(reports[-1])
    
    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters(),
    )
    def list(self, request, *args, **kwargs):
        return ArangoDBHelper(settings.VIEW_NAME, request).get_reports()
    
    @extend_schema(
            
    )
    def destroy(self, request, *args, **kwargs):
        report_id = kwargs.get(self.lookup_url_kwarg)
        ArangoDBHelper(settings.VIEW_NAME, request).remove_report(
            report_id
        )
        return Response()