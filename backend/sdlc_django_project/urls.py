"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.views.generic import TemplateView
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.conf import settings
from django.conf.urls.static import static
from api.views import user_register
from business.roles import portal, signup, RoleLoginView, AdminRegisterView, AdminRegistrationList, AdminDecisionView

urlpatterns = [
    path('user/signup/', signup, {'role': 'user'}, name='user-signup'),
    path('admin-portal/signup/', signup, {'role': 'admin'}, name='admin-signup'),
    path('user/', portal, {'role': 'user'}, name='user-portal'),
    path('admin-portal/', portal, {'role': 'admin'}, name='admin-portal'),
    path('superuser/', portal, {'role': 'superuser'}, name='superuser-portal'),
    path('api/user/login/', RoleLoginView.as_view(portal_role='user')),
    path('api/admin/login/', RoleLoginView.as_view(portal_role='admin')),
    path('api/superuser/login/', RoleLoginView.as_view(portal_role='superuser')),
    path('api/admin/register/', AdminRegisterView.as_view()),
    path('api/superuser/admin-registrations/', AdminRegistrationList.as_view()),
    path('api/superuser/admin-registrations/<int:pk>/decision/', AdminDecisionView.as_view()),
    path('', TemplateView.as_view(template_name='business/home.html'), name='home'),
    path('accounts/', TemplateView.as_view(template_name='api/index.html'), name='accounts'),
    path('<str:role>/reset-password/<str:uid>/<str:token>/', TemplateView.as_view(template_name='api/index.html'), name='reset-page'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api/auth/register/', user_register),
    path('api/auth/login/', TokenObtainPairView.as_view()),
    path('api/auth/refresh/', TokenRefreshView.as_view()),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/', include('business.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
