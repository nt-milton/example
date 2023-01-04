import logging

from blueprint.models.team import TeamBlueprint
from organization.models import Organization
from user.models import Team

logger = logging.getLogger(__name__)


def prescribe(organization: Organization) -> list[str]:
    status_detail = []
    for team_blueprint in TeamBlueprint.objects.iterator():
        try:
            new_team, _ = Team.objects.update_or_create(
                organization=organization,
                name=team_blueprint.name,
                defaults={
                    'description': team_blueprint.description,
                    'charter': team_blueprint.charter,
                },
            )

            logger.info(f'New team {new_team} created for organization: {organization}')
        except Exception as e:
            error_message = f'Error prescribing {team_blueprint}: {e}'
            status_detail.append(error_message)
            logger.warning(error_message)
    return status_detail
