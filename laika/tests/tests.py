import logging
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser, Group
from django.http import HttpResponse
from okta.exceptions import OktaAPIException

from laika.aws.cognito import COGNITO_KEYS, decode_token
from laika.backends.audits_backend import AuditAuthenticationBackend
from laika.backends.base import authenticate, decode_jwt, get_internal_user
from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.constants import COGNITO, OKTA
from laika.middlewares.APIRequestMiddleware import APIRequestMiddleware
from laika.middlewares.TokenAuthMiddleware import TokenAuthMiddleware
from laika.okta.api import OktaApi
from laika.okta.auth import decode_okta
from laika.settings import (
    AUDITS_BACKEND,
    CONCIERGE_BACKEND,
    DJANGO_SETTINGS,
    LAIKA_BACKEND,
)
from laika.utils.dates import now_date
from organization.tests import create_organization
from user.models import Auditor, Concierge, User

logger = logging.getLogger(__name__)

COGNITO_TOKEN = (
    'eyJraWQiOiJVSngycWprUWZFbFgxM1AybHdOK2dSaGJ4SnFoNmVwUlM4aHlYcjM2Tnk4PSIs'
    'ImFsZyI6IlJTMjU2In0.eyJzdWIiOiI5N2YwNDEzYi04NzVhLTRjNTEtYTM5OS00NmIyMWM3'
    'OWZmMWQiLCJjb2duaXRvOmdyb3VwcyI6WyJTdXBlckFkbWluIl0sImVtYWlsX3ZlcmlmaWVk'
    'Ijp0cnVlLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAudXMtZWFzdC0xLmFtYXpvbmF3'
    'cy5jb21cL3VzLWVhc3QtMV9aa2lqT0lieHoiLCJjb2duaXRvOnVzZXJuYW1lIjoiOTdmMDQx'
    'M2ItODc1YS00YzUxLWEzOTktNDZiMjFjNzlmZjFkIiwiY3VzdG9tOm9yZ2FuaXphdGlvbk5h'
    'bWUiOiJMYWlrYSBEZXYiLCJjdXN0b206b3JnYW5pemF0aW9uSWQiOiIzMWYzZDU3ZS1jMWRh'
    'LTQwNGMtYjQ3OS0yZDM1MGM0NzZmZmYiLCJjdXN0b206b3JnYW5pemF0aW9uVGllciI6IlBS'
    'RU1JVU0iLCJhdWQiOiI1b3F0N3N0aW5kcjRmMTdxYm9mMG9tY2VvbCIsImV2ZW50X2lkIjoi'
    'Y2Q5NWVjOWItNTIwMS00MTUzLWI2MjctNjAwMDI1OTQwNWE1IiwidG9rZW5fdXNlIjoiaWQi'
    'LCJhdXRoX3RpbWUiOjE1OTk2NjU5NzEsIm5hbWUiOiJsYWlrYWFwcCIsImV4cCI6MTU5OTc0'
    'ODkxMCwiaWF0IjoxNTk5NzQ1MzEwLCJmYW1pbHlfbmFtZSI6ImFkbWluIiwiZW1haWwiOiJh'
    'ZG1pbitsYWlrYWFwcCtoZXlsYWlrYWRldkBoZXlsYWlrYS5jb20ifQ.RTEJLhVail4GvOLFQ'
    'xsXRpK4O4R4LgK3HhnMtdwBUqPBvGtAyZcFr5WtNrN2DDJGxGw8esYucvn2xldwbsUFDK1X3'
    'eFZYMi-QJjIOFhy6plewLdYZd4G8Sz9z6q8PUGmCt3grKVXLTDgUvVqHDXsVSNFSnQ_--AJL'
    'EsNy1UHrNkDBkNbuodlArUmQMuGDAWnjydkWFtXxvQhv6I-kVzD3sfb9WjHby-9vD9ZLavMK'
    'tSqdstC6XFdXS5as4MjK05t4zDWaMUMBO0lVeL-am7_jGB8t260bEtImmWOXnzKhTQCEZ5BX'
    'F9DWmuIJXzfDNqFAW6vTqUMVcCGdwCd_joCjQ'
)

