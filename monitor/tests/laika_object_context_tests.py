import pytest

from monitor.laikaql import build_raw_query
from monitor.laikaql.lo import (
    FALSE_CRITERIA,
    build_columns_for_spec,
    build_laika_object_query,
    build_raw_select_query,
)
from monitor.runner import build_unfiltered_query
from monitor.sqlutils import (
    _get_table_names,
    get_raw_selected_columns,
    replace_selected_columns,
)
from monitor.template import placeholders_from_template
from objects.system_types import (
    CONNECTION_NAME,
    SOURCE_SYSTEM,
    TEXT,
    USER,
    LOAttribute,
    ObjectTypeSpec,
    SystemType,
    resolve_laika_object_type,
)
from organization.tests import create_organization

KEYWORD_USER = 'user'


class TestingSystemType(SystemType):
    id = LOAttribute('Id', TEXT)
    first_name = LOAttribute('First Name', TEXT)
    last_name = LOAttribute('Last Name', TEXT)
    email = LOAttribute('Email', TEXT)
    is_admin = LOAttribute('Is Admin', TEXT)
    title = LOAttribute('Title', TEXT)
    organization_name = LOAttribute('Organization Name', TEXT)
    roles = LOAttribute('Roles', TEXT)
    groups = LOAttribute('Groups', TEXT)
    applications = LOAttribute('Applications', TEXT)
    mfa_enabled = LOAttribute('Mfa Enabled', TEXT)
    mfa_enforced = LOAttribute('Mfa Enforced', TEXT)
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)


TESTING_SYSTEM_TYPE_SPEC = ObjectTypeSpec(
    display_name='Testing System Type',
    type='testing_system_type',
    icon='None',
    color='None',
    attributes=TestingSystemType.attributes(),
)


def test_build_raw_select_query_without_conditions():
    columns = ['username', 'mfa_enabled']
    raw_select_query = build_raw_select_query(columns, 'lo_user')
    expected = 'SELECT username, mfa_enabled FROM lo_user'
    assert raw_select_query == expected


def test_build_raw_select_query_with_conditions():
    columns = ['username', 'mfa_enabled']
    conditions = 'source = "Source"'
    raw_select_query = build_raw_select_query(columns, 'lo_user', conditions)
    expected = 'SELECT username, mfa_enabled FROM lo_user WHERE source = "Source"'
    assert raw_select_query == expected


@pytest.mark.parametrize(
    'query, tables',
    [
        pytest.param('SELECT * FROM "lo_user";', ['lo_user'], id='With  Keyword'),
        pytest.param('SELECT * FROM anything;', ['anything'], id='With  Identifier'),
        pytest.param(
            'SELECT * FROM table_1, table_2;',
            ['table_1', 'table_2'],
            id='With Identifier List',
        ),
        pytest.param(
            'SELECT * FROM "user", table_2;',
            [KEYWORD_USER, 'table_2'],
            id='With keyword and Identifier',
        ),
        pytest.param(
            'SELECT * FROM "user" JOIN devices', [KEYWORD_USER, 'devices'], id='Join'
        ),
        pytest.param(
            'SELECT * FROM "user" INNER JOIN devices',
            [KEYWORD_USER, 'devices'],
            id='Inner Join',
        ),
    ],
)
def test_get_selected_tables_with_altered_join(query, tables):
    selected_tables = _get_table_names(query)
    assert selected_tables == tables


@pytest.mark.functional
def test_build_raw_query_builder_for_spec_without_laika_object_type():
    organization = create_organization(name='Test')
    query = build_laika_object_query(TESTING_SYSTEM_TYPE_SPEC)(organization)
    assert FALSE_CRITERIA in query


