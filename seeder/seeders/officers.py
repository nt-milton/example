import logging

from user.models import Officer, User

logger = logging.getLogger('seeder')


def seed(organization, workbook):
    status_detail = []
    if 'officers' not in workbook.sheetnames:
        return status_detail

    officers_sheet = workbook['officers']
    for row in officers_sheet.iter_rows(min_row=2):
        name, description, user_email = [c.value for c in row[:3]]
        if not name and not description:
            continue
        try:
            # Name and description are required
            if not name or not description:
                status_detail.append(
                    f'Error seeding officer with name: {name}'
                    'Fields: name and description are required.'
                )
                continue

            user = None
            if user_email:
                user = User.objects.get(
                    email=user_email, organization_id=organization.id
                )
            Officer.objects.update_or_create(
                organization=organization,
                name=name,
                defaults={
                    'description': description,
                    'user': user,
                },
            )
        except Exception as e:
            logger.warn(f'Officer with name: {name} has failed. {e}')
            status_detail.append(f'Error seeding officer with name: {name}. Error: {e}')
    return status_detail
