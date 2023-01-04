# Generated by Django 3.1.6 on 2021-06-17 16:46

from django.db import migrations

from organization.models import (
    ONBOARDING_SETUP_STEP,
    SEED_RELEVANT_DOCUMENTS,
    SELECT_CERTIFICATIONS,
)

NECCESARY_NUMBER_TO_COMPLETE_FLAGS = len(ONBOARDING_SETUP_STEP) - 2


def are_previous_steps_completed(steps):
    [first, second, third] = steps
    return first.completed and second.completed and third.completed


def create_missing_flags(model, onboarding, should_be_complete):
    model.objects.create(
        onboarding=onboarding, name=SELECT_CERTIFICATIONS, completed=should_be_complete
    )
    model.objects.create(
        onboarding=onboarding,
        name=SEED_RELEVANT_DOCUMENTS,
        completed=should_be_complete,
    )


def fill_missing_flags(apps, schema_editor):
    onboarding_model = apps.get_model('organization', 'onboarding')
    onboardings = onboarding_model.objects.all()
    onboarding_setup_step_model = apps.get_model('organization', 'onboardingsetupstep')

    for onboarding in onboardings:
        steps = onboarding.setup_steps.all()
        if len(steps) == NECCESARY_NUMBER_TO_COMPLETE_FLAGS:
            should_be_complete = are_previous_steps_completed(steps)
            create_missing_flags(
                model=onboarding_setup_step_model,
                onboarding=onboarding,
                should_be_complete=should_be_complete,
            )


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0043_add_new_setup_steps'),
    ]

    operations = [migrations.RunPython(fill_missing_flags)]
