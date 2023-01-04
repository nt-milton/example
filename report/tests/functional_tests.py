import pytest

from report.models import Report
from report.tests.factory import (
    create_organization_logo,
    create_reports,
    create_template_with_content,
)
from report.tests.mutations import CREATE_REPORT, DELETE_REPORT
from report.tests.queries import GET_FILTER_GROUPS_REPORTS, GET_REPORTS


def _get_collection_reports(response):
    return response['data']['reports']['data']


@pytest.mark.functional(permissions=['report.view_report'])
def test_get_all_reports(graphql_client, graphql_organization):
    create_reports(graphql_organization)
    response = graphql_client.execute(
        GET_REPORTS, variables={'pagination': {'pageSize': 50, 'page': 1}}
    )
    collection = _get_collection_reports(response)

    assert len(collection) == 2
    assert collection[0]['displayId'] == 'CR-2'
    assert collection[0]['name'] == 'Test_Report_B'
    assert collection[0]['link']['isEnabled'] is True
    assert collection[0]['link']['isValid'] is True
    assert collection[0]['link']['isExpired'] is False


@pytest.mark.functional(permissions=['report.view_report'])
def test_get_all_reports_ordered(graphql_client, graphql_organization):
    create_reports(graphql_organization)
    response = graphql_client.execute(
        GET_REPORTS,
        variables={
            'orderBy': {'order': 'ascend', 'field': 'name'},
            'pagination': {'pageSize': 50, 'page': 1},
        },
    )
    collection = _get_collection_reports(response)

    assert len(collection) == 2
    assert collection[0]['displayId'] == 'CR-1'
    assert collection[0]['name'] == 'Test_Report_A'
    assert collection[0]['link']['isEnabled'] is False
    assert collection[0]['link']['isValid'] is False
    assert collection[0]['link']['isExpired'] is False


@pytest.mark.functional(permissions=['report.view_report'])
def test_resolve_report_sharing_active(graphql_client, graphql_organization):
    create_reports(graphql_organization)
    response = graphql_client.execute(
        GET_REPORTS,
        variables={
            'orderBy': {'order': 'ascend', 'field': 'name'},
            'pagination': {'pageSize': 50, 'page': 1},
            'filter': "{\"status\":\"active\"}",
        },
    )
    collection = _get_collection_reports(response)

    assert len(collection) == 1
    assert collection[0]['displayId'] == 'CR-2'
    assert collection[0]['name'] == 'Test_Report_B'
    assert collection[0]['link']['isEnabled'] is True
    assert collection[0]['link']['isValid'] is True
    assert collection[0]['link']['isExpired'] is False


@pytest.mark.functional(permissions=['report.view_report'])
def test_resolve_report_sharing_inactive(graphql_client, graphql_organization):
    create_reports(graphql_organization)
    response = graphql_client.execute(
        GET_REPORTS,
        variables={
            'orderBy': {'order': 'ascend', 'field': 'name'},
            'pagination': {'pageSize': 50, 'page': 1},
            'filter': "{\"sharing\":\"false\",\"archived\":false}",
        },
    )
    collection = _get_collection_reports(response)

    assert len(collection) == 2
    assert collection[0]['displayId'] == 'CR-1'
    assert collection[0]['name'] == 'Test_Report_A'


@pytest.mark.functional(permissions=['report.view_report'])
def test_resolve_report_days(graphql_client, graphql_organization):
    create_reports(graphql_organization)
    response = graphql_client.execute(
        GET_REPORTS,
        variables={
            'orderBy': {'order': 'ascend', 'field': 'name'},
            'pagination': {'pageSize': 50, 'page': 1},
            'filter': "{\"days\":\"last_seven_days\",\"archived\":false}",
        },
    )
    collection = _get_collection_reports(response)

    assert len(collection) == 2
    assert collection[0]['displayId'] == 'CR-1'
    assert collection[0]['name'] == 'Test_Report_A'


