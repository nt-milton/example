from django.core.management.base import BaseCommand

from feature.constants import okta_feature_flag
from feature.models import Flag
from laika.okta.api import OktaApi
from laika.settings import ENVIRONMENT, LAIKA_BACKEND
from organization.models import Organization
from user.constants import OKTA_GROUPS_NAMES
from user.helpers import send_email_invite
from user.models import User
from user.permissions import add_user_to_group

OktaApi = OktaApi()


class Command(BaseCommand):
    help = '''
        Migrate users with a suffix into okta.
        e.g. alvaro+playground@heylaika.com
    '''

    def add_arguments(self, parser):
        parser.add_argument('email_suffix', type=str)
        parser.add_argument('organization_id', type=str)
        parser.add_argument('--email_domain', type=str, default='heylaika')

    def handle(self, *args, **options):
        email_suffix = options.get("email_suffix")
        organization_id = options.get("organization_id")

        users = User.objects.filter(email__contains=email_suffix)

        organization = Organization.objects.get(id=organization_id)

        (flag, _) = Flag.objects.get_or_create(
            name=okta_feature_flag, organization=organization
        )
        flag.is_enabled = True
        flag.save()

        user_groups = OKTA_GROUPS_NAMES[str(ENVIRONMENT)][LAIKA_BACKEND]

        for user in users:
            try:
                self.stdout.write(
                    self.style.MIGRATE_LABEL(f'Trying to create {user.email} in okta')
                )

                okta_user = OktaApi.get_user_by_email(user.email)

                if okta_user:
                    self.stdout.write(
                        self.style.ERROR(f'User {user.email} already exists in okta')
                    )

                    continue

                okta_user, temporary_password = OktaApi.create_user(
                    first_name=user.first_name,
                    last_name=user.last_name,
                    email=user.email,
                    login=user.email,
                    organization=user.organization,
                    user_groups=user_groups,
                )

                user.username = okta_user.id
                user.is_active = True
                user.save()

                add_user_to_group(user)
                send_email_invite(user, temporary_password)

                self.stdout.write(
                    self.style.SUCCESS(f'Succesfully create user in okta: {user.email}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Some error happen trying to migrate user to okta {e}'
                    )
                )
