from dataclasses import dataclass

from laika.utils.schema_builder.types.base_field import SchemaType
from laika.utils.schema_builder.types.boolean_field import BooleanFieldType
from laika.utils.schema_builder.types.date_field import DateFieldType
from laika.utils.schema_builder.types.email_field import EmailFieldType
from laika.utils.schema_builder.types.single_select_field import SingleSelectField
from laika.utils.schema_builder.types.text_field import TextFieldType
from population.population_builder.types import TextFieldLaikaSourceType


@dataclass
class PopulationSchemaType(SchemaType):
    search_field: str


EMPLOYEE_NAME = 'Employee Name'
CURRENT_EMPLOYEES = 'Current Employees'
TERMINATED_EMPLOYEES = 'Terminated Employees'

POPULATION_EXAMPLE_DATE = 'Example: 11/29/2021'
POPULATION_4_EXAMPLE_DATE = 'Example: 06/10/2022'

POPULATION_1_CURRENT_EMPLOYEES_SCHEMA = PopulationSchemaType(
    sheet_name=CURRENT_EMPLOYEES,
    header_title=CURRENT_EMPLOYEES,
    fields=[
        TextFieldType(
            name=EMPLOYEE_NAME,
            required=True,
            instructions='Example: First and Last Name of Employee, e.g. John Doe',
        ),
        EmailFieldType(
            name='Employee Email',
            required=True,
            instructions='Example: Company email of Employee',
        ),
        TextFieldType(
            name='Job Title',
            required=True,
            instructions=(
                'Example: System Engineer, Information Security Officer, Developer'
            ),
        ),
        DateFieldType(
            name='Hire Date', required=True, instructions=POPULATION_EXAMPLE_DATE
        ),
        BooleanFieldType(
            name='Contractor',
            required=False,
            instructions=(
                'Identifying employees as contractors can help prevent additional'
                ' follow-up. Please identify as Yes/No below if applicable'
            ),
        ),
        TextFieldType(
            name='Location',
            required=False,
            instructions=(
                'If anyone supporting the service is outside of the USA, please'
                ' populate the location/country below'
            ),
        ),
    ],
    search_field=EMPLOYEE_NAME,
)
POPULATION_2_TERMINATED_EMPLOYEES_SCHEMA = PopulationSchemaType(
    sheet_name=TERMINATED_EMPLOYEES,
    header_title=TERMINATED_EMPLOYEES,
    fields=[
        TextFieldType(
            name=EMPLOYEE_NAME,
            required=True,
            instructions='Example: First and Last Name of Employee, e.g. John Doe',
        ),
        EmailFieldType(
            name='Employee Email',
            required=True,
            instructions='Example: Company email of Employee',
        ),
        TextFieldType(
            name='Job Title',
            required=True,
            instructions=(
                'Example: System Engineer, Information Security Officer, Developer'
            ),
        ),
        DateFieldType(
            name='Termination Date', required=True, instructions=POPULATION_EXAMPLE_DATE
        ),
        BooleanFieldType(
            name='Contractor',
            required=False,
            instructions=(
                'Identifying employees as contractors can help prevent additional'
                ' follow-up. Please identify as Yes/No below if applicable'
            ),
        ),
    ],
    search_field=EMPLOYEE_NAME,
)
POPULATION_3_CRITICAL_VENDORS_SCHEMA = PopulationSchemaType(
    sheet_name='Critical Vendors',
    header_title='Critical Vendors',
    fields=[
        TextFieldType(name='Vendor Name', required=True, instructions='Example: AWS'),
        SingleSelectField(
            name='Criticality',
            required=True,
            options=['Low', 'Medium', 'High', 'Critical'],
            instructions='Example: Critical, High, Medium, Low',
        ),
    ],
    search_field='Vendor Name',
)
POPULATION_4_SOFTWARE_INFRASTRUCTURE_PRODUCTION_CHANGES_SCHEMA = PopulationSchemaType(
    sheet_name='Software and Infrastructure',
    header_title='Software and Infrastructure Production Changes',
    fields=[
        TextFieldType(
            name='Ticket ID', required=True, instructions='Example: 456-PROD'
        ),
        TextFieldType(
            name='Ticket Name',
            required=True,
            instructions='Example: Production Code Change UI Update',
        ),
        DateFieldType(
            name='Production Merge Date',
            required=True,
            instructions=POPULATION_4_EXAMPLE_DATE,
        ),
        TextFieldType(
            name='Change Type',
            required=True,
            instructions='Example: Software/Infrastructure',
        ),
        TextFieldType(
            name='Repository',
            required=True,
            instructions='Example: (Dev/Production/Test) If applicable',
        ),
        TextFieldType(
            name='Change Category',
            required=False,
            instructions=(
                'Example: Emergency, Standard, Blanket Approval (Business as Usual)'
            ),
        ),
        DateFieldType(
            name='Date QA Testing Completed',
            required=False,
            instructions=POPULATION_4_EXAMPLE_DATE,
        ),
        DateFieldType(
            name='Date Approved to Production',
            required=False,
            instructions=POPULATION_4_EXAMPLE_DATE,
        ),
    ],
    search_field='Ticket Name',
)
POPULATION_5_SECURITY_EVENTS_SCHEMA = PopulationSchemaType(
    sheet_name='Security Events',
    header_title='Security Events',
    fields=[
        TextFieldType(name='ID', required=True, instructions='Example: SEC-1'),
        TextFieldType(
            name='Name', required=True, instructions='Example: Brute Force SSH Attack'
        ),
        DateFieldType(
            name='Date Opened', required=True, instructions=POPULATION_EXAMPLE_DATE
        ),
        DateFieldType(
            name='Date Closed', required=True, instructions=POPULATION_EXAMPLE_DATE
        ),
        TextFieldType(
            name='Details of Event',
            required=True,
            instructions='Provide a short description of the event if applicable',
        ),
        SingleSelectField(
            name='Criticality',
            required=True,
            options=['Low', 'Medium', 'High', 'Highest'],
            instructions='Example: High',
        ),
    ],
    search_field='Name',
)
POPULATION_6_CUSTOMER_DATA_DELETIONS_SCHEMA = PopulationSchemaType(
    sheet_name='Customer Data Deletions',
    header_title='Customer Data Deletions',
    fields=[
        TextFieldType(
            name='Customer Name', required=True, instructions='Example: SEC-1'
        ),
        TextFieldType(name='Ticket ID', required=True, instructions='Example: DEL-1'),
        TextFieldType(
            name='Description',
            required=True,
            instructions='Example: Delete data for XYZ',
        ),
        DateFieldType(
            name='Date Data Purged or Removed',
            required=True,
            instructions=POPULATION_EXAMPLE_DATE,
        ),
        DateFieldType(
            name='Date Customer Left the Service',
            required=True,
            instructions=POPULATION_EXAMPLE_DATE,
        ),
        TextFieldType(
            name='Retention Period',
            required=True,
            instructions='Example: 30 days after customer leaves the service',
        ),
    ],
    search_field='Customer Name',
)
POPULATION_7_SECURITY_INCIDENTS_SCHEMA = PopulationSchemaType(
    sheet_name='Security Incidents',
    header_title='Security Incidents',
    fields=[
        TextFieldType(name='ID', required=True, instructions='Example: Incident-1'),
        TextFieldType(name='Name', required=True, instructions='Example: Data Breach'),
        DateFieldType(
            name='Date Opened', required=True, instructions=POPULATION_EXAMPLE_DATE
        ),
        DateFieldType(
            name='Date Closed', required=True, instructions=POPULATION_EXAMPLE_DATE
        ),
        TextFieldType(
            name='Details of Incident',
            required=True,
            instructions='Short description of incident that took place',
        ),
        SingleSelectField(
            name='Criticality',
            required=True,
            options=['Low', 'Medium', 'High', 'Highest'],
            instructions='Example: Critical, High',
        ),
    ],
    search_field='Name',
)

