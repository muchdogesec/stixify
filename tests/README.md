# Tests

## Environment setup

```shell
python3 -m venv stixify-venv && \
source stixify-venv/bin/activate && \
pip3 install -r requirements.txt
````

## API schema tests

```shell
st run --checks all http://127.0.0.1:8001/api/schema --generation-allow-x00 true
```

## Functional tests

You must create a `.env` file with the following secrets;

```txt
MARKER_API_KEY=
```

You can then execute these tests as follows;

```shell
act -W .github/workflows/schemathesis_test.yml --secret-file secrets.env
```