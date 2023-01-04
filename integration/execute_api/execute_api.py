import abc
from typing import Dict

from integration.models import ConnectionAccount


class ExecuteAPIInterface:
    @abc.abstractmethod
    def execute(
        self, endpoint: str, connection_account: ConnectionAccount, **kwargs: Dict
    ):
        """Call api endpoint"""
        raise NotImplementedError
