from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
for prefix, view, basename in [
    ('categories', views.CategoryViewSet, 'category'), ('services', views.ServiceViewSet, 'service'),
    ('wishlist', views.WishlistViewSet, 'wishlist'), ('enquiries', views.EnquiryViewSet, 'enquiry'),
    ('leads', views.LeadViewSet, 'lead'), ('followups', views.FollowUpViewSet, 'followup'),
    ('reviews', views.ReviewViewSet, 'review'), ('notifications', views.NotificationViewSet, 'notification'),
    ('admin/reviews', views.ModerationViewSet, 'moderation'), ('admin/seo', views.SEOViewSet, 'seo'),
    ('admin/images', views.ImageViewSet, 'image'), ('admin/packages', views.PackageViewSet, 'package'),
    ('admin/accounts', views.UserManagementViewSet, 'account'),
]:
    router.register(prefix, view, basename=basename)

urlpatterns = [
    path('auth/profile/', views.ProfileView.as_view()),
    path('auth/password/change/', views.PasswordChangeView.as_view()),
    path('auth/logout/', views.LogoutView.as_view()),
    path('ml/predict/', views.PredictView.as_view()),
    path('analytics/summary/', views.AnalyticsView.as_view()),
    path('admin/dashboard/', views.AnalyticsView.as_view()),
    path('', include(router.urls)),
]
