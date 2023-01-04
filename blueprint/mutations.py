import logging

import graphene

from blueprint.models.history import BlueprintHistory
from blueprint.tasks import do_prescribe_controls, prescribe_content
from control.models import Control
from laika.decorators import concierge_service
from laika.utils.exceptions import ServiceException
from organization.constants import HISTORY_STATUS_IN_PROGRESS

logger = logging.getLogger(__name__)
ERROR = 'An error happened Prescribing Controls, please try again'


class PrescribeControls(graphene.Mutation):
    class Arguments:
        organization_id = graphene.String(required=True)
        control_ref_ids = graphene.List(graphene.String, required=True)

    success = graphene.Boolean()

    @concierge_service(
        permission='blueprint.view_controlblueprint',
        exception_msg='Failed to prescribe controls',
    )
    def mutate(self, info, **kwargs):
        organization_id = kwargs.get('organization_id')
        control_ref_ids = kwargs.get('control_ref_ids')

        entry = (
            BlueprintHistory.objects.filter(organization_id=organization_id)
            .order_by('-created_at')
            .first()
        )

        if entry and entry.status == HISTORY_STATUS_IN_PROGRESS:
            logger.info(
                'There is another prescription in the background for this '
                f'organization: {organization_id}. Do nothing'
            )
            return PrescribeControls(success=True)

        do_prescribe_controls.delay(
            organization_id, info.context.user.id, control_ref_ids
        )

        return PrescribeControls(success=True)


class UnprescribeControls(graphene.Mutation):
    class Arguments:
        organization_id = graphene.String(required=True)
        control_ref_ids = graphene.List(graphene.String, required=True)

    success = graphene.Boolean()

    @concierge_service(
        permission='blueprint.view_controlblueprint',
        exception_msg='Failed to unprescribe controls',
    )
    def mutate(self, info, **kwargs):
        try:
            Control.objects.filter(
                reference_id__in=kwargs.get('control_ref_ids'),
                organization_id=kwargs.get('organization_id'),
            ).delete()

            return UnprescribeControls(success=True)
        except Exception as e:
            logger.warning(f'Error happened when unprescribing controls: {e}')
            return ServiceException('Error happened. Please try again!')


class PrescribeContent(graphene.Mutation):
    class Arguments:
        organization_id = graphene.String(required=True)
        framework_tags = graphene.List(graphene.String, required=True)

    success = graphene.Boolean()

    @concierge_service(
        permission='blueprint.view_controlblueprint',
        exception_msg='Failed to prescribe content',
    )
    def mutate(self, info, **kwargs):
        prescribe_content.delay(
            user_id=info.context.user.id,
            organization_id=kwargs.get('organization_id'),
            framework_tags=kwargs.get('framework_tags'),
        )

        return PrescribeContent(success=True)
