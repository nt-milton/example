import logging

from user.models import Team

logger = logging.getLogger('seeder')


def seed(organization, workbook):
    status_detail = []
    if 'teams' not in workbook.sheetnames:
        return status_detail

    teams_sheet = workbook['teams']
    for row in teams_sheet.iter_rows(min_row=2):
        name, description, charter, notes = [c.value for c in row[:4]]
        if not name and not description:
            continue
        try:
            # Name and description are required
            if not name or not description:
                status_detail.append(
                    'Error seeding team. Fields: name and description are required.'
                )
                continue

            Team.objects.update_or_create(
                organization=organization,
                name=name,
                defaults={
                    'description': description,
                    'notes': notes or '',
                    'charter': charter or '',
                },
            )
        except Exception as e:
            logger.warn(f'Team with name: {name} has failed. {e}')
            status_detail.append(f'Error seeding Team with name: {name}. Error: {e}')
    return status_detail
