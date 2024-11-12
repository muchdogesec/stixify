# Tests

## Setup

```shell
python3 -m venv stixify-venv
source stixify-venv/bin/activate
# install requirements
pip3 install -r requirements.txt
````

## Run tests

Download the files used for tests:

```shell
python3 tests/download_test_files.py
```

This will add profiles used by tests (and also delete all existing profiles)

```shell
python3 tests/setup_profiles.py
```

Upload the files used for tests:

```shell
python3 tests/add_files.py
```


## Delete everything!

```shell
python3 tests/delete_all_files.py && \
python3 tests/delete_all_reports.py
```

```shell

```