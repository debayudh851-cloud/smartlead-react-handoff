import secrets
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer
from api.serializers import UserRegistrationSerializer, ForgotPasswordSerializer
from .models import EmployeeAccess, AdminRecoveryRequest
from .permissions import SuperAdminOnly


CredentialResponse = inline_serializer('EmployeeCredentials', fields={'id': serializers.IntegerField(), 'username': serializers.CharField(), 'temporary_password': serializers.CharField(), 'must_change_password': serializers.BooleanField()})


class EmployeeCreateSerializer(UserRegistrationSerializer):
    password = None

    class Meta(UserRegistrationSerializer.Meta):
        fields = ['username', 'email']

    def validate(self, attrs):
        return attrs


def issue_credentials(user, actor):
    password = secrets.token_urlsafe(24)
    user.set_password(password)
    user.save(update_fields=['password'])
    EmployeeAccess.objects.update_or_create(user=user, defaults={'must_change_password': True, 'provisioned_by': actor})
    return {'id': user.pk, 'username': user.username, 'temporary_password': password, 'must_change_password': True}


class EmployeeCreateView(generics.GenericAPIView):
    serializer_class = EmployeeCreateSerializer
    permission_classes = [SuperAdminOnly]

    @extend_schema(responses={201: CredentialResponse})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(**serializer.validated_data, is_staff=True)
                credentials = issue_credentials(user, request.user)
        except IntegrityError:
            raise ValidationError({'username': 'Login ID already exists.'})
        response = Response(credentials, status=201)
        response['Cache-Control'] = 'no-store'
        return response


class RecoverySubmitSerializer(ForgotPasswordSerializer):
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class RecoverySubmitView(generics.GenericAPIView):
    serializer_class = RecoverySubmitSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=inline_serializer('AdminRecoveryMessage', fields={'message': serializers.CharField()}))
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for user in get_user_model().objects.filter(email__iexact=serializer.validated_data['email'], is_staff=True, is_superuser=False, is_active=True):
            AdminRecoveryRequest.objects.get_or_create(user=user, status='PENDING', defaults={'reason': serializer.validated_data.get('reason', '')})
        return Response({'message': 'If an eligible employee account exists, a recovery request has been sent to the super admin.'})


class RecoverySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = AdminRecoveryRequest
        fields = ['id', 'user', 'username', 'email', 'reason', 'status', 'created_at', 'reviewed_by', 'reviewed_at']
        read_only_fields = fields


class RecoveryListView(generics.ListAPIView):
    queryset = AdminRecoveryRequest.objects.select_related('user').all()
    serializer_class = RecoverySerializer
    permission_classes = [SuperAdminOnly]


class RecoveryDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['RESET', 'REJECT'])


class RecoveryDecisionView(generics.GenericAPIView):
    queryset = AdminRecoveryRequest.objects.all()
    serializer_class = RecoveryDecisionSerializer
    permission_classes = [SuperAdminOnly]

    @extend_schema(responses=inline_serializer('RecoveryDecisionResponse', fields={'status': serializers.CharField(), 'credentials': CredentialResponse}))
    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            application = generics.get_object_or_404(self.get_queryset().select_for_update(), pk=pk)
            if application.status != 'PENDING':
                raise ValidationError('This recovery request has already been reviewed.')
            user = get_user_model().objects.select_for_update().get(pk=application.user_id)
            if not user.is_active or not user.is_staff or user.is_superuser:
                raise ValidationError('The account is not an active employee admin.')
            credentials = None
            if serializer.validated_data['decision'] == 'RESET':
                credentials = issue_credentials(user, request.user)
                application.status = 'RESOLVED'
            else:
                application.status = 'REJECTED'
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
        response = Response({'status': application.status, 'credentials': credentials})
        response['Cache-Control'] = 'no-store'
        return response
