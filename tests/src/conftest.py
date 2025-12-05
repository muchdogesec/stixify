import pytest


@pytest.fixture
def celery_eager():
    from stixify.worker.celery import app

    app.conf.task_always_eager = True
    yield
    app.conf.task_always_eager = False