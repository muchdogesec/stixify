import itertools
import os
import time
from urllib.parse import urljoin
from dogesec_commons.objects.helpers import ArangoDBHelper
from txt2stix.retriever import STIXObjectRetriever
from stixify.web.models import Job


def batched(iterable, n):
    """Yield lists of size n from iterable."""
    it = iter(iterable)
    while True:
        batch = list(itertools.islice(it, n))
        if not batch:
            return
        yield batch


def get_vulnerabilities(collection_name) -> dict[str, list[str]]:
    helper = ArangoDBHelper(collection_name, None)
    binds = {"@collection": collection_name}
    vulnerabilities = helper.execute_query(
        """
FOR doc IN @@collection
FILTER doc.type == "vulnerability"
COLLECT name = doc.name INTO prim_key = doc._key
RETURN [name, prim_key]
    """,
        bind_vars=binds,
        paginate=False,
    )
    vulnerabilities = dict(vulnerabilities)
    return vulnerabilities


def get_updates(vulnerabilities, update_time):
    retriever = STIXObjectRetriever("vulmatch")
    for chunk in batched(vulnerabilities, 50):
        chunk = ",".join(chunk)
        for v in retriever._retrieve_objects(
            urljoin(retriever.api_root, f"v1/cve/objects/?cve_id={chunk}")
        ):
            primary_keys = vulnerabilities[v["name"]]
            for _key in primary_keys:
                doc = {"_key": _key, **v, "_stixify_updated_on": update_time}
                doc.pop("id", None)
                yield doc


def run_on_collections(job: Job, batch_size=500):
    update_time = time.time()
    job.extra = job.extra or {}
    db = ArangoDBHelper("", None).db
    collection_name = "stixify_vertex_collection"
    collection = db.collection(collection_name)
    vulnerabilities = get_vulnerabilities(collection_name)

    job.extra["unique_vulnerabilities"] = len(vulnerabilities)
    job.extra["document_count"] = sum(len(x) for x in vulnerabilities.values())
    job.extra["processed_documents"] = 0
    job.save(update_fields=["extra"])

    for chunk in batched(get_updates(vulnerabilities, update_time), batch_size):
        collection.update_many(chunk, raise_on_document_error=True)
        job.extra["processed_documents"] += len(chunk)
        job.save(update_fields=["extra"])