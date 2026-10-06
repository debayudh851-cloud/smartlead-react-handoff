"""Role portals, backed by Django's shared user table."""
from django.shortcuts import render
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


def portal(request, role):
    return render(request, 'business/home.html', {'portal_role': role, 'portal_title': {'user': 'User', 'admin': 'Admin', 'superuser': 'Superuser'}[role]})


def signup(request, role):
    return render(request, 'business/signup.html', {'portal_role': role, 'portal_title': 'Admin' if role == 'admin' else 'User', 'login_url': '/admin-portal/' if role == 'admin' else '/user/'})


class RoleLoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        tokens = super().validate(attrs)
        role = self.context['view'].portal_role
        permitted = {
            'user': not self.user.is_staff and not self.user.is_superuser,
            'admin': self.user.is_staff and not self.user.is_superuser,
            'superuser': self.user.is_superuser,
        }
        if not permitted[role]:
            raise AuthenticationFailed('This account cannot sign in to this portal.')
        return tokens


class RoleLoginView(TokenObtainPairView):
    serializer_class = RoleLoginSerializer
    portal_role = 'user'


