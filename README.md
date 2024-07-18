# Stixify

## Overview

Stixify takes a file and converts into structured threat intelligence.

Lots of intelligence is shared in PDFs, Word docs, Powerpoints, emails, Slack messages, etc.

To help automate the extraction of intelligence from these documents, Stixify automatically extracts indicators for viewing to a user.

It works at a high level like so:

1. A file is added to Stixify (selecting profile to be used)
2. The file is converted into markdown by file2txt
3. The markdown is run through txt2stix where txt2stix pattern extractions/whitelists/aliases are run based on staff defined profile
4. STIX bundles are generated for the file, and stored in a database called `stixify` and a collection matching the `identity` ID used to create the objects
5. A user can access the bundle data or specific objects in the bundle via the API

### Download and configure

```shell
# clone the latest code
git clone https://github.com/muchdogesec/stixify
```

### Configuration options

Obstracts has various settings that are defined in an `.env` file.

To create one using the default settings:

```shell
cp .env.example .env
```

### Build the Docker Image

```shell
sudo docker-compose build
```

### Start the server

```shell
sudo docker-compose up
```

#### ArangoDB install

Note, this script will not install an ArangoDB instance.

If you're new to ArangoDB, [you can install the community edition quickly by following the instructions here](https://arangodb.com/community-server/).

If you are running ArangoDB locally, be sure to set `ARANGODB_HOST='host.docker.internal'` in the `.env` file otherwise you will run into networking errors.

#### Running in production

Note, if you intend on using this in production, you should also modify the variables in the `.env` file for `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASS`, `DJANGO_SECRET` and `DEBUG` (to `False`)


## Support

[Minimal support provided via the DOGESEC community](https://community.dogesec.com/).

## License

[AGPLv3](/LICENSE).