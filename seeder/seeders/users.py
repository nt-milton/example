import logging

from django.db import transaction

from user.utils.invite_laika_user import invite_user_m

logger = logging.getLogger('seeder')


def seed(organization, workbook):
    status_detail = []
    if 'users' not in workbook.sheetnames:
        return status_detail

    users_sheet = workbook['users']
    invite_from_seeder = True
    for row in users_sheet.iter_rows(min_row=2):
        first_name, last_name, email, role = [c.value for c in row[:4]]
        if not first_name and not last_name and not email:
            continue
        try:
            with transaction.atomic():
                if not first_name or not last_name or not email or not role:
                    status_detail.append(
                        f'Error seeding user with name: {first_name} '
                        f'{last_name}. All fields are required.'
                    )
                    continue

                input = {
                    'email': email,
                    'role': role,
                    'first_name': first_name,
                    'last_name': last_name,
                    'organization_id': organization.id,
                }

                result = invite_user_m(None, input, invite_from_seeder)
                if result.get('data'):
                    logger.info(f'Invitation sent to user with email {email}')

        except Exception as e:
            logger.warning(f'Seed user with email: {email} has failed. {e}')
            status_detail.append(
                f'Error seeding user with name: {first_name} {last_name}. Error: {e}'
            )
    return status_detail
