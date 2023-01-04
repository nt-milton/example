from django.urls import path

import policy.views

app_name = 'policy'
urlpatterns = [
    path('document', policy.views.save_document, name='save_document'),
    path(
        '<uuid:policy_id>/export',
        policy.views.export_policy_document,
        name='export_policy_document',
    ),
    path(
        '<uuid:policy_id>/published',
        policy.views.published_policy_document,
        name='published_policy_document',
    ),
]
