# from django.apps import AppConfig


# class ApiConfig(AppConfig):
#     name = 'api'

from django.apps import AppConfig
import logging
logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        from . import signals
        logger.info("API SIGNALS LOADED")