from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Coupon


class CouponAdmin(VersionAdmin):
    model = Coupon
    list_display = (
        'type',
        'organization',
        'coupons',
    )
    list_filter = ('organization', 'type')
    ordering = ('-created_at',)


admin.site.register(Coupon, CouponAdmin)
