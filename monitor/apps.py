from django.apps import AppConfig


class MonitorConfig(AppConfig):
    name = 'monitor'

    def ready(self):
        import monitor.signals  # noqa: F401 imported but unused
