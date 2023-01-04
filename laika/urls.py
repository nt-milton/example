"""laika URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView

from laika.settings import DEBUG
from monitor.views import (
    DuplicateOrganizationMonitorView,
    GetDryRunResult,
    GetMonitorPlayground,
    RequestDryRun,
)
from user.views import MigratePolarisUsersView

urlpatterns = [
    path('training/', include('training.urls')),
    path('vendor/', include('vendor.urls')),
    path('policy/', include('policy.urls')),
    path('user/', include('user.urls')),
    path('dataroom/', include('dataroom.urls')),
    path('evidence/', include('evidence.urls')),
    path('library/', include('library.urls')),
    path('integration/', include('integration.urls')),
    path('drive/', include('drive.urls')),
    path('program/', include('program.urls')),
    path('objects/', include('objects.urls')),
    path('report/', include('report.urls')),
    path('link/', include('link.urls')),
    path('audit/', include('audit.urls')),
    path('monitor/', include('monitor.urls')),
    path('blueprint/', include('blueprint.urls')),
    path(
        'admin/duplicate_monitor',
        DuplicateOrganizationMonitorView,
        name='clone_monitor',
    ),
    path('admin/monitor/dry_run', GetDryRunResult, name='get_dry_run_result'),
    path(
        'admin/monitor/monitor_playground',
        GetMonitorPlayground,
        name='monitor_playground',
    ),
    path('admin/monitor/request_dry_run', RequestDryRun, name='request_dry_run'),
    path('admin/', admin.site.urls),
    path('concierge/', include('concierge.urls')),
    path('fieldwork/', include('fieldwork.urls')),
    path('graphql', csrf_exempt(GraphQLView.as_view(graphiql=DEBUG))),
    path('graphql-api', csrf_exempt(GraphQLView.as_view(graphiql=True))),
    path('tinymce/', include('tinymce.urls')),
    path(
        'admin/user/migrate_polaris_users',
        MigratePolarisUsersView.as_view(),
        name='migrate_polaris_users',
    ),
    path('auditor/', include('auditor.urls')),
    path('auditee/', include('auditee.urls')),
    path('population/', include('population.urls')),
    path('partner/', include('user.partner.urls')),
    path('pentest/', include('pentest.urls')),
    path('access-review/', include('access_review.urls')),
    path('organization/', include('organization.urls')),
    path('scim/v2/', include('user.scim.urls')),
]

admin.site.site_header = 'Laika Admin'
admin.site.site_title = 'Laika Admin Portal'
admin.site.index_title = 'Welcome to Laika Portal'