bad_token = (
    'eyJraWQiOiJcL0hZSzNtSFJvaEk2QkE5bDZaMWpUWUN4Zm1cL0NybEVuQWpuQW5Ia1VxdW89'
    'IiwiYWxnIjoiUlMyNTYifQ.eyJzdWIiOiI3MzBjZGViZi00OWRmLTQyNmUtYTkzOS05ZjhkN'
    'zlhYmRmZWQiLCJjb2duaXRvOmdyb3VwcyI6WyJPcmdhbml6YXRpb25BZG1pbiJdLCJlbWFpb'
    'F92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6XC9cL2NvZ25pdG8taWRwLnVzLWVhc3QtM'
    'S5hbWF6b25hd3MuY29tXC91cy1lYXN0LTFfMndaTkpjN2hvIiwiY29nbml0bzp1c2VybmFtZ'
    'SI6IjczMGNkZWJmLTQ5ZGYtNDI2ZS1hOTM5LTlmOGQ3OWFiZGZlZCIsImN1c3RvbTpvcmdhb'
    'ml6YXRpb25JZCI6IjQ2ZDJiMzQ5LTBmZmQtNDAwZi1hNWE3LTFkNDY5MzE1NjdmOCIsImF1Z'
    'CI6IjJmYTdncnVqNGRrcG5wc21xb2lpcjJua3AiLCJldmVudF9pZCI6IjkyMjU1ODgwLTYxN'
    'zYtNGJmYy1iODhmLWYzZGQxNWM0ZDYwMCIsInRva2VuX3VzZSI6ImlkIiwiYXV0aF90aW1lI'
    'joxNTk5NzcxNTc3LCJuYW1lIjoic2FtIiwiZXhwIjoxNTk5Nzc1MTc4LCJpYXQiOjE1OTk3N'
    'zE1NzgsImZhbWlseV9uYW1lIjoic3RhbmRhcmQiLCJlbWFpbCI6InNhbStzdGFuZGFyZEBoZ'
    'XlsYWlrYS5jb20ifQ.JyNWERn8O7XoK_e-qyyVsWij9DnPQwng-8uoOF8na2Fc5lF7AgHNgQ'
    'LWGrMdbV8MonSc8LxHblRq9Av59qxtuvHLE0M_EPCFu5Wlp5oQe99aO-RtbHY9qSiURxeUQ4'
    '1Fp0-0uZ8ZeGkCLgezEvI4K9kxW8hIccVM1SfzkuGnciDeAXdSai2RM4sUpwQteChqS4Sio2'
    'fKHA9jfZp8qnMmEEID1S-uhsuWGhqBo4Jvkfir-Rpu2i5RdksQv8Hwg2KyVcSZNOm7-y5jeM'
    'G30-SAS8rtwVuKPk81kJXmvM2wq25atLbJURVzVBIKV8Kr4nzxlFQ4KH98v8T3KdcdKSlMIA'
)

