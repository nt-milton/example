import logging
from typing import List, Optional, Tuple, TypeVar

from asgiref.sync import async_to_sync
from okta.client import Client as OktaClient
from okta.models import (
    Application,
    CreateUserRequest,
    Group,
    PasswordCredential,
    User,
    UserCredentials,
    UserProfile,
)
from okta.models.temp_password import TempPassword

from laika.settings import OKTA_API_KEY, OKTA_DOMAIN_URL
from laika.utils.strings import get_temporary_random_password
from organization.models import Organization

logger = logging.getLogger(__name__)

config = {
    'orgUrl': OKTA_DOMAIN_URL,
    'token': OKTA_API_KEY,
    'raiseException': True,
    'logging': {"enabled": True},
    'cache': {'enabled': True},
}

OKTA_MODELS = TypeVar('OKTA_MODELS', User, Group)


def format_response(okta_model, response) -> List[OKTA_MODELS]:
    formatted_response = []
    data, resp, err = response

    if not err:
        for item in data:
            formatted_response.append(okta_model(item.as_dict()))
    else:
        logger.error(err)

    return formatted_response


class OktaApi:
    okta_client = OktaClient(config)

    def get_users(self) -> List[User]:
        try:
            return format_response(User, async_to_sync(self.okta_client.list_users)())
        except Exception as e:
            logger.exception(f'error trying to get  okta users: {e}')
            raise e

    def get_user_by_email(self, email: str) -> Optional[User]:
        query_parameters = {'search': f'profile.login eq "{email}"'}
        try:
            response = format_response(
                User, async_to_sync(self.okta_client.list_users)(query_parameters)
            )

            return response[0] if len(response) else None
        except Exception as e:
            logger.exception(f'error trying to get  okta user by email: {e}')
            return None

    async def get_user_by_email_async(self, email: str) -> Optional[User]:
        query_parameters = {'search': f'profile.login eq "{email}"'}
        try:
            okta_response = await self.okta_client.list_users(query_parameters)
            response = format_response(User, okta_response)

            return response[0] if len(response) else None
        except Exception as e:
            logger.exception(f'error trying to get  okta user by email: {e}')
            raise e

    def get_user_groups(self, user_id: str) -> List[Group]:
        try:
            return format_response(
                Group, async_to_sync(self.okta_client.list_user_groups)(user_id)
            )
        except Exception as e:
            logger.exception(f'error trying to get  okta users: {e}')
            raise e

    async def get_user_groups_async(self, user_id: str) -> List[Group]:
        try:
            okta_response = await self.okta_client.list_user_groups(user_id)
            return format_response(Group, okta_response)
        except Exception as e:
            logger.exception(f'error trying to get  okta users: {e}')
            raise e

    def create_user(
        self,
        first_name: str,
        last_name: str,
        email: str,
        login: str,
        organization: Organization,
        user_groups: List[str] = None,
    ) -> Tuple[User, str]:
        query_parameters = {'activate': 'true'}

        user_profile = UserProfile(
            dict(
                firstName=first_name,
                lastName=last_name,
                email=email,
                login=login,
                organizationId=str(organization.id),
                organization=organization.name,
            )
        )

        groups_ids = []
        if user_groups and len(user_groups):
            try:
                laika_groups = self.get_laika_groups(user_groups)
                for group in laika_groups:
                    groups_ids.append(group.id)
            except Exception as e:
                logger.exception(
                    f'error trying to get okta groups when creating an user: {e}'
                )
                raise e

        password = get_temporary_random_password(length=12)
        create_user_req = CreateUserRequest(
            dict(
                profile=user_profile,
                groupIds=groups_ids,
                credentials=UserCredentials(
                    dict(password=PasswordCredential(dict(value=password)))
                ),
            )
        )

        try:
            user, _, err = async_to_sync(self.okta_client.create_user)(
                create_user_req, query_parameters
            )

            if err:
                logger.error(err)
                raise err

            response, _, err = async_to_sync(
                self.okta_client.expire_password_and_get_temporary_password
            )(user.id)

            temporary_password = TempPassword(response.as_dict()).temp_password

            if err:
                logger.error(err)
                raise err

            return user, temporary_password
        except Exception as e:
            logger.exception(f'error trying to create okta user: {e}')
            raise e

    def get_one_time_token(self, user_id: str) -> str:
        try:
            response, _, err = async_to_sync(
                self.okta_client.expire_password_and_get_temporary_password
            )(user_id)

            if err:
                logger.error(err)
                raise err

            temporary_password = TempPassword(response.as_dict()).temp_password

            return temporary_password
        except Exception as e:
            logger.exception(
                f'error trying to get one time token for user {user_id}: {e}'
            )
            raise e

    def expire_password(self, user_id: str) -> bool:
        try:
            response, _, err = async_to_sync(self.okta_client.expire_password)(user_id)

            if err:
                logger.exception(err)
                return False

            return True
        except Exception as e:
            logger.exception(
                f'error trying to get one time token for user {user_id}: {e}'
            )
            return False

    def update_user(self, okta_user: User, updated_user) -> User:
        user = dict(
            profile=dict(
                email=okta_user.profile.email,
                login=okta_user.profile.login,
                firstName=updated_user.first_name,
                lastName=updated_user.last_name,
            )
        )

        try:
            user, _, err = async_to_sync(self.okta_client.update_user)(
                okta_user.id, user
            )

            if err:
                logger.error(err)
                raise err
        except Exception as e:
            logger.exception(f'error trying to create okta user: {e}')
            raise e

        return user

    def activate_user(self, user_id: str, send_email=True):
        query_parameters = {'sendEmail': 'true' if send_email else 'false'}
        try:
            user, _, err = async_to_sync(self.okta_client.activate_user)(
                user_id, query_parameters
            )

            if err:
                logger.error(err)

        except Exception as e:
            logger.warning(f'error trying to activate okta user: {e}')
            raise e

        return user

    def delete_user(self, user_id: str) -> bool:
        # First deactivate user
        try:
            logger.info(f'Deleting OKTA User: {user_id}')
            async_to_sync(self.okta_client.deactivate_user)(user_id)
        except Exception as e:
            logger.warning(f'error trying to deactivate okta user: {e}')
            return False

        # Then delete
        try:
            async_to_sync(self.okta_client.deactivate_or_delete_user)(user_id)
        except Exception as e:
            logger.exception(f'error trying to delete okta user: {e}')
            raise e

        return True

    def get_laika_groups(self, group_names: List[str] = None):
        """
        [query_params.q] {str}
        """

        api_url = '/api/v1/groups'

        if group_names and len(group_names):
            query_params = 'search='
            for index, name in enumerate(group_names):
                if not index:
                    query_params += f'profile.name eq "{name}"'
                else:
                    query_params += f' or profile.name eq "{name}"'

            api_url += f"/?{query_params}"

        try:
            request, error = async_to_sync(
                self.okta_client.get_request_executor().create_request
            )(method='GET', url=api_url, body={}, headers={}, oauth=False)

            response, error = async_to_sync(
                self.okta_client.get_request_executor().execute
            )(request, Group)

            groups = []

            for item in response.get_body():
                groups.append(Group(item))

            return groups
        except Exception as e:
            logger.exception(f'error trying to get okta groups: {e}')
            raise e

    def get_user_apps(self, user_id: str):
        api_url = f'/api/v1/apps?filter=user.id+eq+"{user_id}"'

        try:
            request, error = async_to_sync(
                self.okta_client.get_request_executor().create_request
            )(method='GET', url=api_url, body={}, headers={}, oauth=False)

            if error:
                logger.error(error)

            response, error = async_to_sync(
                self.okta_client.get_request_executor().execute
            )(request, Application)

            if error:
                logger.error(error)

            apps = []

            for item in response.get_body():
                apps.append(Application(item))

            return apps
        except Exception as e:
            logger.exception(f'error trying to get okta groups: {e}')
            raise e

    async def get_user_apps_async(self, user_id: str):
        api_url = f'/api/v1/apps?filter=user.id+eq+"{user_id}"'

        try:
            (
                request,
                error,
            ) = await self.okta_client.get_request_executor().create_request(
                method='GET', url=api_url, body={}, headers={}, oauth=False
            )

            if error:
                logger.error(error)

            response, error = await self.okta_client.get_request_executor().execute(
                request, Application
            )

            if error:
                logger.error(error)

            apps = []

            for item in response.get_body():
                apps.append(Application(item))

            return apps
        except Exception as e:
            logger.exception(f'error trying to get okta groups: {e}')
            raise e

    def get_users_per_group(self, group_id: str):
        api_url = f'/api/v1/groups/{group_id}/users'

        try:
            request, error = async_to_sync(
                self.okta_client.get_request_executor().create_request
            )(method='GET', url=api_url, body={}, headers={}, oauth=False)

            if error:
                logger.error(error)

            response, error = async_to_sync(
                self.okta_client.get_request_executor().execute
            )(request, User)

            if error:
                logger.error(error)

            users = []

            for item in response.get_body():
                users.append(User(item))

            return users
        except Exception as e:
            logger.exception(f'error trying to get okta users by group {group_id}: {e}')
            raise e

    def set_user_password(self, user_id: str, password: str):
        api_url = f'/api/v1/users/{user_id}'

        request_body = {'credentials': {'password': {'value': password}}}

        try:
            request, err = async_to_sync(
                self.okta_client.get_request_executor().create_request
            )(method='PUT', url=api_url, body=request_body, headers={}, oauth=False)

            if err:
                logger.error(err)
                raise err

            response, error = async_to_sync(
                self.okta_client.get_request_executor().execute
            )(request, User)

            if err:
                logger.error(err)
                raise err

        except Exception as e:
            logger.exception(f'error trying to set password for user {user_id}: {e}')
            raise e
