from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password
from .validators import validate_single_at_email


class UserRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True, allow_blank=False, max_length=254, validators=[validate_single_at_email])
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Email already exists.')
        return value

    def validate(self, attrs):
        try:
            validate_password(attrs['password'], User(username=attrs['username'], email=attrs['email']))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'date_joined']


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, allow_blank=False, max_length=254, validators=[validate_single_at_email])


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=128)
    token = serializers.CharField(max_length=256)
    new_password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs


class PasswordAwareTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = self.token_class(attrs['refresh'])
        try:
            user = User.objects.get(pk=refresh.get(api_settings.USER_ID_CLAIM))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise AuthenticationFailed('Invalid refresh token.')
        if not user.is_active or refresh.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(user.password):
            raise AuthenticationFailed('Token is no longer valid. Please log in again.')
        return super().validate(attrs)
