from django.apps import AppConfig


class PolicyConfig(AppConfig):
    name = 'policy'

    def ready(self):
        import policy.signals  # noqa: F401 imported but unused
