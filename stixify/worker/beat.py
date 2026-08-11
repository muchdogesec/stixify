from datetime import timedelta

from celery import Celery


app = Celery("stixify-beat")
app.config_from_object("os:environ", namespace="CELERY")

app.conf.beat_schedule = {
    "auto_refresh_statistics_data": {
        "task": "stixify.worker.tasks.auto_refresh_statistics_data",
        "schedule": timedelta(minutes=10),
    }
}
