import abc
from abc import ABC

from django.db.models import F, Q

from fieldwork.constants import ER_STATUS_DICT
from search.types import CmdKCommentResultType, CmdKMentionResultType

AUDITOR_ACCEPTED = ER_STATUS_DICT['Auditor Accepted']


def evidence_request_url(audit_id, evidence_id):
    return f'/audits/{audit_id}/evidence-detail/{evidence_id}?activeTab=Comments'


def control_url(control_id):
    return f'/controls/{control_id}?activeTab=Comments'


def draft_report_url(audit_id):
    return f'/audits/{audit_id}?activeKey=Draft%20Report'


class CommentMapperInterface:
    def __init__(self, organization_id):
        self.organization_id = organization_id

    @abc.abstractmethod
    def get_comments(self):
        raise NotImplementedError


class ExtendedCommentMapperInterface(CommentMapperInterface):
    def __init__(self, organization_id):
        super().__init__(organization_id)

    @abc.abstractmethod
    def prefix_id(self):
        raise NotImplementedError

    @abc.abstractmethod
    def conditions(self):
        raise NotImplementedError

    @abc.abstractmethod
    def name(self, entity):
        raise NotImplementedError

    @abc.abstractmethod
    def url(self, entity):
        raise NotImplementedError

    @abc.abstractmethod
    def values_list(self):
        raise NotImplementedError

    def post_filter(self, objects):
        return objects


class MentionCommentMapper(ExtendedCommentMapperInterface, ABC):
    def get_comments(self):
        from comment.models import Mention

        def process_mention(mention):
            content = mention.get('comment__content') or mention.get('reply__content')
            first_name = mention.get('user__first_name')
            last_name = mention.get('user__last_name')
            return CmdKMentionResultType(
                id=f"{self.prefix_id()}-{mention.get('id')}",
                name=self.name(mention),
                description=content,
                mention=f'@{first_name} {last_name}',
                url=self.url(mention),
            )

        mentions = (
            self.post_filter(Mention.objects.filter(self.conditions()))
            .filter(
                Q(comment__is_deleted=False)
                | Q(reply__is_deleted=False, reply__parent__is_deleted=False)
            )
            .values(
                'id',
                'comment__content',
                'reply__content',
                'user__first_name',
                'user__last_name',
                *self.values_list(),
            )
        )

        return list(map(process_mention, mentions))


class ReplyCommentMapper(ExtendedCommentMapperInterface, ABC):
    def get_comments(self):
        from comment.models import Reply

        return [
            CmdKCommentResultType(
                id=f"{self.prefix_id()}-{reply.get('id')}",
                name=self.name(reply),
                owner=reply.get('owner_name'),
                description=reply.get('content'),
                url=self.url(reply),
            )
            for reply in self.post_filter(
                Reply.objects.filter(
                    **self.conditions(),
                    is_deleted=False,
                    parent__is_deleted=False,
                )
            ).values('id', 'owner_name', 'content', *self.values_list())
        ]


class ControlMentionCommentMapper(MentionCommentMapper):
    control_field = 'control'
    comment_control_field = f'comment__{control_field}'
    reply_control_field = f'reply__parent__{control_field}'

    def comment_conditions(self):
        return {f'{self.comment_control_field}__organization_id': self.organization_id}

    def reply_conditions(self):
        return {f'{self.reply_control_field}__organization_id': self.organization_id}

    def conditions(self):
        return Q(**self.comment_conditions()) | Q(**self.reply_conditions())

    def name(self, mention):
        return mention.get(f'{self.comment_control_field}__name') or mention.get(
            f'{self.reply_control_field}__name'
        )

    def url(self, mention):
        control_id = mention.get(f'{self.comment_control_field}__id') or mention.get(
            f'{self.reply_control_field}__id'
        )
        return control_url(control_id)

    def values_list(self):
        return [
            f'{self.comment_control_field}__id',
            f'{self.reply_control_field}__id',
            f'{self.comment_control_field}__name',
            f'{self.reply_control_field}__name',
        ]

    def prefix_id(self):
        return 'cm'


