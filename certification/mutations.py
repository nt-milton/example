import logging

import graphene

from certification.inputs import (
    UnlockedCertificationCompletionDateInput,
    UnlockedOrganizationCertificationAuditDatesInput,
)
from certification.models import UnlockedOrganizationCertification
from certification.types import UnlockedOrganizationCertificationType
from laika.decorators import concierge_service, laika_service

logger = logging.getLogger(__name__)
ERROR = 'An error happened, please try again'


def update_audit_dates_unlocked_certification(_input):
    organization_id = _input.get('organization_id')
    certification_id = _input.get('certification_id')
    target_audit_completion_date = _input.get('target_audit_completion_date')

    unlocked_certification = UnlockedOrganizationCertification.objects.filter(
        organization__id=organization_id, certification_id=certification_id
    )

    update_args = {'target_audit_completion_date': target_audit_completion_date}

    if 'target_audit_start_date' in _input:
        update_args['target_audit_start_date'] = _input.get('target_audit_start_date')

    unlocked_certification.update(**update_args)


class UpdateAuditDatesUnlockedOrgCertification(graphene.Mutation):
    class Arguments:
        input = UnlockedOrganizationCertificationAuditDatesInput(required=True)

    unlocked_org_certification = graphene.Field(UnlockedOrganizationCertificationType)

    @concierge_service(
        permission='user.change_concierge',
        exception_msg='Failed to update unlocked certification',
        revision_name='Audit dates updated',
    )
    def mutate(self, info, input):
        organization_id = input.get('organization_id')
        certification_id = input.get('certification_id')
        update_audit_dates_unlocked_certification(input)

        return UpdateAuditDatesUnlockedOrgCertification(
            unlocked_org_certification=UnlockedOrganizationCertification.objects.get(
                organization__id=organization_id, certification__id=certification_id
            )
        )


class UpdateAuditCompletionDate(graphene.Mutation):
    class Arguments:
        input = UnlockedCertificationCompletionDateInput(required=True)

    unlocked_org_certification = graphene.Field(UnlockedOrganizationCertificationType)

    @laika_service(
        permission='control.change_roadmap',
        exception_msg='Failed to update audit completion date',
        revision_name='Audit dates updated',
    )
    def mutate(self, info, input):
        organization_id = input.get('organization_id')
        certification_id = input.get('certification_id')
        update_audit_dates_unlocked_certification(input)

        return UpdateAuditCompletionDate(
            unlocked_org_certification=UnlockedOrganizationCertification.objects.get(
                organization__id=organization_id, certification__id=certification_id
            )
        )
