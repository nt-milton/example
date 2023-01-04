from integration.azure_boards.constants import AZURE_BOARDS_SYSTEM
from objects.system_types import ChangeRequest

NO = 'NO'


def map_work_item_to_laika_object(work_item_record, connection_name):
    work_item = work_item_record.get('work_item')
    work_item_history = work_item_record.get('work_item_updates', {}).get('value', [])
    lo_change_request = ChangeRequest()
    lo_change_request.key = work_item.get('id', '')
    lo_change_request.title = work_item.get('fields', {}).get('System.Title', '')
    lo_change_request.description = work_item.get('fields', {}).get(
        'System.Description', ''
    )
    lo_change_request.issue_type = work_item.get('fields', {}).get(
        'System.WorkItemType', ''
    )
    lo_change_request.status = work_item.get('fields', {}).get('System.State', '')
    lo_change_request.project = work_item.get('fields', {}).get(
        'System.TeamProject', ''
    )
    lo_change_request.assignee = (
        work_item.get('fields', {}).get('System.AssignedTo', {}).get('displayName', '')
    )
    lo_change_request.reporter = (
        work_item.get('fields', {}).get('System.CreatedBy', {}).get('displayName', '')
    )
    lo_change_request.approver = NO
    lo_change_request.started = work_item.get('fields', {}).get(
        'Microsoft.VSTS.Common.ActivatedDate', ''
    )
    lo_change_request.transitions_history = work_item_history
    lo_change_request.ended = work_item.get('fields', {}).get(
        'Microsoft.VSTS.Common.ClosedDate', ''
    )
    lo_change_request.url = work_item.get('url', '')
    lo_change_request.source_system = AZURE_BOARDS_SYSTEM
    lo_change_request.connection_name = connection_name
    lo_change_request.epic = NO
    return lo_change_request.data()
