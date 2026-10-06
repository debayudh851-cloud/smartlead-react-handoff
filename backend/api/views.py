import logging
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserRegistrationSerializer, UserListSerializer, ForgotPasswordSerializer, ResetPasswordSerializer
from business.permissions import SuperAdminOnly
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

MessageResponse = inline_serializer('MessageResponse', fields={'message': serializers.CharField()})
RegistrationUser = inline_serializer('RegistrationUser', fields={'id': serializers.IntegerField(), 'username': serializers.CharField(), 'email': serializers.EmailField()})
RegistrationResponse = inline_serializer('RegistrationResponse', fields={'message': serializers.CharField(), 'user': RegistrationUser, 'tokens': serializers.DictField(child=serializers.CharField())})
UserListResponse = inline_serializer('UserListResponse', fields={'count': serializers.IntegerField(), 'users': UserListSerializer(many=True)})

logger = logging.getLogger(__name__)


@extend_schema(request=UserRegistrationSerializer, responses={201: RegistrationResponse})
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def user_register(request):
    serializer = UserRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        with transaction.atomic():
            user = serializer.save()
    except IntegrityError:
        return Response({'username': ['Username already exists.']}, status=400)
    refresh = RefreshToken.for_user(user)
    return Response({
        'message': 'User registered successfully',
        'user': {'id': user.pk, 'username': user.username, 'email': user.email},
        'tokens': {'refresh': str(refresh), 'access': str(refresh.access_token)},
    }, status=201)


@extend_schema(responses=UserListResponse)
@api_view(['GET'])
@permission_classes([SuperAdminOnly])
def admin_users(request):
    data = UserListSerializer(User.objects.order_by('-date_joined', '-pk'), many=True).data
    return Response({'count': len(data), 'users': data})


@extend_schema(request=ForgotPasswordSerializer, responses=MessageResponse)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_forgot_password(request):
    return _forgot_password(request, admin=True)


def _forgot_password(request, admin):
    serializer = ForgotPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    # Send to every eligible match: built-in User does not enforce unique email.
    users = User.objects.filter(email__iexact=serializer.validated_data['email'], is_staff=admin, is_active=True)
    for user in users:
        if not user.has_usable_password():
            continue
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        role = 'admin' if admin else 'user'
        link = f'{settings.FRONTEND_URL}/{role}/reset-password/{uid}/{token}/'
        try:
            send_mail(f'{role.title()} Password Reset', f'Reset your password using this link:\n{link}\n\nIf you did not request this, ignore this email.', settings.DEFAULT_FROM_EMAIL, [user.email])
        except Exception:
            logger.error('Password reset email delivery failed; check email service configuration.')
    account = 'admin account' if admin else 'account'
    return Response({'message': f'If an eligible {account} exists, a password reset link has been sent.'})


@extend_schema(request=ResetPasswordSerializer, responses=MessageResponse)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_reset_password(request):
    return _reset_password(request, admin=True)


def _reset_password(request, admin):
    serializer = ResetPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        try:
            user_id = force_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.select_for_update().get(pk=user_id, is_staff=admin, is_active=True)
        except (TypeError, ValueError, OverflowError, UnicodeDecodeError, User.DoesNotExist):
            return Response({'error': 'Invalid password reset request.'}, status=400)
        if not default_token_generator.check_token(user, data['token']):
            return Response({'error': 'Invalid or expired password reset token.'}, status=400)
        try:
            validate_password(data['new_password'], user)
        except ValidationError as exc:
            return Response({'new_password': exc.messages}, status=400)
        user.set_password(data['new_password'])
        user.save(update_fields=['password'])
    return Response({'message': 'Password reset successfully.'})


@extend_schema(request=ForgotPasswordSerializer, responses=MessageResponse)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def user_forgot_password(request):
    return _forgot_password(request, admin=False)


@extend_schema(request=ResetPasswordSerializer, responses=MessageResponse)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def user_reset_password(request):
    return _reset_password(request, admin=False)


@extend_schema(request=ForgotPasswordSerializer, responses=MessageResponse)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def user_forgot_username(request):
    serializer = ForgotPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    users = User.objects.filter(email__iexact=serializer.validated_data['email'], is_staff=False, is_active=True)
    for user in users:
        if not user.has_usable_password():
            continue
        try:
            send_mail('Username Recovery', f'Your login username is: {user.username}\n\nIf you did not request this, ignore this email.', settings.DEFAULT_FROM_EMAIL, [user.email])
        except Exception:
            logger.error('Username recovery email delivery failed; check email service configuration.')
    return Response({'message': 'If an eligible account exists, a username reminder has been sent.'})
