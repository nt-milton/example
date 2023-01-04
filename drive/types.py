import graphene

from evidence.utils import get_evidence_manual_tags, tags_associated_to_evidence
from laika.types import FileType, PaginationResponseType
from laika.utils.files import get_file_extension
from user.types import UserType


class TagsInfo(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String(required=True)
    type = graphene.String(default_value='tag')
    is_manual = graphene.Boolean(default_value=False)


class DriveEvidenceType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    evidence_type = graphene.String(name='type')
    owner = graphene.Field(UserType)
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()
    extension = graphene.String()
    tags = graphene.List(TagsInfo)
    description = graphene.String()
    file = graphene.Field(FileType)


class DriveCollectionType(graphene.ObjectType):
    s3_files = graphene.List(DriveEvidenceType)
    laika_papers = graphene.List(DriveEvidenceType)


class SubItems(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    disabled = graphene.Boolean(default_value=False)


class FilterItems(graphene.ObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    sub_items = graphene.List(SubItems, default_value=[])
    disabled = graphene.Boolean(default_value=False)


class FilterGroups(graphene.ObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    items = graphene.List(FilterItems, default_value=[])


class DocumentsResponseType(graphene.ObjectType):
    id = graphene.String(required=True)
    documents = graphene.List(DriveEvidenceType)


class LaikaLogsType(graphene.ObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    source = graphene.String(required=True)


class LaikaLogsResponseType(graphene.ObjectType):
    laika_logs = graphene.List(LaikaLogsType)
    pagination = graphene.Field(PaginationResponseType)


class DriveResponseType(graphene.ObjectType):
    id = graphene.String(required=True)
    organization_name = graphene.String(required=True)
    collection = graphene.List(DriveEvidenceType)
    pagination = graphene.Field(PaginationResponseType)


class FilterGroupResponseType(graphene.ObjectType):
    data = graphene.List(FilterGroups, required=True)


class DriveResponseIdType(graphene.ObjectType):
    ids = graphene.List(graphene.String)


class LaikaPaperIgnoreWordResponseType(graphene.ObjectType):
    id = graphene.String(required=True)
    word = graphene.String()
    language = graphene.String()


class LaikaPaperResponseType(graphene.ObjectType):
    id = graphene.String(required=True)
    laika_paper_name = graphene.String(required=True)
    laika_paper_content = graphene.String()
    laika_paper_ignore_words = graphene.List(LaikaPaperIgnoreWordResponseType)
    owner = graphene.Field(UserType)
    type = graphene.String()


def append_drive_evidence_to_type(evidence_by_type, drive_evidence):
    evidence_type = drive_evidence.evidence.type
    if evidence_type not in evidence_by_type:
        evidence_by_type[evidence_type] = []
    evidence_by_type[evidence_type].append(drive_evidence)


def get_tags_associated_to_evidence(evidence):
    organization_id = evidence.organization.id

    evidence_tags = get_evidence_manual_tags(
        evidence, cache_name=f'manual_tags_for_{organization_id}_{evidence.id}'
    )

    cache_name = f'doc_tags_{organization_id}_{evidence.id}'
    all_tags = tags_associated_to_evidence(evidence, cache_name=cache_name)

    related_tags = [TagsInfo(id=tag, name=tag) for tag in all_tags['related_tags']]

    evidence_own_tags = [
        TagsInfo(id=tag.id, name=tag.name, is_manual=tag.is_manual)
        for tag in evidence_tags
        if tag.name not in all_tags['related_tags']
    ]

    return (
        [TagsInfo(id=p, name=p, type='playbook') for p in all_tags['playbook_tags']]
        + [TagsInfo(id=c, name=c, type='certificate') for c in all_tags['certs_tags']]
        + related_tags
        + evidence_own_tags
    )


def map_evidence(drive_evidence):
    attached_evidence = []
    for de in drive_evidence:
        attached_evidence.append(
            DriveEvidenceType(
                id=de.evidence.id,
                name=de.evidence.name,
                created_at=de.evidence.created_at,
                updated_at=de.evidence.updated_at,
                evidence_type=de.evidence.type,
                owner=de.owner,
                extension=get_file_extension(de.evidence.file.name),
                tags=get_tags_associated_to_evidence(de.evidence),
                description=de.evidence.description,
                file=de.evidence.file,
            )
        )
    return attached_evidence


class FiltersDocumentType(graphene.InputObjectType):
    search = graphene.String()
    owner = graphene.List(graphene.String)
    type = graphene.List(graphene.String)
    id = graphene.List(graphene.String)
    tags = graphene.List(graphene.String)
