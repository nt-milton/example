from django.apps import AppConfig


class SeederConfig(AppConfig):
    name = 'seeder'

    def ready(self):
        import seeder.signals  # noqa: F401 imported but unused
