from typing import List, Literal
from dogesec_commons.utils.autoschema import CustomAutoSchema
from drf_spectacular.plumbing import ResolvedComponent
from rest_framework.serializers import Serializer
import uritemplate
from dogesec_commons.utils.serializers import CommonErrorSerializer as ErrorSerializer
from drf_spectacular.utils import OpenApiResponse, OpenApiExample


class StixifyAutoSchema(CustomAutoSchema):
    pass


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
