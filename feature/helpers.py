from feature.models import Flag


def create_or_enable_flag(organization, flag_name):
    flag, _ = Flag.objects.update_or_create(
        name=flag_name, organization=organization, defaults={'is_enabled': True}
    )
