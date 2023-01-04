import logging
from multiprocessing.pool import ThreadPool

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.forms import model_to_dict

from monitor.tasks import create_monitors_and_run

from .constants import COMPLETED_STATE
from .models import Onboarding, OrganizationChecklistRun
from .offboarding.create_pdf_file import create_pdf_file
from .offboarding.offboarding_content import (
    get_non_integrated_vendors,
    get_offboarding_steps,
    get_offboarding_vendors,
)

pool = ThreadPool()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=Onboarding, dispatch_uid="post_save_onboarding")
def execute_post_onboarding_actions(sender, instance, created, **kwargs):
    if not created and instance.state == COMPLETED_STATE:
        pool.apply_async(create_monitors_and_run, args=(instance.organization,))


@receiver(
    pre_save,
    sender=OrganizationChecklistRun,
    dispatch_uid="create_offboarding_run_document",
)
def execute_pre_offboarding_actions(sender, instance, **kwargs):
    has_signature = "signature" in instance.metadata
    if has_signature:
        try:
            instance_data = model_to_dict(instance)
            offboarding_run = {
                'integratedVendors': get_offboarding_vendors(instance),
                'nonIntegratedVendors': get_non_integrated_vendors(instance),
                'steps': get_offboarding_steps(instance),
            }
            full_name = instance.owner.get_full_name().title()
            pdf = create_pdf_file(
                {
                    **instance_data,
                    'organizationName': instance.checklist.organization.name,
                    'fullName': full_name,
                    'offboardingRun': offboarding_run,
                }
            )
            instance.document = pdf
            logger.info('onboarding run has been updated with document ')

        except Exception:
            logger.exception('Error processing post offboarding update signal')
