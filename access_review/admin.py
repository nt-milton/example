from django.contrib import admin
from django.contrib.admin import display

from access_review.models import (
    AccessReview,
    AccessReviewObject,
    AccessReviewPreference,
    AccessReviewUserEvent,
    AccessReviewVendor,
    AccessReviewVendorPreference,
    ExternalAccessOwner,
)


class AccessReviewPreferenceAdmin(admin.ModelAdmin):
    list_display = ('organization', 'due_date', 'frequency', 'criticality')


admin.site.register(AccessReviewPreference, AccessReviewPreferenceAdmin)


class AccessReviewVendorPreferenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization_vendor', 'organization', 'vendor', 'in_scope')


admin.site.register(AccessReviewVendorPreference, AccessReviewVendorPreferenceAdmin)


class ExternalAccessOwnerAdmin(admin.ModelAdmin):
    pass


admin.site.register(ExternalAccessOwner, ExternalAccessOwnerAdmin)


class AccessReviewAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'created_at', 'status')


admin.site.register(AccessReview, AccessReviewAdmin)


class AccessReviewVendorAdmin(admin.ModelAdmin):
    list_display = ('id', 'access_review', 'vendor', 'synced_at', 'status')


admin.site.register(AccessReviewVendor, AccessReviewVendorAdmin)


class AccessReviewObjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'access_review', 'vendor', 'review_status', 'is_confirmed')
    readonly_fields = ('laika_object',)

    @display(ordering='access_review', description='Access review')
    def access_review(self, instance):
        return instance.access_review_vendor.access_review

    @display(ordering='vendor', description='Vendor')
    def vendor(self, instance):
        return instance.access_review_vendor.vendor


admin.site.register(AccessReviewObject, AccessReviewObjectAdmin)


class AccessReviewUserEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'access_review', 'user', 'event')

    @display(ordering='access_review', description='Access review')
    def access_review(self, instance):
        return instance.access_review_vendor.access_review


admin.site.register(AccessReviewUserEvent, AccessReviewUserEventAdmin)