class EvidenceRequestMentionCommentMapper(MentionCommentMapper):
    evidence_field = 'evidence'
    comment_field = f'comment__{evidence_field}'
    reply_field = f'reply__parent__{evidence_field}'

    def comment_conditions(self):
        return {
            f'{self.comment_field}__audit__organization_id': self.organization_id,
            f'{self.comment_field}__audit__completed_at': None,
        }

    def reply_conditions(self):
        return {
            f'{self.reply_field}__audit__organization_id': self.organization_id,
            f'{self.reply_field}__audit__completed_at': None,
        }

    def conditions(self):
        return Q(**self.comment_conditions()) | Q(**self.reply_conditions())

    def post_filter(self, objects):
        return objects.exclude(
            Q(comment__evidence__status=AUDITOR_ACCEPTED)
            | Q(reply__parent__evidence__status=AUDITOR_ACCEPTED)
        )

    def name(self, mention):
        return mention.get(f'{self.comment_field}__name') or mention.get(
            f'{self.reply_field}__name'
        )

    def url(self, mention):
        audit_id = mention.get(f'{self.comment_field}__audit_id') or mention.get(
            f'{self.reply_field}__audit_id'
        )
        evidence_id = mention.get(f'{self.comment_field}__id') or mention.get(
            f'{self.reply_field}__id'
        )
        return evidence_request_url(audit_id, evidence_id)

    def values_list(self):
        return [
            f'{self.comment_field}__audit_id',
            f'{self.reply_field}__audit_id',
            f'{self.comment_field}__id',
            f'{self.reply_field}__id',
            f'{self.comment_field}__name',
            f'{self.reply_field}__name',
        ]

    def prefix_id(self):
        return 'erm'


class DraftReportMentionCommentMapper(MentionCommentMapper):
    audit_field = 'draft_report_comments__audit'
    comment_audit_field = f'comment__{audit_field}'
    reply_audit_field = f'reply__parent__{audit_field}'

    def comment_conditions(self):
        return {
            f'{self.comment_audit_field}__organization_id': self.organization_id,
            f'{self.comment_audit_field}__completed_at': None,
        }

    def reply_conditions(self):
        return {
            f'{self.reply_audit_field}__organization_id': self.organization_id,
            f'{self.reply_audit_field}__completed_at': None,
        }

    def conditions(self):
        return Q(**self.comment_conditions()) | Q(**self.reply_conditions())

    def name(self, mention):
        return mention.get(f'{self.comment_audit_field}__name') or mention.get(
            f'{self.reply_audit_field}__name'
        )

    def url(self, mention):
        audit_id = mention.get(f'{self.comment_audit_field}__id') or mention.get(
            f'{self.reply_audit_field}__id'
        )
        return draft_report_url(audit_id)

    def values_list(self):
        return [
            f'{self.comment_audit_field}__id',
            f'{self.reply_audit_field}__id',
            f'{self.comment_audit_field}__name',
            f'{self.reply_audit_field}__name',
        ]

    def prefix_id(self):
        return 'drm'


class ControlReplyCommentMapper(ReplyCommentMapper):
    control_field = 'parent__control'

    def conditions(self):
        return {f'{self.control_field}__organization_id': self.organization_id}

    def name(self, reply):
        return reply.get(f'{self.control_field}__name')

    def url(self, reply):
        return control_url(reply.get(f'{self.control_field}__id'))

    def values_list(self):
        return [
            f'{self.control_field}__id',
            f'{self.control_field}__name',
        ]

    def prefix_id(self):
        return 'cr'