@pytest.mark.functional(permissions=['report.add_report'])
def test_create_report(graphql_client, graphql_organization):
    create_template_with_content(graphql_organization)
    create_organization_logo(graphql_organization)
    response = get_mutation_create_report_executed(graphql_client, 'Test Report')
    assert response['data']['createReport']['id'] == 1


@pytest.mark.functional(permissions=['report.add_report'])
def test_create_report_existing_name(graphql_client, graphql_organization):
    create_reports(graphql_organization)
    create_template_with_content(graphql_organization)
    name = 'Test_Last_A'
    response = get_mutation_create_report_executed(graphql_client, name)
    response2 = get_mutation_create_report_executed(graphql_client, name)
    assert response['data']['createReport']['id'] == 3
    assert response2['errors'][0]['message'] == f'Report "{name}" already exists.'


@pytest.mark.functional(permissions=['report.add_report'])
def test_create_report_with_long_name(graphql_client, graphql_organization):
    create_template_with_content(graphql_organization)
    name = '''
     Lorem ipsum dolor sit amet, consectetur adipiscing elit.
     Donec commodo sapien at lacus pulvinar, a gravida tellus vehicula.
     Cras sodales velit ac est pretium scelerisque.
     Curabitur venenatis fermentum erat.
     Pellentesque tellus nisi, porta in aliquet eget biam.
    '''
    response = get_mutation_create_report_executed(graphql_client, name)
    assert (
        response['errors'][0]['message']
        == 'Error creating the report. Name length max is 250.'
    )


@pytest.mark.functional(permissions=['report.add_report', 'report.delete_report'])
def test_soft_delete_report(graphql_client, graphql_organization):
    create_template_with_content(graphql_organization)
    name = 'report test name'
    get_mutation_create_report_executed(graphql_client, name)
    get_mutation_delete_report_executed(graphql_client, '1')
    report = Report.objects.get(id='1')
    expected_is_deleted = True
    assert report.is_deleted == expected_is_deleted
    assert 'Deleted #' in report.name


@pytest.mark.functional(permissions=['report.add_report', 'report.delete_report'])
def test_soft_delete_long_name_report(graphql_client, graphql_organization):
    create_template_with_content(graphql_organization)
    name = '''
Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Fusce aliquam eleifend lacus, a convallis mi dictum lobortis.
Vestibulum ac est malesuada, pulvinar ligula et, venenatis ipsum.
Nunc nisi felis, luctus sed tempus non, egestas ut turpis.
    '''
    get_mutation_create_report_executed(graphql_client, name)
    get_mutation_delete_report_executed(graphql_client, '1')
    report = Report.objects.get(id='1')
    expected_is_deleted = True
    assert report.is_deleted == expected_is_deleted
    assert '... - Deleted #' in report.name


@pytest.mark.functional(permissions=['report.add_report', 'report.delete_report'])
def test_restore_report(graphql_client, graphql_organization):
    create_template_with_content(graphql_organization)
    name = 'report test name'
    get_mutation_create_report_executed(graphql_client, name)
    get_mutation_restore_report_executed(graphql_client, '1')
    report = Report.objects.get(id='1')
    expected_is_deleted = False
    assert report.is_deleted == expected_is_deleted
    assert report.name == name


@pytest.mark.functional(permissions=['report.view_report'])
def test_resolve_filter_groups_reports(graphql_client):
    executed = graphql_client.execute(GET_FILTER_GROUPS_REPORTS)
    response = executed['data']['filterGroupsReports']

    assert response[0]['id'] == 'time'
    assert response[1]['id'] == 'status'


def get_mutation_create_report_executed(graphql_client, report_name):
    return graphql_client.execute(
        CREATE_REPORT, variables={'input': {'name': report_name}}
    )


def get_mutation_delete_report_executed(graphql_client, report_id):
    return graphql_client.execute(
        DELETE_REPORT, variables={'input': {'reportId': report_id, 'value': True}}
    )


def get_mutation_restore_report_executed(graphql_client, report_id):
    return graphql_client.execute(
        DELETE_REPORT, variables={'input': {'reportId': report_id, 'value': False}}
    )
