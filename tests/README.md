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

