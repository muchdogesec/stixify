# Tests

## Environment setup

```shell
python3 -m venv stixify-venv && \
source stixify-venv/bin/activate && \
pip3 install -r requirements.txt
````

You also need to download and install ACT:

https://github.com/nektos/act

## API schema tests

These tests are run via Github actions.

```shell
st run --checks all http://127.0.0.1:8001/api/schema --generation-allow-x00 true
```

## Functional tests

These tests are run via Github actions.

You must create a `.env` file with the following secrets (on Github they are stored in an environment called `stixify_tests`);

```txt
MARKER_API_KEY=
```

You can then execute these tests as follows;

```shell
act -W .github/workflows/schemathesis_test.yml --secret-file secrets.env
```

## Upload mutex tests

The test Compose stack supplies Redis on port 16379. Run the mutex tests alone with:

```shell
STIXIFY_TEST_REDIS_URL=redis://localhost:16379/15 python -m pytest --noconftest -p no:django tests/src/test_upload_lock.py
```

These tests use unique, expiring Redis keys and do not flush the database. Without
`STIXIFY_TEST_REDIS_URL`, the Redis integration cases are skipped; CI sets it in
`tests/tests.env`.