@pytest.mark.functional
def test_build_raw_query_builder_for_spec_with_laika_object_type():
    organization = create_organization(name='Test')
    resolve_laika_object_type(organization, TESTING_SYSTEM_TYPE_SPEC)
    query_builder = build_laika_object_query(TESTING_SYSTEM_TYPE_SPEC)
    raw_query_for_spec = query_builder(organization)
    assert raw_query_for_spec == SYSTEM_TYPE_QUERY_EXPECTED


def test_build_columns_for_spec():
    columns_for_spec = list(build_columns_for_spec(TESTING_SYSTEM_TYPE_SPEC))
    expected_columns = [
        "data->>'Id' \"id\"",
        "data->>'First Name' \"first_name\"",
        "data->>'Last Name' \"last_name\"",
        "data->>'Email' \"email\"",
        "data->>'Is Admin' \"is_admin\"",
        "data->>'Title' \"title\"",
        "data->>'Organization Name' \"organization_name\"",
        "data->>'Roles' \"roles\"",
        "data->>'Groups' \"groups\"",
        "data->>'Applications' \"applications\"",
        "data->>'Mfa Enabled' \"mfa_enabled\"",
        "data->>'Mfa Enforced' \"mfa_enforced\"",
        "data->>'Source System' \"source_system\"",
        "data->>'Connection Name' \"connection_name\"",
    ]
    assert columns_for_spec == expected_columns


SYSTEM_TYPE_ID = 1
SYSTEM_TYPE_QUERY_EXPECTED = (
    "SELECT "
    "id as lo_id, "
    "data->>'Id' \"id\", "
    "data->>'First Name' \"first_name\", "
    "data->>'Last Name' \"last_name\", "
    "data->>'Email' \"email\", "
    "data->>'Is Admin' \"is_admin\", "
    "data->>'Title' \"title\", "
    "data->>'Organization Name' \"organization_name\", "
    "data->>'Roles' \"roles\", "
    "data->>'Groups' \"groups\", "
    "data->>'Applications' \"applications\", "
    "data->>'Mfa Enabled' \"mfa_enabled\", "
    "data->>'Mfa Enforced' \"mfa_enforced\", "
    "data->>'Source System' \"source_system\", "
    "data->>'Connection Name' \"connection_name\" "
    "FROM objects_laikaobject "
    f"WHERE object_type_id={SYSTEM_TYPE_ID} AND deleted_at is null"
)
REPLACED_SYSTEM_TYPE_QUERY_EXPECTED = f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS lo_users'


