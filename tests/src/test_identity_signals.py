import pytest
from stixify.web.identities import (
    delete_identity_cleanup,
    Identity,
    auto_update_identities,
)
from unittest.mock import patch, MagicMock
import django.test
from dogesec_commons.objects.helpers import ArangoDBHelper

url = "/api/v1/identities/"


@pytest.fixture(autouse=True)
def use_db(db):
    pass


def test_delete_identity_calls_cleanup_signal(identity):
    identity_id = "identity--8ef05850-abcd-51f7-80be-50e4376dbe63"
    identity = Identity.objects.create(id=identity_id, stix=dict(name="Test Identity"))
    with patch(
        "stixify.web.identities.delete_identity_cleanup"
    ) as mock_cleanup_receiver:
        identity.delete()
        mock_cleanup_receiver.assert_called_once_with(
            identity,
        )


def test_identity_modify_calls_auto_update_signal(identity):
    identity_id = identity.id
    identity = Identity.objects.get(id=identity_id)
    with patch(
        "stixify.web.identities.auto_update_identities"
    ) as mock_auto_update_receiver:
        identity.stix["name"] = "Updated Test Identity"
        identity.save()
        mock_auto_update_receiver.assert_called_once_with(
            identity,
        )


def test_auto_update_identities(client: django.test.Client, identity):
    identity_id = identity.id
    identity = Identity.objects.get(id=identity_id)
    name = "Updated Test Identity via Auto Update"
    identity.stix["name"] = name
    identity.save()
    new_identity = client.get(url + identity_id + "/").data
    assert new_identity["name"] == name, "identity name must be updated"
    helper = ArangoDBHelper("stixify_vertex_collection", None)
    arango_identities = helper.execute_query(
        f"""FOR doc IN stixify_vertex_collection
    FILTER doc.id == @identity_id
    RETURN doc""",
        bind_vars={"identity_id": identity_id},
        paginate=False,
    )
    for arango_identity in arango_identities:
        assert (
            arango_identity["name"] == name
        ), "identity name in arangodb must be updated"
