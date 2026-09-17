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


def test_web_routes_and_profile_validation_do_not_load_worker_dependencies():
    _run_in_clean_process(
        """
        import django
        import sys
        from unittest.mock import patch

        with patch("dogesec_commons.objects.db_view_creator.startup_func"):
            django.setup()

        import stixify.worker.tasks
        import stixify.wsgi
        import stixify.urls
        from django.test import Client
        from dogesec_commons.stixifier.serializers import (
            validate_model, validate_extractor, uses_ai, Txt2stixExtractorSerializer,
        )

        assert Client().get('/api/healthcheck/').status_code == 204
        assert Txt2stixExtractorSerializer.all_extractors(('pattern',))
        validate_extractor('extractor', ['pattern'], 'pattern_ipv4_address_only')
        uses_ai(['pattern_ipv4_address_only'])
        for provider in ('openai', 'anthropic', 'gemini', 'deepseek', 'openrouter'):
            assert validate_model(provider) == provider
            assert validate_model(provider + ':example-model') == provider + ':example-model'

        forbidden = (
            'stixify.worker.process_post', 'stixify.worker.pdf_converter',
            'stixify.classifier.tasks', 'txt2stix.txt2stix', 'txt2stix.bundler',
            'txt2stix.indicator', 'txt2stix.pattern', 'llama_index',
            'transformers', 'torch', 'pandas', 'sklearn', 'joblib',
            'openai', 'anthropic', 'google.genai', 'phonenumbers.geodata',
        )
        loaded = [
            name for name in sys.modules
            if any(name == prefix or name.startswith(prefix + '.') for prefix in forbidden)
        ]
        assert not loaded, loaded
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
