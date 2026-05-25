import time
from dogesec_commons.objects.helpers import ArangoDBHelper
from stixify.web.models import Job
from dogesec_commons.objects.kb_sync import sync


def run_on_collections(job: Job, knowledgebase):
    update_time = time.time()
    if job:
        job.extra = job.extra or {}
        job.extra.update(
            unique_objects=0,
            processed_items=0,
        )
        job.save(update_fields=["extra"])

    collection_name = "stixify_vertex_collection"
    processed_count, updated_count = sync.run_on_kb_and_collection(
        collection_name, knowledgebase, update_time=update_time
    )
    job.extra["processed_items"] += updated_count
    job.extra["unique_objects"] += processed_count
    job.save(update_fields=["extra"])