OKTA_TOKEN = (
    'eyJraWQiOiJrQTEzbzFxNE1GQlFQNFJSSGRtRzVORTBsblFZVXYzREhad2VMNTZXT3F3Iiw'
    'iYWxnIjoiUlMyNTYifQ.eyJzdWIiOiIwMHUxeHE5em1hZVhWVzltazVkNyIsIm5hbWUiOiJ'
    'NYXRpYXMgUnViaW4iLCJlbWFpbCI6Im1hdGlhcy5ydWJpbkB2aW4ubGkiLCJ2ZXIiOjEsIm'
    'lzcyI6Imh0dHBzOi8vbGFpa2Eub2t0YS5jb20iLCJhdWQiOiIwb2ExM25sZHhpNG0xSUdRd'
    'TVkNyIsImlhdCI6MTYzODM5OTg4MiwiZXhwIjoxNjM4NDAzNDgyLCJqdGkiOiJJRC5NakpT'
    'SXhQbTdzWkRyZ050VlNYVmM3Wjhhdi1xVXJFenFSOEpXV01UMHUwIiwiYW1yIjpbInB3ZCJ'
    'dLCJpZHAiOiIwb2ExdDF0bHlmMWhTM0NTNTVkNyIsIm5vbmNlIjoiNTFHZVBUc3dybSIsIn'
    'ByZWZlcnJlZF91c2VybmFtZSI6Im1hdGlhcy5ydWJpbkB2aW4ubGkiLCJhdXRoX3RpbWUiO'
    'jE2MzgzOTk4ODAsImF0X2hhc2giOiJsUUFNQjdhUXFFTEVJWnNBdnJDb2FBIn0.XIxe1hBT'
    'C5DDE1s5mOO4uvZhqFgbjZh4M1N1hTQLpoRIqnAxsYpgAbirfXBTOh3NeiHi4ISm91tPS4z'
    'aThkJjntES4jH1kERSOSKLyhwCxtJ-ri-4Qf89XH8wH3Jx0gdJ3I34qsp9ulWP-eUIehmm4'
    'o3rQQFfRPN-EWxgflzbd9nAAYL-a6h2lN5kJRdq0fUbFglksNGiKt-fl3rAwpcM0DV47mPD'
    '-GARRrOlMbuCVIPQ5Of1S0tvatpSv1GvNcUXkUO9BmcYkp81OI0PrEmBj3_cdswHx0ox-8j'
    'kMYOpmran0QBlS-MMdIfvE8e0DdtC_selBrJ2mwJlc1orEjLXQ'
)

AZURE_TOKEN = (
    'eyJraWQiOiIyeTNjYkUwejh4Q0k1RFV1WU9NVkFsTlRpVFJ3dWxNWmFNSGhzdTJhZV9nIiwi'
    'YWxnIjoiUlMyNTYifQ.eyJzdWIiOiIwMHUxMTYwYm11M3M2UDByODVkNyIsIm5hbWUiOiJEZ'
    'XYgTGFpa2EiLCJlbWFpbCI6ImRldkBoZXlsYWlrYS5jb20iLCJ2ZXIiOjEsImlzcyI6Imh0d'
    'HBzOi8vbGFpa2Eub2t0YS5jb20iLCJhdWQiOiIwb2ExM25sZHhpNG0xSUdRdTVkNyIsImlhd'
    'CI6MTYyNjcwNzQ5MiwiZXhwIjoxNjI2NzExMDkyLCJqdGkiOiJJRC5zd3pJaTRRM0pwTmJ3S'
    'jFZMzlHS0xqQk5oX2RBd0EteXFFcVhQdEFGRVM0IiwiYW1yIjpbInB3ZCIsIm90cCIsIm1mY'
    'SJdLCJpZHAiOiIwb2ExNjI1c283UWVCTTNIZjVkNyIsIm5vbmNlIjoiNTFHZVBUc3dybSIsI'
    'nByZWZlcnJlZF91c2VybmFtZSI6ImRldkBoZXlsYWlrYS5jb20iLCJhdXRoX3RpbWUiOjE2M'
    'jY2OTg1OTksImF0X2hhc2giOiJUenJSRU9NakN2dkc5QWpKdDg1Yl9nIn0.bI6cHmNc_HtEi'
    'SsYHSN7zWr7wcjPEmHU99VwAxNaKXr5nmD7l21z_TYgOKEw6l1ynVQF5yBF55fIKtMac-8lo'
    'VgDmq5v898xWiKH_vbucIw_IO97k_-QEA4Lk8_lBYTtot7hdKWc5AFvoEMGZfRz9dF0XTeHE'
    'JPvicX-utg_rWs2PvU7LhOP1rmojQpCgpVgDUeSFWcSLbvjME59jTjXaaABYbOyFATIdxGpb'
    'LoEkuNaexqrJfkcLr1KvxglxNSdEXGqvlNlpg-wRWHIHAm9yeSQU3h0JGrRrjxsNGAmwcdDz'
    'xuj-m8-UoZKqLXRyEd1wxHYf-nzxSP-gEqou9Z7jw'
)

