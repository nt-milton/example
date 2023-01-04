import requests

from integration.log_utils import network_wait


def post(url, data=None, json=None, **kwargs):
    with network_wait():
        return requests.post(url, data, json, **kwargs)


def get(url, params=None, **kwargs):
    with network_wait():
        return requests.get(url, params, **kwargs)


Response = requests.Response
codes = requests.codes
