from typing import Any, List, Literal, TypedDict, Union


class Report(TypedDict):
    id: str
    candidate_id: str
    package: str
    status: Literal[
        'clear',
        'pending',
        'consider',
        'complete',
        'suspended',
        'dispute',
    ]
    result: Literal['clear', 'consider']
    created_at: str
    estimated_completion_time: str


class Candidate(TypedDict):
    id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    report_ids: List[str]
    reports: List[Report]


class Invitation(TypedDict):
    id: str
    status: Literal['pending', 'completed', 'expired']
    uri: str
    invitation_url: str
    completed_at: str
    deleted_at: str
    package: str
    created_at: str
    expires_at: str
    tags: Any
    object: str
    candidate_id: str
    report_id: str


class PaginatedResponse(TypedDict):
    data: List[Union[Candidate, Invitation]]
    object: str
    next_href: str
    previous_href: str
    count: int
