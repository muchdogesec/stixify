from typing import List, Literal
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.plumbing import ResolvedComponent
from rest_framework.serializers import Serializer
import uritemplate
from .utils import ErrorSerializer
from drf_spectacular.utils import OpenApiResponse, OpenApiExample


class StixifyAutoSchema(AutoSchema):
    def get_tags(self) -> List[str]:
        if hasattr(self.view, "openapi_tags"):
            return self.view.openapi_tags
        return super().get_tags()
    
    def get_override_parameters(self):
        params = super().get_override_parameters()
        path_variables = uritemplate.variables(self.path)
        for param in getattr(self.view, 'openapi_path_params', []):
            if param.name in path_variables:
                params.append(param)
        return params
    
    def _map_serializer_field(self, field, direction, bypass_extensions=False):
        if getattr(field, 'internal_serializer', None):
            return super()._map_serializer_field(field.internal_serializer, direction, bypass_extensions)
        return super()._map_serializer_field(field, direction, bypass_extensions)


    def _map_serializer(self, serializer, direction, bypass_extensions=False):
        if getattr(serializer, "get_schema", None):
            return serializer.get_schema()
        return super()._map_serializer(serializer, direction, bypass_extensions)


DEFAULT_400_ERROR = OpenApiResponse(
    ErrorSerializer,
    "The server did not understand the request",
    [
        OpenApiExample(
            "http400",
            {"message": " The server did not understand the request", "code": 400},
        )
    ],
)


DEFAULT_404_ERROR = OpenApiResponse(
    ErrorSerializer,
    "Resource not found",
    [
        OpenApiExample(
            "http404",
            {
                "message": "The server cannot find the resource you requested",
                "code": 404,
            },
        )
    ],
)
