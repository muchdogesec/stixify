"""Measure a fresh web process, including URL loading on the first request.

Run with the application's environment configured:
    python scripts/profile_web_imports.py --skip-external-startup

This is a single-process measurement, not total Gunicorn/container memory.
"""

import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import resource
import sys
import time


def snapshot(stage, started):
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "stage": stage,
        "peak_rss_mib": round(peak / (1024 ** 2 if sys.platform == "darwin" else 1024), 2),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "module_count": len(sys.modules),
    }
    # Linux PSS accounts for shared mappings; do not sum worker RSS values.
    rollup = Path("/proc/self/smaps_rollup")
    if rollup.exists():
        for line in rollup.read_text().splitlines():
            key, _, value = line.partition(":")
            if key in ("Rss", "Pss", "Private_Dirty", "Private_Clean"):
                result[key.lower() + "_mib"] = round(int(value.split()[0]) / 1024, 2)
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-external-startup", action="store_true",
                        help="Skip the shared app's ArangoDB initialization hook.")
    parser.add_argument("--skip-profile-validation", action="store_true",
                        help="Compare older releases whose model validation constructs AI clients.")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stixify.settings")
    started = time.monotonic()
    snapshot("baseline", started)
    from unittest.mock import patch

    context = patch("dogesec_commons.objects.db_view_creator.startup_func") if args.skip_external_startup else nullcontext()
    with context:
        from stixify.wsgi import application  # noqa: F401
    snapshot("wsgi", started)
    import stixify.urls  # noqa: F401
    snapshot("urls", started)
    from dogesec_commons.stixifier.serializers import validate_model, Txt2stixExtractorSerializer

    Txt2stixExtractorSerializer.all_extractors(("pattern", "lookup", "ai"))
    if not args.skip_profile_validation:
        for provider in ("openai", "anthropic", "gemini", "deepseek", "openrouter"):
            validate_model(provider)
    snapshot("profile_metadata_and_validation", started)
    prefixes = ("txt2stix", "llama_index", "pandas", "transformers", "torch", "openai", "phonenumbers.geodata")
    print(json.dumps({"loaded_modules": {
        prefix: sum(name == prefix or name.startswith(prefix + ".") for name in sys.modules)
        for prefix in prefixes
    }}), flush=True)


if __name__ == "__main__":
    main()
