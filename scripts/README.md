# Web import memory

With the application's environment configured, run a fresh process:

```sh
python scripts/profile_web_imports.py --skip-external-startup
```

This skips ArangoDB startup, then measures WSGI, URL loading, extractor metadata,
and AI configuration validation. Older dependency releases construct AI clients
during validation; use `--skip-profile-validation` for that baseline.

The fix requires txt2stix 1.7.2, dogesec-commons 1.5.1 and file2txt 1.1.0.
Publish these dependency releases before building Stixify from the updated pins.
Local wheels can be used for verification before publication.

In the same cached Linux image, route-load RSS fell from 406 MiB to 149 MiB
with the fixed dependency wheels. After metadata and model validation it was
151 MiB, with no LlamaIndex, Transformers, pandas, OpenAI or phone geography
modules loaded. Configuration validation does not check provider credentials;
processing workers still construct the actual clients.

These are single-process measurements, not production container totals.
Gunicorn workers share some mappings; use PSS rather than summing their RSS.
