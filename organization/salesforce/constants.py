from laika.settings import DJANGO_SETTINGS

# Post request params
sf_params = [
    'Account_ID_18_char__c',
    'Name',
    'Website',
    'Compliance_Architect__r',
    'Customer_Success_Manager__r',
    'Current_Contract_Start_Date_Auto__c',
    'Account_Status__c',
    'LastModifiedById',
]

# Name fields in Salesforce
ID_SALESFORCE_FIELD = 'Account_ID_18_char__c'
NAME_SALESFORCE_FIELD = 'Name'
WEBSITE_SALESFORCE_FIELD = 'Website'
COMPLIANCE_ARCHITECT_SALESFORCE_FIELD = 'Compliance_Architect__c'
COMPLIANCE_ARCHITECT_SALESFORCE_RELATION_FIELD = 'Compliance_Architect__r'
CUSTOMER_SUCCESS_MANAGER_SALESFORCE_FIELD = 'Customer_Success_Manager__c'
CUSTOMER_SUCCESS_MANAGER_SALESFORCE_RELATION_FIELD = 'Customer_Success_Manager__r'
CONTRACT_SIGN_DATE_SALESFORCE_FIELD = 'Current_Contract_Start_Date_Auto__c'
ACCOUNT_STATUS_FIELD = 'Account_Status__c'
LAST_MODIFIED_BY = 'LastModifiedById'

# Api Salesforce
SALESFORCE_API_USER = DJANGO_SETTINGS.get('SALESFORCE_API_USER')
SALESFORCE_API_USER_PASSWORD = DJANGO_SETTINGS.get('SALESFORCE_API_USER_PASSWORD')
INTEGRATION_SALESFORCE_CLIENT_ID = DJANGO_SETTINGS.get(
    'INTEGRATION_SALESFORCE_CLIENT_ID'
)
INTEGRATION_SALESFORCE_CONSUMER_SECRET = DJANGO_SETTINGS.get(
    'INTEGRATION_SALESFORCE_CONSUMER_SECRET'
)
INTEGRATION_SALESFORCE_AUTH_URL = DJANGO_SETTINGS.get('INTEGRATION_SALESFORCE_AUTH_URL')
SALESFORCE_API_KEY = DJANGO_SETTINGS.get('SALESFORCE_API_KEY')

#  States mapping
ACTIVE_TRIAL = 'Active Trial'
CUSTOMER = 'Customer'
STATES = {CUSTOMER: 'ONBOARDING', ACTIVE_TRIAL: 'TRIAL'}
SALESFORCE_STATES = [CUSTOMER, ACTIVE_TRIAL]
ACTIVE = 'ACTIVE'

# Custom Salesforce REST Endpoint
SALESFORCE_POLARIS_ENDPOINT_URL = '/services/apexrest/accounts/polaris'
SALESFORCE_USER_URL_API = '/services/data/v55.0/sobjects/User/'

# Salesforce Actions
UPDATING = 'updating'
CREATING = 'creating'
