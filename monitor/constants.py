from integration.factory import get_integration_name, integrations
from monitor.laikaql.builder import APP_ALIASES
from monitor.laikaql.lo import SQL_TO_LO_MAPPING

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50
EMPTY_RESULTS = 'Healthy if no violations found'
RETURN_RESULTS = 'Healthy if monitor returns results'
WATCH = 'watch'
UNWATCH = 'unwatch'
INTEGRATION_DESCRIPTION = '(Integration)'
LAIKA_OBJECT_DESCRIPTION = '(Laika Object)'
LAIKA_APP_DESCRIPTION = '(App)'

INTEGRATION_SOURCES = [
    (f'{alias}', f'{get_integration_name(alias)} {INTEGRATION_DESCRIPTION}')
    for alias in integrations().keys()
]
LO_SOURCES = [
    (alias, f'{spec.display_name} {LAIKA_OBJECT_DESCRIPTION}')
    for alias, spec in SQL_TO_LO_MAPPING.items()
]
APP_SOURCES = [
    (f'app_{app}', f'{app.title()} {LAIKA_APP_DESCRIPTION}')
    for app in APP_ALIASES.keys()
]
LAIKA_SOURCES = APP_SOURCES + LO_SOURCES
SOURCE_SYSTEM_CHOICES = INTEGRATION_SOURCES + LAIKA_SOURCES