CONCIERGE_TOKEN = (
    'eyJraWQiOiJVSngycWprUWZFbFgxM1AybHdOK2dSaGJ4SnFoNmVwUlM4aHlYcjM2Tnk4PSI'
    'sImFsZyI6IlJTMjU2In0.eyJzdWIiOiIzZjhiMmM5Ni00ZmJkLTQ1YWMtOTU3Ny0xNjMwNT'
    'Q1ZDE0MWQiLCJjb2duaXRvOmdyb3VwcyI6WyJDb25jaWVyZ2UiXSwiZW1haWxfdmVyaWZpZ'
    'WQiOnRydWUsImlzcyI6Imh0dHBzOlwvXC9jb2duaXRvLWlkcC51cy1lYXN0LTEuYW1hem9u'
    'YXdzLmNvbVwvdXMtZWFzdC0xX1praWpPSWJ4eiIsImNvZ25pdG86dXNlcm5hbWUiOiIzZjh'
    'iMmM5Ni00ZmJkLTQ1YWMtOTU3Ny0xNjMwNTQ1ZDE0MWQiLCJhdWQiOiI1b3F0N3N0aW5kcj'
    'RmMTdxYm9mMG9tY2VvbCIsImV2ZW50X2lkIjoiNTUzNzI2ZDYtMmIwNC00MTQ3LTk0MWYtN'
    'Tk2ZDk5ZjQyMTczIiwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE2MjY4Nzc2OTAs'
    'Im5hbWUiOiJjb25mbHVlbmNlIiwiZXhwIjoxNjI2OTAzMjQyLCJpYXQiOjE2MjY4OTk2NDI'
    'sImZhbWlseV9uYW1lIjoiY3ggdXNlciIsImVtYWlsIjoibG9lbmdyeStjb25mbHVlbmNlLW'
    'N4LWRldkBoZXlsYWlrYS5jb20ifQ.GWLhVayq4qwAEjbUbkhcnjmnKUJA9B5KcvX3BAtoQd'
    'oayaSCJUnd7dLs6zRVfnjnoNj_pE-UzrumAg6moDF7wevs8QvbHh9hyzS1Rda9b7D6swUcE'
    'kJnaRg7fcSq3-dMDl4BJPGprQCsS2nZpZVCTLn3YMQH1VgeMpqG1WdTOPGWaUALiGJM2eSj'
    'dfOwuOErD4RIBCwSwJRlB16qqgCzOX08yeGPdvlCgG-sIbmay5MCSO7kAP6lCXTtIl1ZQM3'
    'lDq3An1b_RbMLTURw__nncsUbdpfoG8o_L9ieocI9cj1ZrXALTXJBjPPJE9MADmtH4beHqO'
    'lQtJx4UmhmWTm0wg'
)

AUDITS_TOKEN = (
    'eyJraWQiOiJVSngycWprUWZFbFgxM1AybHdOK2dSaGJ4SnFoNmVwUlM4aHlYcjM2Tnk4PS'
    'IsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJkMmJjMzQxYS1mM2EwLTQ4NWEtYjIxZi1iMzJk'
    'Njk3NGRiNmEiLCJjb2duaXRvOmdyb3VwcyI6WyJBdWRpdG9yQWRtaW4iXSwiZW1haWxfdm'
    'VyaWZpZWQiOnRydWUsImlzcyI6Imh0dHBzOlwvXC9jb2duaXRvLWlkcC51cy1lYXN0LTEu'
    'YW1hem9uYXdzLmNvbVwvdXMtZWFzdC0xX1praWpPSWJ4eiIsImNvZ25pdG86dXNlcm5hbW'
    'UiOiJkMmJjMzQxYS1mM2EwLTQ4NWEtYjIxZi1iMzJkNjk3NGRiNmEiLCJhdWQiOiI1b3F0'
    'N3N0aW5kcjRmMTdxYm9mMG9tY2VvbCIsImV2ZW50X2lkIjoiMWEwMWVjYWMtNDE5NC00Nj'
    'VmLWI4N2EtZmE4NmUxMDk1YTE5IiwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE2'
    'MjY5MzUxNDEsIm5hbWUiOiJpdm8iLCJleHAiOjE2MjY5Mzg3NDEsImlhdCI6MTYyNjkzNT'
    'E0MSwiZmFtaWx5X25hbWUiOiJhdWRpdG9yYWRtIiwiZW1haWwiOiJpdm9ubmUrYXVkaXRv'
    'cmFkbWluQGhleWxhaWthLmNvbSJ9.bNhe1x92nACfxog9vaF5h4vxKTRhEVvHKK9izJhg6'
    'xYsfLSWWwxy2v_r1TY6M6WwhBbey2OfyOom_UTxu6TUAoVICklirlp1SPNaKAXLJndTpW3'
    '4t-V-0MayjqpTWV_JLjD-_gwYtmte56tMgF-jwjv4nZEiicctC1yMmddfJktrLeMbFFrrf'
    '3Y3zMGllDNHbGIWDNxB3cv76fEMkZc0nuZ0hRkvlcYWOLIXZQFt-i_UGYHMbV4a6LwRHqs'
    'KK-mm8Q2WAdp9Z063YRfvteuNqKUZfsZOys8bVDzi1CNLWaGqe3JveKV9H5we7Nyw5M5zD'
    '3Z05WuF8qTH6T1rCibGfA'
)


