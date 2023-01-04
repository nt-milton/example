from typing import Any

import monitor.laika_context
import monitor.steampipe
from monitor.models import MonitorRunnerType

RUNNER_TYPES = {
    MonitorRunnerType.LAIKA_CONTEXT: monitor.laika_context,
    MonitorRunnerType.ON_DEMAND: monitor.steampipe,
}


def get_monitor_runner(runner_type: str) -> Any:
    runner = RUNNER_TYPES.get(runner_type)
    if not runner:
        raise ValueError(f'Unexpected runner: {runner_type}')
    return runner