class EvidenceRequestReplyCommentMapper(ReplyCommentMapper):
    evidence_field = 'parent__evidence'
    audit_field = f'{evidence_field}__audit'

    def conditions(self):
        return {
            f'{self.audit_field}__organization_id': self.organization_id,
            f'{self.audit_field}__completed_at': None,
        }

    def post_filter(self, objects):
        return objects.exclude(parent__evidence__status=AUDITOR_ACCEPTED)

    def name(self, reply):
        return reply.get(f'{self.evidence_field}__name')

    def url(self, reply):
        audit_id = reply.get(f'{self.audit_field}_id')
        evidence_id = reply.get(f'{self.evidence_field}__id')
        return evidence_request_url(audit_id, evidence_id)

    def values_list(self):
        return [
            f'{self.audit_field}_id',
            f'{self.evidence_field}__name',
            f'{self.evidence_field}__id',
        ]

    def prefix_id(self):
        return 'err'


class DraftReportReplyCommentMapper(ReplyCommentMapper):
    audit_field = 'parent__draft_report_comments__audit'

    def conditions(self):
        return {
            f'{self.audit_field}__organization_id': self.organization_id,
            f'{self.audit_field}__completed_at': None,
        }

    def name(self, reply):
        return reply.get(f'{self.audit_field}__name')

    def url(self, reply):
        return draft_report_url(reply.get(f'{self.audit_field}__id'))

    def values_list(self):
        return [
            f'{self.audit_field}__id',
            f'{self.audit_field}__name',
        ]

    def prefix_id(self):
        return 'drr'


class ControlCommentMapper(CommentMapperInterface):
    def get_comments(self):
        from control.models import ControlComment

        return [
            CmdKCommentResultType(
                id=f"cc-{comment.get('id')}",
                name=comment.get('control__name'),
                owner=comment.get('comment__owner_name'),
                description=comment.get('comment__content'),
                url=control_url(comment.get("control__id")),
            )
            for comment in ControlComment.objects.filter(
                control__organization_id=self.organization_id, comment__is_deleted=False
            ).values(
                'id',
                'control__name',
                'comment__content',
                'comment__owner_name',
                'control__id',
            )
        ]


class EvidenceRequestCommentMapper(CommentMapperInterface):
    def get_comments(self):
        from fieldwork.models import EvidenceComment

        return [
            CmdKCommentResultType(
                id=f"erc-{ec.get('id')}",
                name=ec.get('evidence__name'),
                owner=ec.get('comment__owner_name'),
                description=ec.get('comment__content'),
                url=evidence_request_url(ec.get('audit_id'), ec.get('evidence_id')),
            )
            for ec in EvidenceComment.objects.filter(
                is_internal_comment=False,
                evidence__audit__organization_id=self.organization_id,
                evidence__audit__completed_at=None,
                comment__is_deleted=False,
            )
            .exclude(evidence__status=AUDITOR_ACCEPTED)
            .annotate(
                audit_id=F('evidence__audit_id'),
            )
            .values(
                'id',
                'evidence_id',
                'audit_id',
                'evidence__name',
                'comment__owner_name',
                'comment__content',
            )
        ]


class DraftReportCommentMapper(CommentMapperInterface):
    def get_comments(self):
        from audit.models import DraftReportComment

        return [
            CmdKCommentResultType(
                id=f"drc-{dr.get('id')}",
                name=dr.get('audit__name'),
                owner=dr.get('comment__owner_name'),
                description=dr.get('comment__content'),
                url=draft_report_url(dr.get('audit_id')),
            )
            for dr in DraftReportComment.objects.filter(
                audit__organization_id=self.organization_id,
                audit__completed_at=None,
                comment__is_deleted=False,
            ).values(
                'id',
                'audit_id',
                'audit__name',
                'comment__owner_name',
                'comment__content',
            )
        ]


def launchpad_mapper(model, organization_id):
    results = []
    mapper_classes = [
        ControlCommentMapper(organization_id),
        ControlReplyCommentMapper(organization_id),
        ControlMentionCommentMapper(organization_id),
        EvidenceRequestCommentMapper(organization_id),
        EvidenceRequestReplyCommentMapper(organization_id),
        EvidenceRequestMentionCommentMapper(organization_id),
        DraftReportCommentMapper(organization_id),
        DraftReportReplyCommentMapper(organization_id),
        DraftReportMentionCommentMapper(organization_id),
    ]

    for mapper in mapper_classes:
        results.extend(mapper.get_comments())

    return results
