import logging
from copy import copy

from django.core.files import File

from blueprint.models.training import TrainingBlueprint
from organization.models import Organization
from training.models import Training

logger = logging.getLogger(__name__)


def prescribe(organization: Organization) -> list[str]:
    status_detail = []
    for training_blueprint in TrainingBlueprint.objects.iterator():
        try:
            training_file = File(
                name=training_blueprint.name,
                file=copy(training_blueprint.file_attachment.file),
            )
            new_training, _ = Training.objects.update_or_create(
                organization=organization,
                name=training_blueprint.name,
                defaults={
                    'category': training_blueprint.category,
                    'description': training_blueprint.description,
                    'slides': training_file,
                },
            )

            logger.info(
                f'New training {new_training} created for organization: {organization}'
            )
        except Exception as e:
            error_message = f'Error prescribing {training_blueprint}: {e}'
            status_detail.append(error_message)
            logger.warning(error_message)
    return status_detail
