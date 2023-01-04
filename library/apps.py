from django.apps import AppConfig


class LibraryConfig(AppConfig):
    name = 'library'

    def ready(self):
        import library.signals  # noqa: F401 imported but unused
