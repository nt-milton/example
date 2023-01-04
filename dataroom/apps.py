from django.apps import AppConfig


class DataroomConfig(AppConfig):
    name = 'dataroom'

    def ready(self):
        import dataroom.signals  # noqa: F401 imported but unused
