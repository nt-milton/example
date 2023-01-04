from datetime import timedelta

import pytest
from django.utils import timezone
from graphene import Context

from monitor.data_loaders import (
    RECENT_USER_DAYS,
    NewBadgeLoader,
    more_one_month_older,
    pass_week_after_view_dashboard,
    viewed_monitors,
)
from monitor.models import MonitorUserEvent, MonitorUserEventsOptions
from monitor.tests.factory import create_monitor_user_event, create_organization_monitor
from organization.tests import create_organization
from user.tests import create_user


@pytest.fixture
def loader():
    org = create_organization()
    context = Context(organization=org, user=create_user(org), FILES={})
    return NewBadgeLoader.with_context(context)


@pytest.mark.functional
def test_no_new_monitor_for_new_user(loader):
    om = create_organization_monitor()
    create_monitor_user_event(user=loader.context.user)

    is_new, *_ = loader.batch_load_fn([om]).get()

    assert not is_new


@pytest.mark.functional
def test_is_new_monitor(loader):
    no_recent_date = timezone.now() - timedelta(RECENT_USER_DAYS + 1)
    loader.context.user.date_joined = no_recent_date
    om = create_organization_monitor()
    loader.context.user.organization = om.organization
    create_monitor_user_event(user=loader.context.user)

    is_new, *_ = loader.batch_load_fn([om]).get()

    assert is_new


@pytest.mark.functional
def test_user_has_view_detail(loader):
    om = create_organization_monitor()
    create_monitor_user_event(
        user=loader.context.user,
        event=MonitorUserEventsOptions.VIEW_DETAIL,
        organization_monitor=om,
    )

    is_new, *_ = loader.batch_load_fn([om]).get()
    assert om in viewed_monitors(loader.context.user)
    assert not is_new


@pytest.mark.functional
def test_pass_week_after_view_dashboard(loader):
    us = loader.context.user
    us.date_joined = timezone.now() - timedelta(days=15)
    us.save(force_update=True)
    om = create_organization_monitor()
    om.created_at = timezone.now() - timedelta(days=10)
    om.save(force_update=True)
    mue = create_monitor_user_event(user=us)
    mue.event_time = timezone.now() - timedelta(days=8)
    mue.save(force_update=True)
    mue1 = create_monitor_user_event(user=us)
    mue1.event_time = timezone.now() - timedelta(days=2)
    mue1.save(force_update=True)

    is_new, *_ = loader.batch_load_fn([om]).get()

    assert pass_week_after_view_dashboard(om, MonitorUserEvent.objects.filter(user=us))
    assert not is_new


@pytest.mark.functional
def test_more_one_month_older(loader):
    us = loader.context.user
    om = create_organization_monitor()
    om.created_at = timezone.now() - timedelta(days=31)
    om.save(force_update=True)
    create_monitor_user_event(user=us)

    is_new, *_ = loader.batch_load_fn([om]).get()

    assert more_one_month_older(om)
    assert not is_new
