from integration.constants import ON_CREATE_PAYROLL_CONNECTION_ACCOUNT
from laika.edas import EdaRegistry

EdaRegistry.register_events(
    app=__package__, events=[ON_CREATE_PAYROLL_CONNECTION_ACCOUNT]
)
