import graphene
from graphene.types.objecttype import ObjectType

import access_review.schema
import action_item.schema
import address.schema
import alert.schema
import announcement.schema
import audit.schema
import auditee.schema
import auditor.schema
import blueprint.schema
import certification.schema
import comment.schema
import concierge.schema
import control.roadmap.schema
import control.schema
import dashboard.schema
import dataroom.schema
import drive.schema
import evidence.schema
import feature.schema
import integration.schema
import library.schema
import link.schema
import monitor.schema
import objects.schema
import organization.schema
import pentest.schema
import policy.schema
import program.schema
import report.schema
import search.schema
import seeder.schema
import sso.schema
import tag.schema
import training.schema
import user.officers
import user.schema
import user.team_members
import user.teams
import user.watcher_list.schema
import vendor.schema
from action_item.constants import ACTION_ITEM_EDAS_HEALTH_CHECK
from laika.decorators import laika_service
from laika.edas import eda_publisher
from laika.edas.edas import EdaMessage, EdaRegistry
from search.types import SearchTypes


class EdasHealthCheckQuery(object):
    edas_action_item_health_check = graphene.String()

    @laika_service(
        permission='dashboard.view_dashboard',
        exception_msg='Failed to send message to exchange',
    )
    def resolve_edas_action_item_health_check(self, info, **kwargs):
        message = EdaMessage.build(
            event=EdaRegistry.event_lookup(ACTION_ITEM_EDAS_HEALTH_CHECK),
            message='Edas service health check passed',
        )

        eda_publisher.submit_event(message=message)

        return 'Message sent successfully'


class Query(
    announcement.schema.Query,
    certification.schema.Query,
    address.schema.Query,
    dashboard.schema.Query,
    objects.schema.Query,
    feature.schema.Query,
    training.schema.Query,
    policy.schema.Query,
    user.schema.Query,
    organization.schema.Query,
    vendor.schema.Query,
    user.officers.Query,
    user.teams.Query,
    user.watcher_list.schema.Query,
    control.schema.Query,
    control.roadmap.schema.Query,
    program.schema.Query,
    graphene.ObjectType,
    concierge.schema.Query,
    search.schema.Query,
    library.schema.Query,
    dataroom.schema.Query,
    drive.schema.Query,
    integration.schema.Query,
    report.schema.Query,
    alert.schema.Query,
    tag.schema.Query,
    audit.schema.Query,
    monitor.schema.Query,
    seeder.schema.Query,
    auditee.schema.Query,
    action_item.schema.Query,
    auditor.schema.Query,
    sso.schema.Query,
    pentest.schema.Query,
    blueprint.schema.Query,
    access_review.schema.Query,
    EdasHealthCheckQuery,
):
    pass


class Mutation(
    action_item.schema.Mutation,
    blueprint.schema.Mutation,
    certification.schema.Mutation,
    report.schema.Mutation,
    dashboard.schema.Mutation,
    objects.schema.Mutation,
    concierge.schema.Mutation,
    training.schema.Mutation,
    policy.schema.Mutation,
    user.schema.Mutation,
    organization.schema.Mutation,
    vendor.schema.Mutation,
    user.teams.Mutation,
    user.watcher_list.schema.Mutation,
    user.officers.Mutation,
    user.team_members.Mutation,
    control.schema.Mutation,
    sso.schema.Mutation,
    seeder.schema.Mutation,
    control.roadmap.schema.Mutation,
    program.schema.Mutation,
    dataroom.schema.Mutation,
    evidence.schema.Mutation,
    library.schema.Mutation,
    link.schema.Mutation,
    integration.schema.Mutation,
    drive.schema.Mutation,
    tag.schema.Mutation,
    graphene.ObjectType,
    alert.schema.Mutation,
    audit.schema.Mutation,
    monitor.schema.Mutation,
    feature.schema.Mutation,
    auditee.schema.Mutation,
    auditor.schema.Mutation,
    comment.schema.Mutation,
    pentest.schema.Mutation,
    access_review.schema.Mutation,
):
    pass


class EvidenceQuery(objects.schema.Query, ObjectType):
    pass


class EvidenceMutation(
    objects.schema.Mutation,
):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation, types=SearchTypes)
evidence_api_schema = graphene.Schema(
    query=EvidenceQuery,
    mutation=EvidenceMutation,
)
