from typing import Optional

from django.contrib.auth.backends import BaseBackend

from laika.backends.base import backend_authenticate
from laika.settings import AUDITS_BACKEND
from user.models import User


class AuditAuthenticationBackend(BaseBackend):
    BACKEND = AUDITS_BACKEND

    def authenticate(self, request, **kwargs) -> Optional[User]:
        return backend_authenticate(self.BACKEND, **kwargs)
