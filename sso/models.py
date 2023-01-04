from django.db import models

from organization.models import Organization
from sso.constants import PENDING_IDP_DATA, SAML_INTEGRATIONS


class IdentityProvider(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='identity_provider',
    )
    idp_id = models.CharField(max_length=20)
    provider = models.CharField(
        max_length=10, choices=SAML_INTEGRATIONS, default='Okta'
    )
    name = models.CharField(max_length=255, default='SAML integration')
    rule_id = models.CharField(max_length=20, default=None, blank=True, null=True)
    state = models.CharField(max_length=20, default=PENDING_IDP_DATA)


class IdentityProviderDomain(models.Model):
    domain = models.TextField(unique=True)
    idp = models.ForeignKey(
        IdentityProvider, on_delete=models.CASCADE, related_name='domains'
    )
