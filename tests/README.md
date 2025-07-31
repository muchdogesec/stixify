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