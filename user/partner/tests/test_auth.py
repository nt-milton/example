import pytest
from django.contrib.auth.models import AnonymousUser

from user.models import Partner, PartnerType, User
from user.partner.auth import is_partner, is_pentest_partner


def partner_user(**kwargs) -> User:
    return User.objects.create(role='Partner', **kwargs)


def pentest_user(**kwargs) -> User:
    user = partner_user(**kwargs)
    partner = Partner.objects.create(type=PartnerType.PENTEST)
    user.partners.add(partner)
    return user


def test_anonymous_is_not_partner():
    assert not is_partner(AnonymousUser())


@pytest.mark.django_db
def test_is_partner():
    user = partner_user()
    assert is_partner(user)
    assert not is_pentest_partner(user)


@pytest.mark.django_db
def test_is_pentest_partner():
    user = pentest_user()
    assert is_partner(user)
    assert is_pentest_partner(user)


@pytest.mark.django_db
def test_partner_cannot_access_admin():
    user = pentest_user()
    user.is_staff = True
    assert not is_partner(user)
