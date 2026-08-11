import os
import subprocess
import sys
import textwrap

from dotenv import load_dotenv


def _run_in_clean_process(code):
    load_dotenv()
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "stixify.settings")
    subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=True,
        env=env,
    )


def test_django_and_task_imports_do_not_load_worker_dependencies():
    _run_in_clean_process(
        """
        import django
        import sys
        from unittest.mock import patch

        with patch("dogesec_commons.objects.db_view_creator.startup_func"):
            django.setup()

        import stixify.worker.tasks

        assert not any(
            name == "txt2stix" or name.startswith("txt2stix.")
            for name in sys.modules
        )
        assert "stixify.worker.process_post" not in sys.modules
        assert "stixify.worker.pdf_converter" not in sys.modules
        assert "stixify.classifier.tasks" not in sys.modules
        assert "sklearn.metrics.pairwise" not in sys.modules
        assert "joblib" not in sys.modules
        """
    )


def test_beat_app_does_not_load_django_or_worker_dependencies():
    _run_in_clean_process(
        """
        import os
        import sys

        os.environ.pop("DJANGO_SETTINGS_MODULE", None)
        from stixify.worker.beat import app
        from django.apps import apps

        assert not apps.ready
        assert "stixify.worker.tasks" not in sys.modules
        assert "stixify.worker.process_post" not in sys.modules
        assert "stixify.classifier.tasks" not in sys.modules
        assert "txt2stix" not in sys.modules
        assert "joblib" not in sys.modules
        assert app.conf.beat_schedule["auto_refresh_statistics_data"]["task"] == (
            "stixify.worker.tasks.auto_refresh_statistics_data"
        )
        """
    )


def test_celery_imports_preload_worker_dependencies():
    _run_in_clean_process(
        """
        import sys
        from unittest.mock import patch

        with patch("dogesec_commons.objects.db_view_creator.startup_func"):
            from stixify.worker.celery import app
            app.loader.import_default_modules()

        assert "stixify.worker.process_post" in sys.modules
        assert "stixify.worker.pdf_converter" in sys.modules
        assert "stixify.classifier.tasks" in sys.modules
        assert "txt2stix" in sys.modules
        assert "joblib" in sys.modules
        """
    )
