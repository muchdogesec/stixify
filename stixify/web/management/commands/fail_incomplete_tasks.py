from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from stixify.web import models


class Command(BaseCommand):
    help = "Fail incomplete jobs and remove their upload locks."

    def handle(self, *args, **options):
        incomplete_jobs = models.Job.objects.filter(
            state__in=(models.JobState.PENDING, models.JobState.PROCESSING)
        )
        job_ids = list(incomplete_jobs.values_list("id", flat=True))
        updated = incomplete_jobs.update(
            state=models.JobState.CANCELED,
            error="canceled automatically during restart",
            completion_time=timezone.now(),
        )
        cache.delete_many([f"arango_upload_lock:{job_id}" for job_id in job_ids])
        cache.delete("arango_upload_active_count")
        self.stdout.write(f"Failed {updated} incomplete job(s).")