AZURE_EMAIL = 'dev@heylaika.com'
CONCIERGE_TOKEN_EMAIL = 'loengry+confluence-cx-dev@heylaika.com'
AUDITS_TOKEN_EMAIL = 'ivonne+auditoradmin@heylaika.com'
COGNITO_TOKEN_EMAIL = 'admin+laikaapp+heylaikadev@heylaika.com'
OKTA_TOKEN_EMAIL = 'matias.rubin@vin.li'
LAIKA_TEST_EMAIL = 'laika+testing@heylaika.com'
SIGNATURE_EXPIRED_EXCEPTION_MESSAGE = 'Signature has expired'
MOCKED_OKTA_USER_ID = '1234'
MOCKED_OKTA_PASSWORD = 'j9w+/AHcJ!=]uR5mMjMk'

OktaApi = OktaApi()


def create_users(graphql_organization, backend, email):
    user = User.objects.create(organization=graphql_organization, email=email)

    if backend in (CONCIERGE_BACKEND, ConciergeAuthenticationBackend):
        user.role = 'Concierge'
        user.save()

        concierge = Concierge(user=user)
        concierge.save()
        assert Concierge.objects.get(user__email=email)

    elif backend in (AUDITS_BACKEND, AuditAuthenticationBackend):
        user.role = 'Auditor'
        user.save()

        auditor = Auditor(user=user)
        auditor.save(is_not_django=True)
        assert Auditor.objects.get(user__email=email)


@database_sync_to_async
def create_async_user(**kwargs):
    return User.objects.create(
        first_name='Test', last_name='User', role='OrganizationViewer', **kwargs
    )


@pytest.mark.skip()
def test_decode_token():
    decoded_token = decode_token(bad_token, verify=False)
    assert 'sam+standard@heylaika.com' == decoded_token['email']


# @pytest.mark.skipif(not COGNITO_KEYS, reason='cognito is down')
@pytest.mark.skip()
def test_verify_token():
    verified_token = decode_token(COGNITO_TOKEN, verify_exp=False)
    assert 'admin+laikaapp+heylaikadev@heylaika.com' == verified_token['email']


# @pytest.mark.skipif(not COGNITO_KEYS, reason='cognito is down')
@pytest.mark.skip()
def test_verify_invalid_token():
    key_id_another_token = jwt.get_unverified_header(COGNITO_TOKEN)['kid']
    mismatch_key = COGNITO_KEYS[key_id_another_token]
    with pytest.raises(jwt.InvalidSignatureError) as excinfo:
        decode_token(bad_token, verify_exp=False, key=mismatch_key)

    assert "Signature verification failed" == str(excinfo.value)


# @pytest.mark.skipif(
#     not COGNITO_KEYS,
#     reason='cognito down'
# )
@pytest.mark.skip()
def test_verify_cognito_token_no_match_key():
    with pytest.raises(jwt.exceptions.InvalidKeyError) as exc_info:
        decode_token(bad_token, verify_exp=False)

    assert 'Token with unexpected key' == str(exc_info.value)


