# Tests

## Setup

```shell
python3 -m venv stixify-venv
source stixify-venv/bin/activate
# install requirements
pip3 install -r requirements.txt
````

## API schema tests

```shell
st run --checks all http://127.0.0.1:8001/api/schema --generation-allow-x00 true
```

## Run tests

Download the files used for tests:

```shell
python3 tests/download_test_files.py
```

These files will be stored in `/tests/files/`

This will add profiles used by tests (and also delete all existing profiles)

```shell
python3 tests/setup_profiles.py
```

Upload ALL the files used for tests:

```shell
python3 tests/add_files.py
```

It is also possible to control what files are uploaded by using the `report_id` value found in `add_files.py`, e.g..

```shell
python3 tests/add_files.py --report-ids report--6cb8665e-3607-4bbe-a9a3-c2a46bd13630 report--b2869cb5-5270-4543-ac71-601cc8cd2e3b
```

PDF: Bitdefender rdstealer

```shell
python3 tests/add_files.py --report-ids report--aaec934b-9141-4ff7-958b-3b99a7b24234
```

HTML: GroupIB 0ktapus


```shell
python3 tests/add_files.py --report-ids report--5795e067-72a4-4953-87ed-f6c56dc6f639
```

Word: txt2stix local extractions docx

```shell
python3 tests/add_files.py --report-ids report--2bd196b5-cc59-491d-99ee-ed5ea2002d61
```


## Delete everything!

```shell
python3 tests/delete_all_files.py && \
python3 tests/delete_all_reports.py && \
python3 tests/delete_all_dossiers.py && \
python3 tests/delete_all_profiles.py
```

Note if using Cloudflare R2 (and app fails to correctly delete file via API commands -- e.g. if destroy db), to delete all files in a bucket install rclone and run;

```shell
rclone delete remote:bucket-name
```

e.g.

```shell
rclone delete r2:stixify-local-david
```