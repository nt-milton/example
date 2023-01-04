from typing import Dict, Set
from unittest.mock import MagicMock


class MockRedis:
    def __init__(self, cache: Dict = {}):
        self.cache = cache
        self.values: Set = set()

    def smembers(self, alias: str):
        return self.cache.get(alias, [])

    def sadd(self, alias: str, *new_values):
        new_values_set = set(new_values)
        self.values.update(new_values_set)
        self.cache[alias] = self.values
        return len(new_values)

    def srem(self, alias: str, *delete_values):
        new_values_set = set(delete_values)
        self.cache[alias].difference_update(new_values_set)

    def connection_pool(self):
        return MagicMock()
