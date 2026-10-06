"""Role portals and admin applications, backed by Django's shared user table."""
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.shortcuts import render
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema, inline_serializer
from api.serializers import UserRegistrationSerializer
from .models import AdminRegistration
from .permissions import SuperAdminOnly


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
            if role == 'admin' and AdminRegistration.objects.filter(user=self.user, status='PENDING').exists():
                raise AuthenticationFailed('Your admin registration is awaiting superuser approval.')
            raise AuthenticationFailed('This account cannot sign in to this portal.')
        return tokens


class RoleLoginView(TokenObtainPairView):
    serializer_class = RoleLoginSerializer
    portal_role = 'user'


class AdminRegisterView(generics.GenericAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={201: inline_serializer('AdminRegistrationResponse', fields={'message': serializers.CharField(), 'registration_id': serializers.IntegerField()})})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
                application = AdminRegistration.objects.create(user=user)
        except IntegrityError:
            raise ValidationError({'username': 'Username already exists.'})
        return Response({'message': 'Admin registration submitted. A superuser must approve access before admin login.', 'registration_id': application.pk}, status=201)


class AdminRegistrationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = AdminRegistration
        fields = ['id', 'user', 'username', 'email', 'status', 'created_at', 'reviewed_by', 'reviewed_at']
        read_only_fields = fields


class AdminDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])


class AdminRegistrationList(generics.ListAPIView):
    queryset = AdminRegistration.objects.select_related('user').all()
    serializer_class = AdminRegistrationSerializer
    permission_classes = [SuperAdminOnly]


class AdminDecisionView(generics.GenericAPIView):
    queryset = AdminRegistration.objects.all()
    serializer_class = AdminDecisionSerializer
    permission_classes = [SuperAdminOnly]

    @extend_schema(responses=AdminRegistrationSerializer)
    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            application = self.get_queryset().select_for_update().filter(pk=pk).first()
            if application is None:
                from rest_framework.exceptions import NotFound
                raise NotFound()
            if application.status != 'PENDING':
                raise ValidationError('This registration has already been reviewed.')
            user = get_user_model().objects.select_for_update().get(pk=application.user_id)
            if user.is_superuser or user.is_staff or not user.is_active:
                raise ValidationError('The account is no longer eligible for this registration decision.')
            application.status = serializer.validated_data['status']
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
            if application.status == 'APPROVED':
                user.is_staff = True
                user.save(update_fields=['is_staff'])
        return Response(AdminRegistrationSerializer(application).data)
