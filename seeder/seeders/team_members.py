import logging

from user.models import Team, TeamMember, User

logger = logging.getLogger('seeder')


def seed(organization, workbook):
    status_detail = []
    if 'team_members' not in workbook.sheetnames:
        return status_detail

    members_sheet = workbook['team_members']
    for row in members_sheet.iter_rows(min_row=2):
        role, phone, user_email, team_name = [c.value for c in row[:4]]
        if not role and not phone and not user_email and not team_name:
            continue
        try:
            if not role or not phone or not user_email or not team_name:
                status_detail.append(
                    'Error seeding team member. Fields: role, phone, '
                    'user_email and team_name are required.'
                )
                continue

            user = User.objects.get(email=user_email, organization_id=organization.id)

            team = Team.objects.get(name=team_name, organization_id=organization.id)

            TeamMember.objects.update_or_create(
                user=user,
                team=team,
                defaults={
                    'role': role,
                    'phone': phone,
                },
            )
        except Exception as e:
            logger.warning(
                f'Team member with email: {user_email}                 has failed. {e}'
            )
            status_detail.append(
                f'Error seeding team member with email: {user_email}. Error: {e}'
            )
    return status_detail
