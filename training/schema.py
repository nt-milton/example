import base64
import io
import logging
from enum import Enum

import graphene
import reversion
from django.core.files import File
from django.db.models import Count, Q
from graphene_django.types import DjangoObjectType

from laika.auth import login_required, permission_required
from laika.types import FileType
from laika.utils.history import create_revision
from training.models import Alumni, Training
from user.constants import USER_ROLES

logger = logging.getLogger(__name__)


def map_user_roles_to_training_user_types(self):
    return Enum('TrainingUserRoles', [(self[val], self[val]) for val in self])


TrainingUserTypes = graphene.Enum.from_enum(
    map_user_roles_to_training_user_types(USER_ROLES)
)


class TrainingType(DjangoObjectType):
    class Meta:
        model = Training

    is_alumni = graphene.Boolean()
    slides = graphene.Field(FileType)
    roles = graphene.List(TrainingUserTypes, required=True)

    def resolve_is_alumni(self, info):
        return Alumni.objects.filter(user=info.context.user, training=self).exists()

    def resolve_slides(self, info):
        if not self.slides:
            return None

        return FileType(name=self.slides.name, url=self.slides.url)


class AlumniType(DjangoObjectType):
    class Meta:
        model = Alumni


class Query(object):
    trainings = graphene.List(TrainingType, required=True)
    training = graphene.Field(
        TrainingType, id=graphene.Int(required=True), required=True
    )

    @login_required
    @permission_required("training.view_training")
    def resolve_trainings(self, info, **kwargs):
        user_is_alumni = Count(
            'alumni', filter=Q(alumni__user__username=info.context.user.username)
        )
        current_user_role = info.context.user.role
        if (
            current_user_role == TrainingUserTypes.SuperAdmin.value
            or current_user_role == TrainingUserTypes.OrganizationAdmin.value
        ):
            return Training.objects.annotate(is_alumni=user_is_alumni).filter(
                organization=info.context.user.organization
            )
        else:
            return (
                Training.objects.annotate(is_alumni=user_is_alumni)
                .filter(organization=info.context.user.organization)
                .filter(Q(roles__contains=current_user_role))
            )

    @login_required
    @permission_required("training.view_training")
    def resolve_training(self, info, **kwargs):
        training_id = kwargs.get('id')
        current_user_role = info.context.user.role
        if not training_id or not current_user_role:
            return None

        if (
            current_user_role == TrainingUserTypes.SuperAdmin.value
            or current_user_role == TrainingUserTypes.OrganizationAdmin.value
        ):
            return Training.objects.get(
                pk=training_id, organization=info.context.user.organization
            )
        else:
            return Training.objects.get(
                Q(roles__contains=current_user_role),
                pk=training_id,
                organization=info.context.user.organization,
            )


class TrainingInput(graphene.InputObjectType):
    name = graphene.String(required=False, default=None)
    category = graphene.String(required=False, default=None)
    roles = graphene.List(TrainingUserTypes, required=False, default=list)
    description = graphene.String(required=False, default=None)
    filename = graphene.String(required=False, default=None)
    slides = graphene.String(required=False, default=None)


class CreateTraining(graphene.Mutation):
    class Arguments:
        input = TrainingInput(required=True)

    ok = graphene.Boolean()
    error = graphene.String()
    training = graphene.Field(TrainingType)

    @staticmethod
    @login_required
    @create_revision('Created training')
    @permission_required('training.add_training')
    def mutate(root, info, input=None):
        training = None
        ok = True
        error = None
        try:
            if 'slides' in info.context.FILES:
                slides = info.context.FILES['slides']
            else:
                slides = File(
                    name=input.filename, file=io.BytesIO(base64.b64decode(input.slides))
                )
            training = {
                'organization': info.context.user.organization,
                'name': input.name,
                'category': input.category,
                'description': input.description,
                'slides': slides,
            }
            if input.get('roles'):
                training.update({'roles': input.get('roles')})
            training = Training.objects.create(**training)
        except Exception as e:
            error = str(e)
            ok = False
        finally:
            return CreateTraining(ok=ok, error=error, training=training)


class UpdateTraining(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = TrainingInput(required=True)

    ok = graphene.Boolean()
    error = graphene.String()
    training = graphene.Field(TrainingType)

    @staticmethod
    @login_required
    @create_revision('Updated training')
    @permission_required('training.change_training')
    def mutate(root, info, id, input=None):
        ok = True
        error = None
        training = None
        try:
            training = Training.objects.get(
                pk=id, organization=info.context.user.organization
            )
            if input.name:
                training.name = input.name
            if input.category:
                training.category = input.category
            if input.roles:
                training.roles = list(input.roles)
            if input.description:
                training.description = input.description
            if 'slides' in info.context.FILES:
                training.slides = info.context.FILES['slides']
            if input.filename:
                training.slides = File(
                    name=input.filename, file=io.BytesIO(base64.b64decode(input.slides))
                )
            training.save()
        except Exception as e:
            ok = False
            error = str(e)
            training = None
        finally:
            return UpdateTraining(ok=ok, error=error, training=training)


class CompleteTraining(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    ok = graphene.Boolean()
    error = graphene.String()
    alumni = graphene.Field(AlumniType)

    @staticmethod
    @login_required
    @create_revision('Completed training')
    def mutate(root, info, id):
        ok = True
        error = None
        alumni = None
        try:
            training = Training.objects.get(
                pk=id, organization=info.context.user.organization
            )
            alumni = Alumni.objects.create(user=info.context.user, training=training)
        except Exception as e:
            ok = False
            error = str(e)
            alumni = None
        finally:
            return CompleteTraining(ok=ok, error=error, alumni=alumni)


class DeleteTraining(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    ok = graphene.Boolean()
    error = graphene.String()
    alumni = graphene.Field(AlumniType)

    @staticmethod
    @login_required
    @permission_required('training.delete_training')
    def mutate(root, info, id):
        ok = True
        error = None
        try:
            with reversion.create_revision():
                msg = (
                    f'Deleted training {id} - Organization '
                    f'{info.context.user.organization.id}, '
                    f'User {info.context.user.id}'
                )
                reversion.set_user(info.context.user)
                reversion.set_comment(msg)

                Training.objects.filter(pk=id).delete()
                logger.info(msg)
        except Exception as e:
            ok = False
            error = str(e)
        finally:
            return DeleteTraining(ok=ok, error=error)


class Mutation(graphene.ObjectType):
    create_training = CreateTraining.Field()
    update_training = UpdateTraining.Field()
    complete_training = CompleteTraining.Field()
    delete_training = DeleteTraining.Field()
