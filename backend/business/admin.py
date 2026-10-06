from django.contrib import admin
from .models import Category, Service, ServiceImage, ServicePackage, Wishlist, Enquiry, Lead, LeadFollowUp, LeadHistory, Review, SEOContent, MLPrediction, Notification, Profile


class ImageInline(admin.TabularInline):
    model = ServiceImage
    extra = 0


class PackageInline(admin.TabularInline):
    model = ServicePackage
    extra = 0


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'starting_price', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ['name']}
    inlines = [ImageInline, PackageInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ['name']}


class ImmutableAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Lead)
class LeadAdmin(ImmutableAdmin):
    list_display = ['id', 'enquiry', 'status', 'assigned_to', 'created_at']
    list_filter = ['status', 'assigned_to']
    search_fields = ['enquiry__user__username', 'enquiry__service__name']


@admin.register(Enquiry)
class EnquiryAdmin(ImmutableAdmin):
    list_display = ['id', 'user', 'service', 'budget', 'traffic_source', 'created_at']
    list_filter = ['service', 'traffic_source']
    search_fields = ['requirement', 'user__username']


@admin.register(LeadHistory, MLPrediction, Notification)
class AuditAdmin(ImmutableAdmin):
    pass


@admin.register(LeadFollowUp)
class FollowUpAdmin(ImmutableAdmin):
    list_display = ['lead', 'created_by', 'follow_up_date', 'completed']
    list_filter = ['completed']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['service', 'user', 'rating', 'is_approved']
    list_filter = ['is_approved', 'rating']
    readonly_fields = ['user', 'service', 'rating', 'comment']

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        from django.core.exceptions import PermissionDenied
        if obj.user_id == request.user.pk and obj.is_approved:
            raise PermissionDenied('Cannot approve your own review.')
        super().save_model(request, obj, form, change)


admin.site.register(SEOContent)
admin.site.register(Profile)
admin.site.register(Wishlist, ImmutableAdmin)
admin.site.site_header = 'SMARTLEAD administration'
