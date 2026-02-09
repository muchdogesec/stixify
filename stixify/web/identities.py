import logging
import textwrap
import typing
from dogesec_commons.utils import Pagination
from drf_spectacular.utils import extend_schema, extend_schema_view

from dogesec_commons.identity.views import IdentityView as BaseIdentityView
from dogesec_commons.identity.models import Identity
from dogesec_commons.objects.helpers import ArangoDBHelper
from django.conf import settings

if typing.TYPE_CHECKING:
    from .. import settings

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

def classify_objects(object_ids: list[str]):
    collections = {}
    for doc_id in object_ids:
        collection, _, key = doc_id.partition("/")
        collection_holder: list = collections.setdefault(collection, [])
        collection_holder.append(key)
    return collections



def delete_identity_cleanup(identity: Identity):
    identity_id = identity.id
    assert isinstance(identity_id, str)

    helper = ArangoDBHelper(settings.VIEW_NAME, None)
    vertices = helper.execute_query(
        """
        FOR doc IN @@view
        FILTER doc.id == @identity_id OR doc.created_by_ref == @identity_id
        RETURN doc._id
    """,
        bind_vars={"identity_id": identity_id, "@view": settings.VIEW_NAME},
        paginate=False,
    )

    objects = helper.execute_query(
        """
        FOR doc IN @@view
        FILTER
                doc.id == @identity_id OR
                doc.created_by_ref == @identity_id OR
                doc._from IN @vertex_ids OR doc._to IN @vertex_ids
        RETURN doc._id
    """,
        bind_vars={
            "identity_id": identity_id,
            "@view": settings.VIEW_NAME,
            "vertex_ids": vertices,
        },
        paginate=False,
    )

    logging.info(f"removing {len(objects)} objects")
    for collection, documents in classify_objects(objects).items():
        logging.info(f"removing {len(documents)} documents from {collection}")
        helper.db.collection(collection).delete_many(
            [dict(_key=key) for key in documents], silent=True
        )

def auto_update_identities(instance: Identity):
    stix_obj = instance.dict
    stix_obj["_record_modified"] = timezone.now().isoformat().replace("+00:00", "Z")
    stix_obj['_product_identity'] = True
    query = """
    FOR doc IN @@vertex_collection
    FILTER doc.id == @identity.id
    UPDATE doc WITH @identity IN @@vertex_collection
    RETURN doc._key
    """
    binds = {
        "@vertex_collection": 'stixify_vertex_collection',
        "identity": stix_obj,
    }

    from django.http.request import HttpRequest
    from rest_framework.request import Request

    helper = ArangoDBHelper(settings.VIEW_NAME, Request(HttpRequest()))
    try:
        updated_keys = helper.execute_query(query, bind_vars=binds, paginate=False)
        logging.info(f"updated {len(updated_keys)} identities for {instance.id}")
        return updated_keys
    except Exception as e:
        logging.exception("could not update identities")

@receiver(post_save, sender=Identity)
def auto_update_identities_callback(sender, instance: Identity, created, **kwargs):
    if not created:
        auto_update_identities(instance)

@receiver(post_delete, sender=Identity)
def delete_identity_cleanup_callback(sender, instance: Identity, **kwargs):
    return delete_identity_cleanup(instance)


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