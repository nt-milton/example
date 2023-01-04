import json
import re
from pathlib import Path
from typing import Final
from urllib.parse import SplitResult, parse_qs
from uuid import uuid4

from httmock import HTTMock, response, urlmatch
from requests.models import PreparedRequest

BASE_PATH = path = Path(__file__).parent
URL: Final = 'api.checkr-staging.com'
headers = {'content-type': 'application/json'}


def generate_candidates(per_page: int, page: int, amount: int):
    res_path = BASE_PATH / 'candidates.res.json'
    with open(res_path, 'r') as json_file:
        content = json.loads(json_file.read())
    base_candidate = content['data'][0]
    generate_amount = per_page
    overflow = amount - per_page * page
    if overflow < 0:
        generate_amount = per_page + overflow

    candidates = []
    for _ in range(generate_amount):
        new_candidate = base_candidate.copy()
        new_candidate['id'] = uuid4().hex[:-8]
        candidates.append(new_candidate)

    next_href = None
    previous_href = None
    base_url = f'https://{URL}/v1/candidates'
    base_url += (
        '?page={}&per_page=25&order_by=created_at' + '&order=asc&partner_owned=false'
    )
    if per_page * page < amount:
        next_href = base_url.format(page + 1)
    if page > 1:
        previous_href = base_url.format(page - 1)
    return candidates, next_href, previous_href


def fake_checkr_api(candidates=-1):
    """Intercept checkr calls"""
    return HTTMock(checkr_handler(candidates))


def handle_candidates(request: PreparedRequest, url: SplitResult, amount: int):
    if amount == -1:
        res_path = BASE_PATH / 'candidates.res.json'
        with open(res_path, 'r') as json_file:
            content = json.loads(json_file.read())
    else:
        query_data = parse_qs(url.query)
        per_page = int(query_data.get('per_page', ['25'])[0])
        page = int(query_data.get('page', ['1'])[0])
        candidate_list, next_href, previous_href = generate_candidates(
            per_page, page, amount
        )

        content = {
            'data': candidate_list,
            "object": "list",
            "next_href": next_href,
            "previous_href": previous_href,
            "count": amount,
        }
    return response(
        status_code=200,
        content=content,
        headers=headers,
        request=request,
    )


def checkr_handler(candidates: int):
    regex = '/v1/(\\w+)/?((([a-f]|\\d)+)?/?)?$'

    methods_file_name: dict = {
        'POST': {
            'candidates': 'create_candidates.res.json',
            'invitations': 'send_invitation.res.json',
        },
        'GET': {
            'account': 'account_details.res.json',
            'invitations': 'invitations.res.json',
            'nodes': 'nodes.res.json',
            'packages': 'packages.res.json',
        },
    }

    @urlmatch(netloc=URL)
    def response_handler(url: SplitResult, request: PreparedRequest):
        if url.path == '/oauth/tokens':
            return request_api_endpoints(request, 'auth.res.json')

        v1_api_match = re.match(regex, url.path)
        if v1_api_match is not None:
            resource = v1_api_match.group(1)
            resource_id = v1_api_match.group(3)

        if resource == 'candidates' and request.method == 'GET':
            return handle_candidates(request, url, candidates)
        if resource == 'reports' and resource_id is not None:
            return request_api_endpoints(request, f'reports.res.{resource_id}.json')
        else:
            file_name = methods_file_name.get(request.method, {}).get(resource)
            if file_name:
                return request_api_endpoints(request, file_name)

        return response(
            status_code=500,
            content={'error': 'Internal Server Error'},
            headers=headers,
            request=request,
        )

    return response_handler


def request_api_endpoints(request: PreparedRequest, file_name: str):
    res_path = BASE_PATH / file_name
    with open(res_path, 'r') as json_file:
        content = json.loads(json_file.read())
    return response(
        status_code=200,
        content=content,
        headers=headers,
        request=request,
    )
