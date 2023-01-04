import logging

from django.core.files import File

from training.models import Training

logger = logging.getLogger('seeder')


def seed(organization, zip_obj, workbook):
    status_detail = []
    if 'trainings' not in workbook.sheetnames:
        return status_detail

    trainings_sheet = workbook['trainings']
    for row in trainings_sheet.iter_rows(min_row=2):
        logger.info('Processing trainings')
        name, category, description = [c.value for c in row[:3]]
        if not name and not category and not description:
            continue
        try:
            # Training file should have the training name
            if not name or not category or not description:
                status_detail.append(
                    f'Error seeding training with name: {name}, '
                    f'category: {category} and description: {description}. '
                    'All fields are required.'
                )
                continue
            with zip_obj.open(f'trainings/{name}.pdf') as training_file:
                slides = File(name=name + '.pdf', file=training_file)
                Training.objects.update_or_create(
                    organization=organization,
                    name=name,
                    defaults={
                        'category': category,
                        'description': description,
                        'slides': slides,
                    },
                )
        except Exception as e:
            logger.warning(f'Training with name: {name} has failed. {e}')
            status_detail.append(
                f'Error seeding training with name: {name}. Error: {e}'
            )
    return status_detail