POPULATION_SCHEMAS = {
    'POP-1': POPULATION_1_CURRENT_EMPLOYEES_SCHEMA,
    'POP-2': POPULATION_2_TERMINATED_EMPLOYEES_SCHEMA,
    'POP-3': POPULATION_3_CRITICAL_VENDORS_SCHEMA,
    'POP-4': POPULATION_4_SOFTWARE_INFRASTRUCTURE_PRODUCTION_CHANGES_SCHEMA,
    'POP-5': POPULATION_5_SECURITY_EVENTS_SCHEMA,
    'POP-6': POPULATION_6_CUSTOMER_DATA_DELETIONS_SCHEMA,
    'POP-7': POPULATION_7_SECURITY_INCIDENTS_SCHEMA,
}

POPULATION_1_CURRENT_EMPLOYEES_PEOPLE_SOURCE_SCHEMA = PopulationSchemaType(
    sheet_name=CURRENT_EMPLOYEES,
    header_title=CURRENT_EMPLOYEES,
    fields=[
        TextFieldLaikaSourceType(
            name='Name',
            required=True,
        ),
        EmailFieldType(
            name='Email',
            required=True,
        ),
        TextFieldLaikaSourceType(
            name='Title',
            required=True,
        ),
        DateFieldType(name='Start Date', required=True),
        TextFieldLaikaSourceType(
            name='Employment Type',
            required=False,
        ),
    ],
    search_field='Name',
)

POPULATION_2_TERMINATED_EMPLOYEES_PEOPLE_SOURCE_SCHEMA = PopulationSchemaType(
    sheet_name=TERMINATED_EMPLOYEES,
    header_title=TERMINATED_EMPLOYEES,
    fields=[
        TextFieldLaikaSourceType(
            name='Name',
            required=True,
        ),
        EmailFieldType(
            name='Email',
            required=True,
        ),
        TextFieldLaikaSourceType(
            name='Title',
            required=True,
        ),
        DateFieldType(name='End Date', required=True),
        TextFieldLaikaSourceType(
            name='Employment Type',
            required=False,
        ),
    ],
    search_field='Name',
)

POPULATION_LAIKA_SOURCE_SCHEMAS = {
    'POP-1': POPULATION_1_CURRENT_EMPLOYEES_PEOPLE_SOURCE_SCHEMA,
    'POP-2': POPULATION_2_TERMINATED_EMPLOYEES_PEOPLE_SOURCE_SCHEMA,
}