# @pytest.mark.skipif(
#     not COGNITO_KEYS or not OKTA_KEYS,
#     reason='okta/cognito down'
# )
@pytest.mark.skip()
def test_verify_token_no_match_key():
    with pytest.raises(jwt.exceptions.InvalidKeyError) as exc_info:
        decode_jwt(bad_token, verify_exp=False)

    assert 'Token with unexpected key' == str(exc_info.value)


# @pytest.mark.skipif(
#     not COGNITO_KEYS or not OKTA_KEYS,
#     reason='okta/cognito down'
# )
@pytest.mark.skip()
@pytest.mark.parametrize(
    'unverified_token,email,idp',
    [
        (OKTA_TOKEN, OKTA_TOKEN_EMAIL, OKTA),
        (AZURE_TOKEN, AZURE_EMAIL, OKTA),
        (COGNITO_TOKEN, COGNITO_TOKEN_EMAIL, COGNITO),
    ],
)
def test_verify_cognito_or_okta_token(unverified_token, email, idp):
    verified_token = decode_jwt(unverified_token, verify_exp=False)
    assert email == verified_token['email']
    assert idp == verified_token['idp']


# @pytest.mark.skipif(
#     not COGNITO_KEYS or not OKTA_KEYS,
#     reason='okta/cognito down'
# )
@pytest.mark.skip()
@pytest.mark.parametrize(
    'unverified_token,exception_message',
    [
        (OKTA_TOKEN, SIGNATURE_EXPIRED_EXCEPTION_MESSAGE),
        (COGNITO_TOKEN, SIGNATURE_EXPIRED_EXCEPTION_MESSAGE),
    ],
)
def test_verify_cognito_or_okta_signature_expired(unverified_token, exception_message):
    with pytest.raises(jwt.exceptions.ExpiredSignatureError) as excinfo:
        decode_jwt(unverified_token)
    assert exception_message == str(excinfo.value)


# @pytest.mark.skipif(not OKTA_KEYS, reason='okta is down')
@pytest.mark.skip()
def test_verify_okta_token():
    verified_token = decode_okta(OKTA_TOKEN, verify_exp=False)
    assert OKTA_TOKEN_EMAIL == verified_token['email']
    assert OKTA == verified_token['idp']
    assert verified_token['auth_groups']


# @pytest.mark.skipif(not OKTA_KEYS, reason='okta is down')
@pytest.mark.skip()
def test_get_okta_users():
    users = OktaApi.get_users()
    assert len(users) > 0


# @pytest.mark.skipif(not OKTA_KEYS, reason='okta is down')
@pytest.mark.skip()
def test_get_okta_user_by_email():
    user = OktaApi.get_user_by_email(OKTA_TOKEN_EMAIL)
    assert user
    assert user.profile

    logger.info(f'USER: {user}')


# @pytest.mark.skipif(not OKTA_KEYS, reason='okta is down')
@pytest.mark.skip()
def test_get_okta_user_groups():
    user = OktaApi.get_user_by_email(OKTA_TOKEN_EMAIL)
    assert user
    assert user.id

    groups = OktaApi.get_user_groups(user.id)
    logger.info(f'GROUPS: {groups}')
    assert len(groups) > 0


# @pytest.mark.skipif(not OKTA_KEYS, reason='okta is down')
@pytest.mark.skip()
@pytest.mark.functional
def test_create_okta_user_repeated_email_exception(graphql_organization):
    with pytest.raises(OktaAPIException) as okta_excinfo:
        OktaApi.create_user(
            first_name='User',
            last_name='Test',
            email=OKTA_TOKEN_EMAIL,
            login=OKTA_TOKEN_EMAIL,
            organization=graphql_organization,
            user_groups=['Laika-Dev'],
        )

    logger.info(str(okta_excinfo.value).split(', ')[-1].split('\': '))


# @pytest.mark.skipif(not OKTA_KEYS, reason='okta is down')
@pytest.mark.skip()
@pytest.mark.functional
def test_set_okta_password_exception():
    with pytest.raises(OktaAPIException) as okta_excinfo:
        OktaApi.set_user_password(MOCKED_OKTA_USER_ID, MOCKED_OKTA_PASSWORD)
    logger.info(str(okta_excinfo.value).split(', ')[-1].split('\': '))


