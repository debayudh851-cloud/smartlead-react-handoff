from django.urls import path
from . import views

urlpatterns = [
    path('user/register/', views.user_register, name='user-register'),
    path('user/forgot-password/', views.user_forgot_password, name='user-forgot-password'),
    path('user/reset-password/', views.user_reset_password, name='user-reset-password'),
    path('user/forgot-username/', views.user_forgot_username, name='user-forgot-username'),
    path('admin/users/', views.admin_users, name='admin-users'),
]
