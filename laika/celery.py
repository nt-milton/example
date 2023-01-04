import os

from celery import Celery
from celery.signals import setup_logging
from kombu import Exchange, Queue

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'laika.settings')
app = Celery('laika')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
LONG_RUN_QUEUE = 'long_run'
DEFAULT_QUEUE = 'celery'
MAX_PRIORITY = 10
app.conf.task_queues = [
    Queue(
        LONG_RUN_QUEUE,
        Exchange(LONG_RUN_QUEUE),
        routing_key=LONG_RUN_QUEUE,
        queue_arguments={'x-max-priority': MAX_PRIORITY},
    ),
    Queue(DEFAULT_QUEUE, Exchange(DEFAULT_QUEUE), routing_key=DEFAULT_QUEUE),
]

app.conf.task_routes = {
    'run_integration': {'queue': LONG_RUN_QUEUE},
    'run_initial_and_notify_monitors': {'queue': LONG_RUN_QUEUE},
    'simulator': {'queue': LONG_RUN_QUEUE},
}


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
