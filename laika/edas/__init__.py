import logging
import re
from typing import Any

from laika.edas.edas import EdaPublisher, EdaRegistry, PikaClient
from laika.edas.utils import auto_discover_edas_modules, get_eda_apps
from laika.settings import DJANGO_SETTINGS, ENVIRONMENT

logger = logging.getLogger(__name__)

vhost = '/'
user = DJANGO_SETTINGS.get('RABBITMQ_USER')
password = DJANGO_SETTINGS.get('RABBITMQ_PASSWORD')
broker = DJANGO_SETTINGS.get('RABBITMQ_BROKER')
port = DJANGO_SETTINGS.get('RABBITMQ_PORT')

credentials = user, password

PR_ENVIRONMENT_REGEX = r"^[a-z]{2,3}-\d{4}-?"
if ENVIRONMENT:
    if re.match(PR_ENVIRONMENT_REGEX, ENVIRONMENT):
        vhost += ENVIRONMENT

connection_data: dict[str, Any] = dict(
    credentials=credentials, broker=broker, port=port, vhost=vhost
)

edas_modules = auto_discover_edas_modules()
eda_apps = get_eda_apps(edas_modules)
EdaRegistry.register_listeners(edas_modules)

client = PikaClient(apps_to_subscribe=eda_apps, **connection_data)

eda_publisher = EdaPublisher(client=client)
