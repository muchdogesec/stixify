from django.apps import AppConfig


class WebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'stixify.web'
    label = "stixify_core"

    def ready(self):
        # Import the post-upload hook to register it
        from stixify.web.values import process_uploaded_objects_hook

