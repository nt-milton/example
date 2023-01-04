from typing import Optional

from django.contrib.auth.backends import BaseBackend

from laika.backends.base import backend_authenticate
from laika.settings import CONCIERGE_BACKEND
from user.models import User


class ConciergeAuthenticationBackend(BaseBackend):
    BACKEND = CONCIERGE_BACKEND

    def authenticate(self, request, **kwargs) -> Optional[User]:
        return backend_authenticate(self.BACKEND, **kwargs)
