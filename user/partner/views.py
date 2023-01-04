from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from user.partner.auth import (
    PARTNER_LOGIN,
    is_partner,
    is_pentest_partner,
    partner_login,
)

PARTNER_HOME = '/partner/'


@require_GET
@partner_login
def index_view(request: HttpRequest) -> HttpResponse:
    if is_pentest_partner(request.user):
        return redirect('/pentest/')
    # Pentest is the only available feature
    # informative message for no-pentest partner
    return render(request, 'partner/no_features.html')


@require_GET
def login_view(request: HttpRequest) -> HttpResponse:
    user = getattr(request, 'user', None)
    if user and is_partner(user):
        return redirect(PARTNER_HOME)
    return render(request, 'partner/login.html')


@require_POST
def auth_view(request: HttpRequest) -> HttpResponse:
    user = authenticate(
        username=request.POST.get('username'), password=request.POST.get('password')
    )
    if user is not None:
        login(request, user)
        return redirect(PARTNER_HOME)
    else:
        return render(request, 'partner/login.html', {'error': True})


@require_GET
@partner_login
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect(PARTNER_LOGIN)
