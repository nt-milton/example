import graphene
from graphene_django.types import DjangoObjectType

import evidence.constants as constants
from dataroom.models import Dataroom
from drive.types import SubItems
from evidence.utils import get_content_id, get_file_name_from_path


class DataroomDocumentType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    description = graphene.String()
    link = graphene.String()
    evidence_type = graphene.String(name='type')
    date = graphene.DateTime()
    linkable = graphene.Boolean()
    content_id = graphene.String()
    file_name = graphene.String()


class CollectionType(graphene.ObjectType):
    documents = graphene.List(DataroomDocumentType)
    policies = graphene.List(DataroomDocumentType)
    s3_files = graphene.List(DataroomDocumentType)
    officers = graphene.List(DataroomDocumentType)
    teams = graphene.List(DataroomDocumentType)


class DataroomType(DjangoObjectType):
    class Meta:
        model = Dataroom

    collection = graphene.Field(CollectionType)
    evidence = graphene.List(DataroomDocumentType)

    @staticmethod
    def append_evidence_to_type(evidence_by_type, evidence_type, evidence):
        if evidence_type not in evidence_by_type:
            evidence_by_type[evidence_type] = []
        evidence_by_type[evidence_type].append(evidence)

    def resolve_collection(self, info):
        evidence_by_type = {}
        for e in self.dataroom_evidence.all():
            DataroomType.append_evidence_to_type(
                evidence_by_type, e.evidence.type, e.evidence
            )

        return CollectionType(
            documents=map_evidence(evidence_by_type.get(constants.LAIKA_PAPER, [])),
            policies=map_evidence(evidence_by_type.get(constants.POLICY, [])),
            s3_files=map_evidence(evidence_by_type.get(constants.FILE, [])),
            officers=map_evidence(evidence_by_type.get(constants.OFFICER, [])),
            teams=map_evidence(evidence_by_type.get(constants.TEAM, [])),
        )

    def resolve_evidence(self, info):
        return [e.evidence for e in self.dataroom_evidence.all()]


class FilterItemsDatarooms(graphene.ObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    sub_items = graphene.List(SubItems, default_value=[])
    disabled = graphene.Boolean(default_value=False)


class FilterGroupsDatarooms(graphene.ObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    items = graphene.List(FilterItemsDatarooms, default_value=[])


def get_file_name(evidence):
    return (
        get_file_name_from_path(evidence.file.name)
        if evidence.type in [constants.POLICY]
        else evidence.name
    )


def map_evidence(evidence):
    docs = []
    for e in evidence:
        docs.append(
            DataroomDocumentType(
                id=e.id,
                name=e.name,
                link=e.file.url
                if e.type
                in [
                    constants.FILE,
                    constants.OFFICER,
                    constants.TEAM,
                    constants.LAIKA_PAPER,
                    constants.POLICY,
                ]
                else '',
                description=e.description,
                date=e.created_at,
                evidence_type=e.type,
                linkable=(
                    e.type
                    not in (
                        constants.FILE,
                        constants.TEAM,
                        constants.OFFICER,
                        constants.LAIKA_PAPER,
                        constants.POLICY,
                    )
                ),
                content_id=get_content_id(e),
                file_name=get_file_name(e),
            )
        )
    return docs