params_for_query_building_tests = [
    (
        'SELECT id, name, column FROM lo_users WHERE id=1;',
        'SELECT id, name, column '
        f'FROM {REPLACED_SYSTEM_TYPE_QUERY_EXPECTED} '
        'WHERE id=1;',
    ),
    (
        'SELECT id FROM lo_users WHERE id=1;',
        f'SELECT id FROM {REPLACED_SYSTEM_TYPE_QUERY_EXPECTED} WHERE id=1;',
    ),
    (
        'SELECT id FROM lo_users, lo_users WHERE id=1;',
        'SELECT id FROM '
        f'{REPLACED_SYSTEM_TYPE_QUERY_EXPECTED}, '
        f'{REPLACED_SYSTEM_TYPE_QUERY_EXPECTED} '
        'WHERE id=1;',
    ),
    (
        'SELECT id, name, column FROM lo_users, lo_users WHERE id=1;',
        'SELECT id, name, column FROM '
        f'{REPLACED_SYSTEM_TYPE_QUERY_EXPECTED}, '
        f'{REPLACED_SYSTEM_TYPE_QUERY_EXPECTED} '
        'WHERE id=1;',
    ),
    (
        'SELECT id FROM lo_users INNER JOIN lo_users WHERE id=1;',
        'SELECT id '
        f'FROM {REPLACED_SYSTEM_TYPE_QUERY_EXPECTED} '
        f'INNER JOIN {REPLACED_SYSTEM_TYPE_QUERY_EXPECTED} '
        'WHERE id=1;',
    ),
    (
        'SELECT id, name, column FROM lo_users INNER JOIN lo_users WHERE id=1;',
        'SELECT id, name, column '
        f'FROM {REPLACED_SYSTEM_TYPE_QUERY_EXPECTED} '
        f'INNER JOIN {REPLACED_SYSTEM_TYPE_QUERY_EXPECTED} '
        'WHERE id=1;',
    ),
    (
        'SELECT u.id FROM lo_users u WHERE id=1;',
        f'SELECT u.id FROM ({SYSTEM_TYPE_QUERY_EXPECTED}) AS u WHERE id=1;',
    ),
    (
        'SELECT u.id FROM lo_users as u WHERE id=1;',
        f'SELECT u.id FROM ({SYSTEM_TYPE_QUERY_EXPECTED}) AS u WHERE id=1;',
    ),
    (
        'SELECT u.id FROM lo_users as "u" WHERE id=1;',
        f'SELECT u.id FROM ({SYSTEM_TYPE_QUERY_EXPECTED}) AS u WHERE id=1;',
    ),
    (
        'SELECT u.id, u.name, u.column FROM lo_users u WHERE id=1;',
        'SELECT u.id, u.name, u.column '
        f'FROM ({SYSTEM_TYPE_QUERY_EXPECTED}) AS u '
        'WHERE id=1;',
    ),
    (
        'SELECT u.id, u.name, u.column FROM lo_users "u" WHERE id=1;',
        'SELECT u.id, u.name, u.column '
        f'FROM ({SYSTEM_TYPE_QUERY_EXPECTED}) AS u '
        'WHERE id=1;',
    ),
    (
        'SELECT u.id FROM lo_users u, lo_users v WHERE id=1;',
        'SELECT u.id FROM '
        f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS u, '
        f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS v '
        'WHERE id=1;',
    ),
    (
        'SELECT u.id FROM lo_users "u", lo_users "v" WHERE id=1;',
        'SELECT u.id FROM '
        f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS u, '
        f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS v '
        'WHERE id=1;',
    ),
    (
        'SELECT v.id FROM lo_users u, lo_users v WHERE id=1;',
        'SELECT v.id FROM '
        f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS u, '
        f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS v '
        'WHERE id=1;',
    ),
    (
        'SELECT u.id, v.id FROM lo_users u, lo_users v WHERE id=1;',
        'SELECT u.id, v.id FROM '
        f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS u, '
        f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS v '
        'WHERE id=1;',
    ),
    (
        'SELECT u.id, v.id FROM lo_users "u", lo_users "v" WHERE id=1;',
        'SELECT u.id, v.id FROM '
        f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS u, '
        f'({SYSTEM_TYPE_QUERY_EXPECTED}) AS v '
        'WHERE id=1;',
    ),
    (
        'SELECT u.id FROM lo_users as u INNER JOIN lo_users as v WHERE id=1;',
        'SELECT u.id '
        f'FROM ({SYSTEM_TYPE_QUERY_EXPECTED}) AS u '
        f'INNER JOIN ({SYSTEM_TYPE_QUERY_EXPECTED}) AS v '
        'WHERE id=1;',
    ),
    (
        'SELECT u.id, v.id FROM lo_users as u INNER JOIN lo_users as v WHERE id=1;',
        'SELECT u.id, v.id '
        f'FROM ({SYSTEM_TYPE_QUERY_EXPECTED}) AS u '
        f'INNER JOIN ({SYSTEM_TYPE_QUERY_EXPECTED}) AS v '
        'WHERE id=1;',
    ),
    (
        'SELECT u.id FROM lo_users as "u" INNER JOIN lo_users as "v" WHERE id=1;',
        'SELECT u.id '
        f'FROM ({SYSTEM_TYPE_QUERY_EXPECTED}) AS u '
        f'INNER JOIN ({SYSTEM_TYPE_QUERY_EXPECTED}) AS v '
        'WHERE id=1;',
    ),
    (
        'SELECT u.id, v.id FROM lo_users as "u" INNER JOIN lo_users as "v" WHERE id=1;',
        'SELECT u.id, v.id '
        f'FROM ({SYSTEM_TYPE_QUERY_EXPECTED}) AS u '
        f'INNER JOIN ({SYSTEM_TYPE_QUERY_EXPECTED}) AS v '
        'WHERE id=1;',
    ),
]


