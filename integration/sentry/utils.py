from datetime import date
from typing import Generator, List, Optional, Union

from dateutil.parser import parse

from laika.utils.dates import str_date_to_date_formatted as format_date


def get_current_cursor_offset(current_url: Optional[str]) -> Union[int, None]:
    current_cursor = (
        current_url.split('&cursor=')[1]
        if current_url and '&cursor=' in current_url
        else None
    )
    if not current_cursor:
        return None
    return int(current_cursor.split(':')[1])


def has_reached_url_chunks_limit(current_url: Optional[str], chunks_limit: int) -> bool:
    url_row_offset: Union[int, None] = get_current_cursor_offset(current_url)
    if not url_row_offset:
        return True
    return url_row_offset >= chunks_limit


def get_mapped_projects(projects: Generator, organization: str) -> List:
    mapped_projects = []
    for project in projects:
        project_data = dict(
            id=project.get('id'),
            slug=project.get('slug'),
            name=project.get('name'),
            organization=organization,
        )
        mapped_projects.append(project_data)
    return mapped_projects


def next_has_results(link: str) -> bool:
    return 'results="true"' in link.split()[6]


def is_next_url(link: str) -> bool:
    return 'rel="next"' in link.split()[5]


def pagination_next_page(response):
    link = response.headers.get('Link')
    if link and is_next_url(link) and next_has_results(link):
        return link.split()[4][1:-2]
    else:
        return None


def can_continue_fetching(
    does_reached_chunk_limit: bool = True, current_next_page: Union[str, None] = None
) -> bool:
    return not does_reached_chunk_limit and current_next_page is not None


def get_event_formatted_date(current_date: str) -> date:
    return parse(current_date).date()


# Events are ordered by date, if last event is still on date range
# then the previous ones are also.
def are_all_events_within_date_range(
    selected_time_range: str, page_events: List
) -> bool:
    if not page_events:
        return False

    last_event = page_events[-1]['dateCreated']
    event_created_date = get_event_formatted_date(last_event)
    return event_created_date >= format_date(selected_time_range).date()


def extract_relevant_events(selected_time_range: str, current_events: List) -> List:
    if not current_events:
        return current_events

    reversed_events_page = reversed(current_events)
    selected_date = format_date(selected_time_range).date()
    for event in reversed_events_page:
        created_date = get_event_formatted_date(event.get('dateCreated'))
        if created_date < selected_date:
            current_events.pop()
        else:
            break

    return current_events
