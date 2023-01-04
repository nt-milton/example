from django.db.models import Q

from integration.models import Integration
from objects.models import LaikaObject
from organization.models import (
    OffboardingStatus,
    OffboardingVendor,
    OrganizationChecklistRun,
    OrganizationChecklistRunSteps,
)
from vendor.models import Vendor


def get_integrated_vendors(checklist_run: OrganizationChecklistRun):
    organization = checklist_run.owner.organization
    lo_filter = Q(
        object_type__type_name='user',
        data__Email=checklist_run.owner.email,
        connection_account__isnull=False,
        connection_account__organization=organization,
    )
    object_ids = LaikaObject.objects.filter(lo_filter).values_list('id', flat=True)
    revoked_laika_objects = LaikaObject.objects.filter(
        Q(lo_filter & Q(deleted_at__isnull=False))
    )
    revoked_ids = revoked_laika_objects.values_list('id', flat=True)
    revoked_vendors = revoked_laika_objects.values_list(
        'connection_account__integration__vendor', 'deleted_at'
    )
    all_ids = object_ids.union(revoked_ids)
    return Integration.objects.filter(
        connection_accounts__laika_objects__id__in=all_ids,
        connection_accounts__isnull=False,
    ), dict(revoked_vendors)


def get_offboarding_vendors(checklist_run: OrganizationChecklistRun):
    from organization.types import OffboardingRunVendorType

    integrated_vendors, revoked_vendors = get_integrated_vendors(checklist_run)
    vendors = Vendor.objects.filter(integration__in=integrated_vendors).distinct()

    return [
        OffboardingRunVendorType(
            checklist_run_id=checklist_run.id,
            vendor=vendor,
            offboarding_state=OffboardingVendor(
                checklist_run=checklist_run,
                status=OffboardingStatus.COMPLETED
                if revoked_vendors.get(vendor.id, None)
                else OffboardingStatus.PENDING,
                vendor=vendor,
                date=revoked_vendors.get(vendor.id, None),
            ),
        )
        for vendor in vendors
    ]


def get_offboarding_vendors_state(
    checklist_run: OrganizationChecklistRun, vendors: list[Vendor]
):
    states = OffboardingVendor.objects.filter(
        checklist_run_id=checklist_run.id, vendor__in=vendors
    )
    return {state.vendor.id: state for state in states}


def get_non_integrated_vendors(checklist_run: OrganizationChecklistRun):
    from organization.types import OffboardingRunVendorType

    integrated_vendors, _ = get_integrated_vendors(checklist_run)
    organization = checklist_run.checklist.organization
    vendors = (
        Vendor.objects.filter(organizations=organization.id)
        .exclude(integration__in=integrated_vendors)
        .distinct()
    )
    vendors_state = get_offboarding_vendors_state(checklist_run, vendors)
    return [
        OffboardingRunVendorType(
            checklist_run_id=checklist_run.id,
            vendor=vendor,
            offboarding_state=vendors_state.get(vendor.id),
        )
        for vendor in vendors
    ]


def get_offboarding_steps_state(checklist_run, steps):
    states = OrganizationChecklistRunSteps.objects.filter(
        checklist_run_id=checklist_run.id, action_item__in=steps
    )
    return {state.action_item.id: state for state in states}


def get_offboarding_steps(checklist_run: OrganizationChecklistRun):
    from organization.types import OffboardingRunStepType

    steps = checklist_run.checklist.action_item.steps.filter(
        Q(metadata__isTemplate__isnull=True) | Q(metadata__isTemplate=False)
    ).order_by('-id')

    steps_state = get_offboarding_steps_state(checklist_run, steps)
    return [
        OffboardingRunStepType(
            checklist_run_id=checklist_run.id,
            step=step,
            offboarding_state=steps_state.get(step.id),
        )
        for step in steps
    ]
