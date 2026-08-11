import os
from celery import Celery
# Set the default Django settings module for the 'celery' program.

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stixify.settings')

app = Celery('stixify')


app.config_from_object('os:environ', namespace='CELERY')

app.conf.imports = (
    "stixify.worker.process_post",
    "stixify.classifier.tasks",
    "stixify.worker.tasks",
)

# Load task modules from all registered Django apps.
app.autodiscover_tasks()
