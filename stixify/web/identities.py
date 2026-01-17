import textwrap
from dogesec_commons.utils import Pagination
from drf_spectacular.utils import extend_schema, extend_schema_view

from dogesec_commons.identity.views import IdentityView as BaseIdentityView

@extend_schema_view(
    destroy=extend_schema(
        summary="Delete an Identity and all its Files and Reports",
        description=textwrap.dedent(
            """
            Delete an Identity object and ALL Files and Reports linked to it

            IMPORTANT: make sure this is the request you want to run. It will delete all data related to the Identity ID, including the Identity object, all Reports belonging to the Identity object, all objects belonging to the Identity Object and all objects within those feeds.

            You cannot delete an Identity uploaded to a Feed using this endpoint. You must update it using the Feed objects endpoints.
            """
        ),
    ),
    list=extend_schema(
        summary="List Identities",
        description=textwrap.dedent(
            """
            List all STIX Identity objects that can be used to create reports.

            You can create an Identity using the POST Identities endpoint.

            This request will not return Identity objects that have been extracted from Reports.
            """
        ),
    ),
    retrieve=extend_schema(
        summary="Retrieve an Identity",
        description=textwrap.dedent(
            """
            Retrieve a STIX Identity object by its ID.

            This request will not return Identity objects that have been extracted from Reports.
            """
        ),
    ),
)
class IdentityView(BaseIdentityView):
    pagination_class = Pagination('objects')