@pytest.mark.functional
@pytest.mark.parametrize('query, expected', params_for_query_building_tests)
def test_build_query_for_organization_monitor(query, expected):
    organization = create_organization(name='organization_test')
    resolve_laika_object_type(organization, USER)
    raw_query = build_raw_query(organization, query)
    assert raw_query == expected


@pytest.mark.parametrize(
    'query',
    [
        pytest.param('select * from x where a=b;'),
        pytest.param('select * from x where a=b LIMIT 20'),
        pytest.param('select * from x '),
    ],
)
def test_unfiltered_query(query):
    expected = 'select * from x limit 10'
    assert build_unfiltered_query(query, 10) == expected


def test_unfiltered_query_keep_nested():
    query = 'select * from (select * from c where d=e) where a=b'
    expected = 'select * from (select * from c where d=e) limit 10'
    assert build_unfiltered_query(query, 10) == expected


LAIKA_APP_DOMAIN = 'app.heylaika.com'
FIX_ME_LINKS_PARAMS = [
    (LAIKA_APP_DOMAIN, []),
    (f'{LAIKA_APP_DOMAIN}/$t.c1', ['$t.c1']),
    (f'{LAIKA_APP_DOMAIN}/$t.c1/$t.c2', ['$t.c1', '$t.c2']),
    (f'{LAIKA_APP_DOMAIN}/$t.c1/$t.c2/$t.c3', ['$t.c1', '$t.c2', '$t.c3']),
    (
        f'{LAIKA_APP_DOMAIN}/$table.column_1/$table.column_2',
        ['$table.column_1', '$table.column_2'],
    ),
]


@pytest.mark.parametrize('link, expected', FIX_ME_LINKS_PARAMS)
def test_get_variables_from_fix_me_link(link, expected):
    got = placeholders_from_template(link)
    assert got == expected


GET_RAW_SELECTED_COLUMN_PARAMS = [
    ('select * from users', '*'),
    ('select c1 from users', 'c1'),
    ('select c1, c2 from users', 'c1, c2'),
    ('select c1 as x, c2 as y from users', 'c1 as x, c2 as y'),
    ('select u.c1, u.c2 from users as u', 'u.c1, u.c2'),
    ('select u.c1 as x, u.c2 as y from users as u', 'u.c1 as x, u.c2 as y'),
]


@pytest.mark.parametrize('query, expected', GET_RAW_SELECTED_COLUMN_PARAMS)
def test_get_raw_selected_columns(query, expected):
    got = get_raw_selected_columns(query)
    assert got == expected


REPLACE_SELECTED_COLUMNS_PARAMS = [
    ('select * from users', 'replacement', 'select replacement from users'),
    ('select c1 from users', 'c2', 'select c2 from users'),
    ('select c1, c2 from users', 'c1, c2, c3', 'select c1, c2, c3 from users'),
    (
        'select c1 as x, c2 as y from users',
        'c1 as x',
        'select c1 as x from users',
    ),
    (
        'select u.c1, u.c2 from users as u',
        'column_1 as x',
        'select column_1 as x from users as u',
    ),
    (
        'select u.c1 as x, u.c2 as y from users as u',
        'u.column_1 as x',
        'select u.column_1 as x from users as u',
    ),
]


@pytest.mark.parametrize(
    'query, replacement, expected', REPLACE_SELECTED_COLUMNS_PARAMS
)
def test_replace_selected_columns_params(query, replacement, expected):
    got = replace_selected_columns(query, replacement)
    assert got == expected