# @pytest.mark.skipif(not OKTA_KEYS, reason='okta is down')
@pytest.mark.skip()
def test_get_laika_groups():
    groups = OktaApi.get_laika_groups(['Laika-Dev', 'Audits-Dev'])
    assert len(groups) == 2


# @pytest.mark.skipif(not OKTA_KEYS, reason='okta is down')
@pytest.mark.skip()
def test_get_user_apps():
    groups = OktaApi.get_user_apps(
        user_id=OktaApi.get_user_by_email(email='dev@heylaika.com').id
    )

    assert len(groups) > 1


# @pytest.mark.skipif(
#     not COGNITO_KEYS or not OKTA_KEYS,
#     reason='okta is down'
# )
@pytest.mark.skip()
@pytest.mark.functional
@pytest.mark.parametrize(
    'unverified_token,backend,email,assertion',
    [
        (
            OKTA_TOKEN,
            LAIKA_BACKEND,
            OKTA_TOKEN_EMAIL,
            True,
        ),  # OKTA_TOKEN is in Laika Employees group
        (OKTA_TOKEN, CONCIERGE_BACKEND, OKTA_TOKEN_EMAIL, False),
        (OKTA_TOKEN, AUDITS_BACKEND, OKTA_TOKEN_EMAIL, False),
        # AZURE_TOKEN is in Laika-Employees group
        (AZURE_TOKEN, LAIKA_BACKEND, AZURE_EMAIL, True),
        (AZURE_TOKEN, CONCIERGE_BACKEND, AZURE_EMAIL, False),
        (AZURE_TOKEN, AUDITS_BACKEND, AZURE_EMAIL, False),
        (
            COGNITO_TOKEN,
            LAIKA_BACKEND,
            COGNITO_TOKEN_EMAIL,
            True,
        ),  # COGNITO_TOKEN is SuperAdmin
        (COGNITO_TOKEN, CONCIERGE_BACKEND, COGNITO_TOKEN_EMAIL, False),
        (COGNITO_TOKEN, AUDITS_BACKEND, COGNITO_TOKEN_EMAIL, False),
    ],
)
def test_base_authenticate(
    graphql_organization, unverified_token, backend, email, assertion
):
    create_users(graphql_organization, backend, email)
    verified_token = authenticate(
        selected_backend=backend, token=unverified_token, verify_exp=False
    )

    if assertion:
        assert verified_token
    else:
        assert not verified_token


def test_non_valid_timezone_now_date():
    time_zone = 'Unknown'
    date = now_date(time_zone)
    assert date


# @pytest.mark.skipif(
#     not COGNITO_KEYS or not OKTA_KEYS,
#     reason='okta is down'
# )
@pytest.mark.skip()
@pytest.mark.functional
@pytest.mark.parametrize(
    'unverified_token,backend,email,assertion',
    [
        (OKTA_TOKEN, LAIKA_BACKEND, OKTA_TOKEN_EMAIL, True),
        (AZURE_TOKEN, LAIKA_BACKEND, AZURE_EMAIL, True),
    ],
)
def test_base_authenticate_create_internal_user(
    unverified_token, backend, email, assertion
):
    create_organization(flags=[], name='Laika Local')

    Group.objects.create(name='premium_viewer')

    verified_token = authenticate(
        selected_backend=backend, token=unverified_token, verify_exp=False
    )

    if assertion:
        assert verified_token
        logger.info(f'Verified Token: {verified_token}')
    else:
        assert not verified_token


