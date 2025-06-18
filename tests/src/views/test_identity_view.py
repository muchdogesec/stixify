from stixify.web import models
from stixify.web.serializers import FileSerializer, JobSerializer
from stixify.web.views import IdentityView
import pytest
from unittest.mock import patch
from .test_report_view import upload_arango_objects

def test_list_identities(client):
    resp = client.get('/api/v1/identities/')
    assert resp.status_code == 200
    assert {obj['id'] for obj in resp.data['objects']}.isdisjoint(IdentityView.SYSTEM_IDENTITIES)

@pytest.mark.parametrize(
    "identity_id",
    [
       "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5",
    ]
)
def test_retrieve_identities(client, identity_id):
    resp = client.get(f'/api/v1/identities/{identity_id}/')
    assert resp.status_code == 200
    assert resp.data['objects'][0]['id'] == identity_id

@pytest.mark.django_db
def test_delete_identity(client, stixify_file):
    identity_id = "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30"
    report_id = "report--ed758a1b-34fe-4fca-8178-0c30d93a03ab"
    resp = client.delete(f'/api/v1/identities/{identity_id}/')
    assert resp.status_code == 204
    with pytest.raises(Exception):
        stixify_file.refresh_from_db()
    
    