import dataclasses
import json
from typing import Any, List, Optional

from django.core.serializers.json import DjangoJSONEncoder

from monitor.models import MonitorHealthCondition, MonitorInstanceStatus

HEALTHY = MonitorInstanceStatus.HEALTHY
TRIGGERED = MonitorInstanceStatus.TRIGGERED
CONNECTION_ERROR = MonitorInstanceStatus.CONNECTION_ERROR


@dataclasses.dataclass
class Result:
    columns: List[str]
    data: List[List[Any]]
    error: Optional[str] = None
    variables: List[dict] = dataclasses.field(default_factory=list)
    excluded_results: dict = dataclasses.field(default_factory=dict)

    @staticmethod
    def from_error(error: str):
        return Result(columns=[], data=[], error=error)

    def status(self, health_condition: str) -> str:
        return_result = MonitorHealthCondition.RETURN_RESULTS
        if not self.columns or self.error:
            return CONNECTION_ERROR
        empty = not self.data
        triggered = empty if health_condition == return_result else not empty
        return TRIGGERED if triggered else HEALTHY

    def to_json(self) -> Any:
        json_result = DjangoJSONEncoder().encode(self.serialize())
        return json.loads(json_result)

    def serialize(self) -> dict:
        result = self.__dict__.copy()
        if not result['error']:
            del result['error']
        if not result['variables']:
            del result['variables']
        if not result['excluded_results']:
            del result['excluded_results']
        return result


class AggregateResult(Result):
    def __init__(self, results: List[Result]):
        self.results = results
        columns, data = self.aggregate()
        super().__init__(columns=columns, data=data)

    def status(self, health_condition: str) -> str:
        statuses = [result.status(health_condition) for result in self.results]
        for status in [TRIGGERED, HEALTHY]:
            if status in statuses:
                return status
        return CONNECTION_ERROR

    def aggregate(self) -> tuple:
        columns = self.results[0].columns if len(self.results) > 0 else []
        data = []
        for result in self.results:
            data.extend(result.data)
        return columns, data

    def serialize(self) -> dict:
        result = super().serialize()
        del result['results']
        return result
