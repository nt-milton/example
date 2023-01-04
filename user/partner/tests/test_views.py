import pytest
from django.test import Client

from user.partner.auth import PARTNER_LOGIN
from user.partner.tests.test_auth import partner_user, pentest_user
from user.partner.views import PARTNER_HOME

USERNAME = 'danny'
TEST_PASS = 'chacon'
PARTNER_AUTH = '/partner/auth'


@pytest.fixture
def browser():
    return Client()


def test_render_login(browser):
    response = browser.get(PARTNER_LOGIN)

    html = response.content.decode('utf8')
    assert 'username' in html
    assert 'password' in html
    assert 'Login' in html


@pytest.mark.django_db
def test_login_error(browser):
    response = browser.post(PARTNER_AUTH, {'username': USERNAME, 'password': TEST_PASS})

    assert 'Invalid credentials.' in response.content.decode('utf8')


@pytest.mark.django_db
def test_login_success(browser):
    create_partner_user()

    response = browser.post(PARTNER_AUTH, {'username': USERNAME, 'password': TEST_PASS})

    assert response.status_code == 302
    assert response.url == PARTNER_HOME


def create_partner_user():
    user = partner_user(username=USERNAME)
    user.set_password(TEST_PASS)
    user.save()


def create_pentest_user():
    user = pentest_user(username=USERNAME)
    user.set_password(TEST_PASS)
    user.save()


@pytest.mark.django_db
def test_home_no_pentest_info_message(browser):
    create_partner_user()
    browser.login(username=USERNAME, password=TEST_PASS)

    response = browser.get(PARTNER_HOME)

    html = response.content.decode('utf8')
    assert 'no available features' in html


@pytest.mark.django_db
def test_home_pentest_redirect(browser):
    create_pentest_user()
    browser.login(username=USERNAME, password=TEST_PASS)

    response = browser.get(PARTNER_HOME)

    assert response.status_code == 302
    assert response.url == '/pentest/'
