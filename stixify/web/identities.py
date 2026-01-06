import textwrap
from dogesec_commons.utils import Pagination
from drf_spectacular.utils import extend_schema, extend_schema_view

from dogesec_commons.identity.views import IdentityView as BaseIdentityView

@extend_schema_view(
    destroy=extend_schema(
        summary="Delete all objects associated with identity",
        description=textwrap.dedent(
            """
            This endpoint will delete all Files, Reports, and any other STIX objects created using this identity.
            """
        ),
    ),
    list=extend_schema(
        summary="Search identity objects",
        description=textwrap.dedent(
            """
            This endpoint will allow you to search for all identities that exist.
            """
        ),
    ),
    retrieve=extend_schema(
        summary="GET identity object by STIX ID",
        description=textwrap.dedent(
            """
            This endpoint will allow you to GET an identity object by its STIX ID.
            """
        ),
    ),
)
class IdentityView(BaseIdentityView):
    pagination_class = Pagination('objects')