@pytest.mark.functional()
@pytest.mark.parametrize(
    'decoded_token',
    [
        (dict(email='myoktaemail@heylaika.com', idp=OKTA, username='asdf123')),
        (
            dict(
                email='mycognitoemail@heylaika.com',
                idp=COGNITO,
                username='my_cognito_username',
            )
        ),
    ],
)
def test_base_authenticate_get_internal_user(
    decoded_token,
):
    # Given
    assert decoded_token

    User.objects.create(
        first_name='Test',
        last_name='User',
        email=decoded_token['email'],
        role='OrganizationViewer',
    )

    Group.objects.create(name='premium_viewer')

    # When
    user = get_internal_user(decoded_token)

    # Then
    assert user
    assert user.groups.filter(name='premium_viewer').first()
    assert user.is_active

    if decoded_token['idp'] == OKTA:
        assert user.username == 'asdf123'

    if decoded_token['idp'] == COGNITO:
        assert user.username == decoded_token['username']


@pytest.mark.django_db
def test_base_authenticate_get_internal_django_user():
    expected_user = User.objects.create(
        first_name='Test',
        last_name='User',
        email=DJANGO_SETTINGS.get('LEGACY_SUPERADMIN'),
        username='idpUsername',
        role='OrganizationViewer',
    )

    user = get_internal_user(
        {
            'email': DJANGO_SETTINGS.get('LEGACY_SUPERADMIN'),
            'username': 'idpUsername',
            'idp': COGNITO,
        }
    )

    assert user == expected_user


@pytest.mark.django_db
def test_base_authenticate_get_internal_user_not_username():
    expected_user = User.objects.create(
        first_name='Test',
        last_name='User',
        email='test@heylaika.com',
        username='12345',
        role='OrganizationViewer',
    )
    expected_user.groups.add(Group.objects.create(name='premium_viewer'))

    user = get_internal_user(
        {'email': 'test@heylaika.com', 'username': 'idpUsername', 'idp': COGNITO}
    )

    assert user == expected_user


def test_api_request_middleware(caplog):
    get_response_mock = MagicMock(return_value=HttpResponse({'mock_response': True}))
    request_mock = MagicMock()
    request_mock.__setattr__('laika_operation', 'operation: Query.resolve_objects')
    request_mock.headers = {
        'Origin': None,
        'Host': 'localhost:8000',
        'User-Agent': 'http://localhost:8000',
    }
    request_mock.body = {'mock_request': 'test'}
    request_mock.id = 12345

    middleware = APIRequestMiddleware(get_response=get_response_mock)
    middleware.__call__(request=request_mock)

    assert (
        'Request ID 12345 - Started - Operation operation: '
        'Query.resolve_objects - Host localhost:8000 - '
        'User-Agent http://localhost:8000 - External origin'
        in caplog.text
    )
    assert "Request ID 12345 - Body: {'mock_request': 'test'}" in caplog.text
    assert "Request ID 12345 - Content: b'mock_response'" in caplog.text
    assert (
        'Request ID 12345 - Ended - Operation operation: '
        'Query.resolve_objects - Host localhost:8000 - '
        'User-Agent http://localhost:8000 - External origin.'
        in caplog.text
    )


@pytest.mark.django_db
@pytest.mark.asyncio
@patch('laika.middlewares.TokenAuthMiddleware.decode_jwt_async')
async def test_auth_token_middleware(decode_jwt_async_mock, caplog):
    email = 'test@heylaika.com'
    expected_user = await create_async_user(email=email, username='test12345')

    scope = dict(user=None, query_string='token=foo'.encode('UTF-8'))
    inner_mock = AsyncMock(return_value=scope)
    middleware = TokenAuthMiddleware(inner_mock)

    decode_jwt_async_mock.return_value = {'email': email}
    result = await middleware.__call__(scope=scope, receive=None, send=None)
    assert result['user'] == expected_user

    email = 'missing@heylaika.com'
    decode_jwt_async_mock.return_value = {'email': email}
    result = await middleware.__call__(scope=scope, receive=None, send=None)
    assert result['user'] == AnonymousUser()
    assert (
        "Error on web socket authentication: User matching query does not exist. with"
        f" email: {email}"
        in caplog.text
    )

    email = ''
    decode_jwt_async_mock.return_value = {'email': email}
    result = await middleware.__call__(scope=scope, receive=None, send=None)
    assert result['user'] == AnonymousUser()

    scope = dict(user=None, query_string='')
    result = await middleware.__call__(scope=scope, receive=None, send=None)
    assert result['user'] == AnonymousUser()
