from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import EmployeeAccess
from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class EmployeeJWTScheme(SimpleJWTScheme):
    target_class = 'business.authentication.EmployeeJWTAuthentication'
    name = 'jwtAuth'


class EmployeeJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            user, token = result
            allowed = {'/api/auth/profile/', '/api/auth/password/change/', '/api/auth/logout/'}
            if user.is_staff and not user.is_superuser and request.path not in allowed and EmployeeAccess.objects.filter(user=user, must_change_password=True).exists():
                raise PermissionDenied('Change your temporary password before accessing the workspace.')
        return result
