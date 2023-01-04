from django.urls import path

from .views import (
    activate_user,
    export_officers,
    export_team,
    export_template,
    get_magic_link,
    get_okta_temporary_password,
    get_one_time_token,
    get_otp_from_magic_link,
    get_user_idp,
    get_user_status,
)

app_name = 'user'
urlpatterns = [
    path('export_officers', export_officers, name='export_officers'),
    path('team/<uuid:team_id>/export', export_team, name='export_team'),
    path('export/template', export_template, name='export_template'),
    path('user_idp', get_user_idp, name='get_user_idp'),
    path('magic_link/<str:token>', get_magic_link, name='get_magic_link'),
    path(
        'get_otp_from_magic_link',
        get_otp_from_magic_link,
        name='get_otp_from_magic_link',
    ),
    path(
        'okta_one_time_token',
        get_one_time_token,
        name='get_one_time_token',
    ),
    path(
        'get_okta_temporary_password',
        get_okta_temporary_password,
        name='get_okta_temporary_password',
    ),
    path('activate_user', activate_user, name='activate_user'),
    path('get_user_status', get_user_status, name='get_user_status'),
]
