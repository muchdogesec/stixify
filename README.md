# Stixify

## Before you begin...

We offer a fully hosted web version of Stixify which includes many additional features over those in this codebase. [You can find out more about the web version here](https://www.stixify.com/).

## Overview

![](docs/stixify.png)

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

Stixify has various settings that are defined in an `.env` file.

To create one using the default settings:

```shell
cp .env.example .env
```

#### A note on ArangoDB secrets

Note, this script will not install an ArangoDB instance.

If you're new to ArangoDB, [you can install the community edition quickly by following the instructions here](https://arangodb.com/community-server/).

If you are running ArangoDB locally, be sure to set `ARANGODB_HOST_URL='http://host.docker.internal:8529'` in the `.env` file otherwise you will run into networking errors.

The script will automatically create a database called `stixify_database` when the container is spun up (if it does not exist).

The converted STIX objects will be stored in collections names `stixify_vertex_collection` and `stixify_edge_collection` depending on the object type.

#### A note on Django and Postgres secrets

Note, if you intend on using this for testing, you can leave the variables in the `.env` as is. However, these need to be changed in a production install for security.

#### A note Cloudflare R2 storage

By default, all images will be stored locally on the server. This is fine if you're using Obstracts on your own machine. If running on a remote server, Obstracts support the storage of images on Cloudflare R2. This can be set in the `.env` file/

### Build the Docker Image

```shell
sudo docker compose build
```

### Start the server

```shell
sudo docker compose up
```

### Access the server

The webserver (Django) should now be running on: http://127.0.0.1:8004/

You can access the Swagger UI for the API in a browser at: http://127.0.0.1:8004/api/schema/swagger-ui/



#### Running in production

Note, if you intend on using this in production, you should also modify the variables in the `.env` file for `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASS`, `DJANGO_SECRET` and `DEBUG` (to `False`)

## Support

[Minimal support provided via the DOGESEC community](https://community.dogesec.com/).

## License

[Apache 2.0](/LICENSE).