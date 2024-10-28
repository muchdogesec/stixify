"""
Django settings for stixify project.

Generated by 'django-admin startproject' using Django 5.1.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

import logging
import os
from pathlib import Path
from textwrap import dedent
from typing import Any
import uuid

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['DJANGO_SECRET']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", False)

ALLOWED_HOSTS = []

MEDIA_ROOT = Path("media/uploads")

STATIC_ROOT = MEDIA_ROOT.with_name("staticfiles")
MEDIA_URL = str("media/uploads/")

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'drf_spectacular',
    'django.contrib.postgres',
    'stixify.web',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'stixify.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'stixify.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB'),            # Database name
        'USER': os.getenv('POSTGRES_USER'),          # Database user
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),  # Database password
        'HOST': os.getenv('POSTGRES_HOST'),                              # PostgreSQL service name in Docker Compose
        'PORT': '5432',                              # PostgreSQL default port
    },
    'sqlite': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Storage

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
          "location": MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

if os.getenv("USE_S3_STORAGE") == "1":
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["R2_BUCKET_NAME"],
            "endpoint_url": os.environ["R2_ENDPOINT_URL"],
            "access_key": os.environ["R2_ACCESS_KEY"],
            "secret_key": os.environ["R2_SECRET_KEY"],
            'custom_domain': os.environ["R2_CUSTOM_DOMAIN"],
            'location': 'stixify/media',
        },
    }

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "stixify.web.autoschema.StixifyAutoSchema",
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
}

STIX_NAMESPACE = uuid.UUID('e92c648d-03eb-59a5-a318-9a36e6f8057c')

TXT2STIX_INCLUDE_URL = "https://github.com/muchdogesec/txt2stix/blob/main/includes/"

MAXIMUM_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", 50))
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", 50))

SPECTACULAR_SETTINGS: dict[str, Any] = {
    "COMPONENT_SPLIT_REQUEST": True,
    "TITLE": "Stixify API",
    "DESCRIPTION": dedent(
        """
        Stixify extracts machine readable intelligence from unstructured data.\n\n
        [DOGESEC](https://www.dogesec.com/) offer a fully hosted web version of Stixify which includes many additional features over those in this codebase. [You can find out more about the web version here](https://www.stixify.com/).
    """
    ),
    "VERSION": "1.0.0",
    "CONTACT": {
        "email": "noreply@dogesec.com",
        "url": "https://github.com/muchdogesec/stixify",
    },
    "TAGS": [
        {"name": "Files", "description": "Upload files and retrieve uploaded files"},
        {"name": "Reports", "description": "Files are processed into Reports. Search and view created Reports."},
        {"name": "Dossiers", "description": "Group together Reports as Dossiers around a theme."},
        {"name": "Objects", "description": "Search through STIX object extracted from Files in Reports."},
        {"name": "Profiles", "description": "Create and search for extraction profile applied to text Files."},
        {"name": "Aliases", "description": "Search through aliases that can be used in profiles (see txt2stix for more information)"},
        {"name": "Extractors", "description": "Search through extractors that can be used in profiles (see txt2stix for more information)"},
        {"name": "Whitelists", "description": "Search through whitelists that can be used in profiles (see txt2stix for more information)"},
        {"name": "Jobs", "description": "Check the status of data retrieval from Files uploaded."},
    ]
}


ARANGODB_DATABASE   = "stixify"
VIEW_NAME = "stixify_view"
ARANGODB_USERNAME   = os.getenv('ARANGODB_USERNAME')
ARANGODB_PASSWORD   = os.getenv('ARANGODB_PASSWORD')
ARANGODB_HOST_URL   = os.getenv("ARANGODB_HOST_URL")

GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY")
if not GOOGLE_VISION_API_KEY:
    logging.warning("GOOGLE_VISION_API_KEY not set")