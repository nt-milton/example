from django.urls import path


def get_file_name_without_ext(file_name):
    return path.basename(path.splitext(file_name)[0])
