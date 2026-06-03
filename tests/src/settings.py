from stixify.settings import *

ARANGODB_DATABASE = 'stixify_test'
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-cache-name",
    }
}

