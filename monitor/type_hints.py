from typing import Callable

from monitor.models import OrganizationMonitor
from monitor.result import Result
from organization.models import Organization

QueryRunner = Callable[[OrganizationMonitor], Result]

QueryBuilder = Callable[[Organization], str]
