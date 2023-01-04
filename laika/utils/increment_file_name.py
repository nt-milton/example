import re

from laika.utils.regex import FILE_NAME_EXTENSION


def increment_file_name(reference_model, file_name, filters):
    file_counter = 1
    file_ext = re.search(FILE_NAME_EXTENSION, file_name).group(0)
    file_name_without_ext = re.sub(FILE_NAME_EXTENSION, '', file_name)
    new_file_name = file_name
    while True:
        if not reference_model.objects.filter(name=new_file_name, **filters):
            break
        new_file_name = f'{file_name_without_ext}({file_counter}){file_ext}'
        file_counter += 1
    return new_file_name
