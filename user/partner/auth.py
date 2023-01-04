from typing import Callable

from django.shortcuts import redirect

from user.models import PartnerType, User

PARTNER_LOGIN = '/partner/login'


def is_partner(user: User) -> bool:
    return user.is_authenticated and user.role == 'Partner' and not user.is_staff


def is_pentest_partner(user: User) -> bool:
    return is_partner(user) and user.partners.filter(type=PartnerType.PENTEST).exists()


def build_partner_login(view, predicate: Callable[[User], bool]):
    def validated_function(request, **kwargs):
        if not predicate(request.user):
            return redirect(PARTNER_LOGIN)
        return view(request, **kwargs)

    return validated_function


def partner_login(view):
    return build_partner_login(view, is_partner)


def pentest_partner_login(view):
    return build_partner_login(view, is_pentest_partner)
