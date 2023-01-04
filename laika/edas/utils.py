import logging
from importlib import import_module

from django.apps import apps

from laika.edas.edas import EDA_MODULE_NAME

logger = logging.getLogger(__name__)


def get_eda_apps(edas_modules):
    if not edas_modules:
        return []
    return [eda_module.__name__.split('.')[0] for eda_module in edas_modules]


def auto_discover_edas_modules():
    configured_modules = []
    not_configured_modules = []
    for name in apps.app_configs.keys():
        module_name = f'{name}.{EDA_MODULE_NAME}'
        try:
            edas_module = import_module(module_name)
            configured_modules.append(edas_module)
        except ImportError:
            not_configured_modules.append(module_name)

    logger.info(
        f'Registered Eda apps: {[module.__name__ for module in configured_modules]}.'
    )

    logger.info(f'Not registered Eda apps: {not_configured_modules}.')

    return configured_modules
