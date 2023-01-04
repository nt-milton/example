import os

from django.core.files import File

from seeder.models import SeedProfile

template_seed_file_path = f'{os.path.dirname(__file__)}/resources/template_seed.zip'


def create_seed_profiles():
    file_to_seed = File(open(template_seed_file_path, 'rb'))
    seed_one = SeedProfile.objects.create(
        name='[Playbooks] HIPAA Documents',
        is_visible=True,
        content_description='Playbooks related document templates specific to HIPAA.',
        file=file_to_seed,
    )

    seed_two = SeedProfile.objects.create(
        name='[Playbooks] SOC Documents',
        is_visible=False,
        content_description='Playbooks related document templates specific to SOC.',
        file=file_to_seed,
    )

    return [seed_one, seed_two]
