import logging

import pytest
from django.contrib.admin import AdminSite
from django.core.exceptions import ValidationError

from blueprint.admin.page import BlueprintPageAdmin
from blueprint.choices import BlueprintPage
from blueprint.models.page import Page
from user.tests import create_user

logger = logging.getLogger(__name__)


class MockRequest(object):
    def __init__(self, user=None):
        self.user = user


@pytest.fixture
def staff_user_test(graphql_organization):
    return create_user(
        graphql_organization,
        email='test@heylaika.com',
        role='OrganizationAdmin',
        first_name='Test',
    )


@pytest.mark.functional
def test_get_form_empty_obj(staff_user_test):
    page_admin = BlueprintPageAdmin(model=Page, admin_site=AdminSite())
    form = page_admin.get_form(request=MockRequest(user=staff_user_test))

    assert form.base_fields['created_by']
    assert form.base_fields['created_by'].disabled is True
    assert form.base_fields['created_by'].initial == staff_user_test


@pytest.mark.functional
def test_save_model_raises_airtable_link(staff_user_test):
    obj = Page(name=BlueprintPage.GLOBAL)

    with pytest.raises(ValidationError) as excinfo:
        obj.clean_fields()

    assert 'Airtable Link and api key are required for Global Blueprint' in str(
        excinfo.value
    )


@pytest.mark.functional
def test_clean_fields_raises_single_blueprints(staff_user_test):
    obj = Page(
        name=BlueprintPage.CONTROLS,
        airtable_link='https//fake-link.com',
        airtable_api_key='fake-api-key',
    )

    with pytest.raises(ValidationError) as excinfo:
        obj.clean_fields()

    assert (
        'You are not allowed to add single blueprints. '
        'Please add or edit the Global Blueprint to reflect all '
        'changes.'
        in str(excinfo.value)
    )


@pytest.mark.functional
def test_save_model_success(staff_user_test):
    request = MockRequest(user=staff_user_test)
    page_admin = BlueprintPageAdmin(model=Page, admin_site=AdminSite())
    form = page_admin.get_form(request)

    obj = Page(
        name=BlueprintPage.GLOBAL,
        airtable_link='https//fake-link.com',
        airtable_api_key='fake-api-key',
    )

    page_admin.save_model(request, obj, form, None)

    blueprint_pages = Page.objects.all()

    assert len(blueprint_pages) == len(BlueprintPage.values)
    for page in blueprint_pages:
        assert page.airtable_link == obj.airtable_link
        assert page.airtable_api_key == obj.airtable_api_key
        assert page.name in BlueprintPage.values
