"""
Django settings for laika project.

Generated by 'django-admin startproject' using Django 3.0.2.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""

import logging
import os
import sys
from typing import Any, Dict

from corsheaders.defaults import default_headers

from .aws.secrets import get_secret
from .constants import EXCEL_PLUGIN_REGEX, LAIKA_SUB_DOMAINS_REGEX, LOCALHOST_REGEX

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_ROOT = 'files/'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/
ENVIRONMENT = os.getenv("ENVIRONMENT")
DJANGO_SETTINGS = get_secret(f'{ENVIRONMENT}/laika-app/settings')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = DJANGO_SETTINGS.get('SECRET_KEY')

# Concierge channel
CONCIERGE_SLACK_CHANNEL = (
    '#concierge-requests' if ENVIRONMENT == 'prod' else '#concierge-tests'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = (
    True
    if DJANGO_SETTINGS.get('DEBUG') in [True, 'True'] and ENVIRONMENT == 'local'
    else False
)
if DEBUG:
    logging.error('DEBUG is enabled!')

ORIGIN_LOCALHOST = [
    'http://localhost:3000',
    'http://localhost:3001',
    'http://localhost:3006',
    'https://localhost:3002',
]
ORIGIN_DEV = [
    'https://dev.heylaika.com',
    'https://cep-dev.heylaika.com',
    'https://audit-dev.heylaika.com',
    'https://polaris-dev.heylaika.com',
    'https://development-magic-excel-plugin.s3.amazonaws.com',
    'https://sjm-000.heylaika.com',
]
ORIGIN_STAGING = [
    'https://staging.heylaika.com',
    'https://cep-staging.heylaika.com',
    'https://audit-staging.heylaika.com',
    'https://polaris-staging.heylaika.com',
    'https://staging-magic-excel-plugin.s3.amazonaws.com',
]

ORIGIN_RC = [
    'https://lw-rc.heylaika.com',
    'https://audit-rc.heylaika.com',
    'https://polaris-rc.heylaika.com',
    'https://rc-magic-excel-plugin.s3.amazonaws.com',
]

ORIGIN_PROD = [
    'https://app.heylaika.com',
    'https://cep.heylaika.com',
    'https://audit.heylaika.com',
    'https://polaris.heylaika.com',
    'https://magic-excel-plugin.heylaika.com',
]

ORIGIN = ORIGIN_DEV + ORIGIN_STAGING + ORIGIN_RC + ORIGIN_PROD

# TODO: Replace this with valid hosts - TR-234
ALLOWED_HOSTS = ['*']

SLACK_TOKEN = DJANGO_SETTINGS.get('SLACK_TOKEN')

# TODO: Remove hardcoded aws region from code
EMAIL_BACKEND = 'django_ses.SESBackend'

AWS_REGION = 'us-east-1'
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = DJANGO_SETTINGS.get('AWS_STORAGE_BUCKET_NAME')
DOCUMENT_SERVER_URL = DJANGO_SETTINGS.get('DOCUMENT_SERVER_URL')
AWS_CLOUD_SEARCH_URL = DJANGO_SETTINGS.get('AWS_CLOUD_SEARCH_URL')
AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}

AWS_DEFAULT_ACL = None
AWS_STATIC_LOCATION = 'static'
STATICFILES_STORAGE = 'laika.storage.StaticStorage'
STATIC_URL = 'https://%s/%s/' % (AWS_S3_CUSTOM_DOMAIN, AWS_STATIC_LOCATION)

TINYMCE_API_KEY = DJANGO_SETTINGS.get('TINYMCE_API_KEY')
TINYMCE_JS_URL = (
    f'https://cdn.tiny.cloud/1/{TINYMCE_API_KEY}/tinymce/5.7/tinymce.min.js'
)
TINYMCE_DEFAULT_CONFIG = {
    "height": "320px",
    "width": "960px",
    "menubar": "file edit view insert format tools table help",
    "plugins": (
        "advlist autolink lists link image charmap print preview anchor searchreplace"
        " visualblocks code fullscreen insertdatetime media table paste code help"
        " wordcount spellchecker"
    ),
    "toolbar": (
        "undo redo | bold italic underline strikethrough | fontselect fontsizeselect"
        " formatselect | alignleft aligncenter alignright alignjustify | outdent indent"
        " |  numlist bullist checklist | forecolor backcolor casechange permanentpen"
        " formatpainter removeformat | pagebreak | charmap emoticons | fullscreen "
        " preview save print | insertfile image media pageembed template link anchor"
        " codesample | a11ycheck ltr rtl | showcomments addcomment code"
    ),
    "custom_undo_redo_levels": 10,
    "language": "es_ES",
}

AWS_PUBLIC_MEDIA_LOCATION = 'media/public'
DEFAULT_FILE_STORAGE = 'laika.storage.PublicMediaStorage'

AWS_PRIVATE_MEDIA_LOCATION = 'media/private'
PRIVATE_FILE_STORAGE = 'laika.storage.PrivateMediaStorage'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'laika/static'),
]

GRAPHENE = {
    'SCHEMA': 'laika.schema.schema',
    'MIDDLEWARE': [
        'laika.middlewares.LoadersMiddleware.LoaderMiddleware',
        'laika.middlewares.SQLErrorsMidleware.SQLErrorMiddleware',
        'laika.middlewares.GraphQLIntrospectionMiddleware.DisableIntrospectionMiddleware',
    ],
}

CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-amz-user-agent',
]

CORS_ORIGIN_ALLOW_ALL = False

CORS_ORIGIN_REGEX_WHITELIST = [
    LOCALHOST_REGEX,
    LAIKA_SUB_DOMAINS_REGEX,
    EXCEL_PLUGIN_REGEX,
]

AUTH_USER_MODEL = 'user.User'
# Application definition
INSTALLED_APPS = [
    'population.apps.PopulationConfig',
    'fieldwork.apps.FieldworkConfig',
    'action_item.apps.ActionItemConfig',
    'audit.apps.AuditConfig',
    'auditee.apps.AuditeeConfig',
    'auditor.apps.AuditorConfig',
    'coupon.apps.CouponConfig',
    'comment.apps.CommentConfig',
    'alert.apps.AlertConfig',
    'announcement.apps.AnnouncementsConfig',
    'report.apps.ReportConfig',
    'dashboard.apps.DashboardConfig',
    'integration.apps.IntegrationConfig',
    'objects.apps.ObjectsConfig',
    'certification.apps.CertificationConfig',
    'dataroom.apps.DataroomConfig',
    'library.apps.LibraryConfig',
    'feature.apps.FeatureConfig',
    'evidence.apps.EvidenceConfig',
    'control.apps.ControlConfig',
    'search.apps.SearchConfig',
    'program.apps.ProgramConfig',
    'seeder.apps.SeederConfig',
    'concierge.apps.ConciergeConfig',
    'vendor.apps.VendorConfig',
    'user.apps.UserConfig',
    'address.apps.AddressConfig',
    'organization.apps.OrganizationConfig',
    'training.apps.TrainingConfig',
    'policy.apps.PolicyConfig',
    'tag.apps.TagConfig',
    'drive.apps.DriveConfig',
    'link.apps.LinkConfig',
    'monitor.apps.MonitorConfig',
    'sso.apps.SsoConfig',
    'blueprint.apps.BlueprintConfig',
    'pentest.apps.PentestConfig',
    'access_review.apps.AccessReviewConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.postgres',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'graphene_django',
    'corsheaders',
    'storages',
    'reversion',
    'django_celery_results',
    'django_celery_beat',
    'channels',
    'tinymce',
    'ddtrace.contrib.django',
]

MIDDLEWARE = [
    'reversion.middleware.RevisionMiddleware',
    'log_request_id.middleware.RequestIDMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_session_timeout.middleware.SessionTimeoutMiddleware',
    'laika.middlewares.APIRequestMiddleware.APIRequestMiddleware',
]

LAIKA_BACKEND = 'laika.auth.AuthenticationBackend'
AUDITS_BACKEND = 'laika.auth.AuditAuthenticationBackend'
CONCIERGE_BACKEND = 'laika.auth.ConciergeAuthenticationBackend'
DJANGO_BACKEND = 'django.contrib.auth.backends.ModelBackend'

AUTHENTICATION_BACKENDS = [
    AUDITS_BACKEND,
    CONCIERGE_BACKEND,
    LAIKA_BACKEND,
    DJANGO_BACKEND,
]

ROOT_URLCONF = 'laika.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'auditor/report/templates'),
            os.path.join(BASE_DIR, 'auditor/automated_testing/templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

SSO_DEFAULT_DOMAINS = DJANGO_SETTINGS.get('SSO_DEFAULT_DOMAINS')

LOGIN_API_KEY = DJANGO_SETTINGS.get('LOGIN_API_KEY')

OKTA_DOMAIN_URL = DJANGO_SETTINGS.get('OKTA_DOMAIN_URL')
OKTA_ISSUER = DJANGO_SETTINGS.get('OKTA_ISSUER')
OKTA_API_KEY = DJANGO_SETTINGS.get('OKTA_API_KEY')
OKTA_CLIENT_ID = DJANGO_SETTINGS.get('OKTA_CLIENT_ID')
OKTA_AUDIENCE = DJANGO_SETTINGS.get('OKTA_AUDIENCE')
OKTA_SERVER_ID = DJANGO_SETTINGS.get('OKTA_SERVER_ID')
OKTA_CLIENT_SECRET = DJANGO_SETTINGS.get('OKTA_CLIENT_SECRET')
OKTA_AUTH = {
    'ORG_URL': OKTA_DOMAIN_URL,
    'ISSUER': OKTA_ISSUER,
    'CLIENT_ID': OKTA_CLIENT_ID,
    'CLIENT_SECRET': OKTA_CLIENT_SECRET,
    'SCOPES': 'openid profile email groups',
    'REDIRECT_URI': 'http://localhost:8000/accounts/oauth2/callback',
    'LOGIN_REDIRECT_URL': '/',  # default
    'CACHE_PREFIX': 'okta',  # default
    'CACHE_ALIAS': 'default',  # default
    'PUBLIC_NAMED_URLS': (),  # default
    'PUBLIC_URLS': (),  # default
    'USE_USERNAME': False,  # default
}

WSGI_APPLICATION = 'laika.wsgi.application'
ASGI_APPLICATION = 'laika.asgi.application'

# Session Management
SESSION_EXPIRE_SECONDS = 900
SESSION_COOKIE_AGE = 900
SESSION_TIMEOUT_REDIRECT = '/admin'
SESSION_EXPIRE_AFTER_LAST_ACTIVITY = True

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases
TEST_DATABASE = {
    'ENGINE': 'django.db.backends.sqlite3',
    'TEST_CHARSET': 'UTF8',
    'NAME': ':memory:',
    'TEST_NAME': ':memory:',
    'OPTIONS': {
        # https://docs.djangoproject.com/en/3.0/ref/databases/#database-is-locked-errors
        'timeout': 20,
    },
}

DATABASE = get_secret(f'{ENVIRONMENT}/laika-app/db')
DATABASE_READONLY = get_secret(f'{ENVIRONMENT}/laika-app/db-readonly')
UNDER_TEST = 'pytest' in sys.argv[0]
DATABASES = {
    'default': TEST_DATABASE if UNDER_TEST else DATABASE,
    'query_monitor': TEST_DATABASE if UNDER_TEST else DATABASE_READONLY,
}

REQUEST_ID_RESPONSE_HEADER = "X-Request-Id"
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_id': {'()': 'laika.utils.logging.EdasSpanIdFilter'},
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {request_id} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'filters': ['request_id'],
            'formatter': 'verbose',
        },
        'console_debug': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': os.getenv('LAIKA_LOG_LEVEL', 'INFO'),
        },
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': [
                # Enable this for logging SQL queries
                # 'console_debug'
            ],
        },
    },
}

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_URL = '/static/'

DATA_UPLOAD_MAX_MEMORY_SIZE = 115343360  # 110 Megabytes

SEARCH_THRESHOLD = 0.1

# Celery
CELERY_BROKER_URL = DJANGO_SETTINGS.get('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = 'django-db'

CHANNEL_LAYERS: Dict[str, Dict[str, Any]]
CACHES: Dict[str, Dict[str, Any]]
if ENVIRONMENT == 'local':
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'local-cache',
        },
        'redis': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': f'redis://redis:6379/1',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [
                    (
                        DJANGO_SETTINGS.get('REDIS_ENDPOINT'),
                        DJANGO_SETTINGS.get('REDIS_PORT'),
                    )
                ],
            },
        },
    }
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': f'redis://{DJANGO_SETTINGS.get("REDIS_ENDPOINT")}/1',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
            },
        }
    }

# IFRAME configuration
CSP_RULE = (
    'frame-ancestors localhost:*'
    if ENVIRONMENT == 'local'
    else 'frame-ancestors *.heylaika.com'
)

LAIKA_WEB_REDIRECT = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')

LAIKA_CONCIERGE_REDIRECT = DJANGO_SETTINGS.get('LAIKA_CEP_REDIRECT')

# SILENCED SYSTEM CHECKS
SILENCED_SYSTEM_CHECKS = ["auth.W004"]

NO_REPLY_EMAIL = 'Laika | Alerts <no-reply@heylaika.com>'

INVITE_NO_REPLY_EMAIL = 'Laika <no-reply@heylaika.com>'

MAIN_ARCHIVE_MAIL = 'emailarchive@heylaika.com'
LAIKA_ADMIN_EMAIL = 'admin@heylaika.com'
LAIKA_APP_ADMIN_EMAIL = 'admin+laikaapp@heylaika.com'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Open Api
OPEN_API_SECRET = DJANGO_SETTINGS.get('LAIKA_API_SECRET_KEY')

# Open AI
OPEN_AI_KEY = DJANGO_SETTINGS.get('OPEN_AI_KEY')
