from django.apps import AppConfig


class ClassifierConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "stixify.classifier"
    verbose_name = "Classifier"
