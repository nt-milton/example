from django.db import models

from organization.models import Organization


class Coupon(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(
        Organization,
        # this is so it let's me create the new column
        # for existing rows (no rows for now)
        null=True,
        related_name='coupons',
        on_delete=models.CASCADE,
    )
    type = models.CharField(
        max_length=100,
        help_text='[Audit Type] [Audit Firm Name] e.g SOC 2 Type 1 Laika Compliance',
    )
    coupons = models.IntegerField(default=0)
