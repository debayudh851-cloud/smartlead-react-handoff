from datetime import datetime
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Avg
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from rest_framework import serializers
from .models import Category, Service, ServiceImage, ServicePackage, Wishlist, Enquiry, Lead, LeadFollowUp, Review, SEOContent, Notification
from .serializers import CategorySerializer, ServiceSerializer, ImageSerializer, PackageSerializer, WishlistSerializer, EnquirySerializer, LeadSerializer, FollowUpSerializer, HistorySerializer, ReviewSerializer, ReviewModerationSerializer, SEOSerializer, NotificationSerializer, ProfileSerializer, PasswordChangeSerializer, LogoutSerializer, PredictRequestSerializer, PredictionSerializer, UserManagementSerializer
from .permissions import PublicReadStaffWrite, SuperAdminOnly
from .operations import create_enquiry, update_lead
from .predictor import predict


def date_filter(request, queryset, field='created_at'):
    for key, lookup in [('date_from', 'gte'), ('date_to', 'lte')]:
        value = request.query_params.get(key)
        if value:
            try:
                value = datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                raise ValidationError({key: 'Use YYYY-MM-DD.'})
            queryset = queryset.filter(**{f'{field}__date__{lookup}': value})
    return queryset


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [PublicReadStaffWrite]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        qs = Category.objects.all()
        return qs if self.request.user.is_staff else qs.filter(is_active=True)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


class ServiceViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceSerializer
    permission_classes = [PublicReadStaffWrite]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'category__name']
    ordering_fields = ['name', 'starting_price', 'created_at']

    def get_queryset(self):
        qs = Service.objects.select_related('category').prefetch_related('images', 'packages', 'seo')
        if not self.request.user.is_staff:
            qs = qs.filter(is_active=True, category__is_active=True)
        category = self.request.query_params.get('category')
        if category:
            if not category.isdigit():
                raise ValidationError({'category': 'Use a category ID.'})
            qs = qs.filter(category_id=category)
        for param, lookup in [('min_price', 'gte'), ('max_price', 'lte')]:
            if param in self.request.query_params:
                from decimal import Decimal, InvalidOperation
                try:
                    value = Decimal(self.request.query_params[param])
                    if not value.is_finite() or value < 0:
                        raise InvalidOperation
                except InvalidOperation:
                    raise ValidationError({param: 'Use a nonnegative price.'})
                qs = qs.filter(**{f'starting_price__{lookup}': value})
        return qs

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])

    @action(detail=True, methods=['get'])
    def related(self, request, pk=None):
        service = self.get_object()
        qs = self.get_queryset().filter(category=service.category).exclude(pk=service.pk)[:5]
        return Response(self.get_serializer(qs, many=True).data)


class ImageViewSet(viewsets.ModelViewSet):
    queryset = ServiceImage.objects.all()
    serializer_class = ImageSerializer
    permission_classes = [IsAdminUser]


class PackageViewSet(viewsets.ModelViewSet):
    queryset = ServicePackage.objects.all()
    serializer_class = PackageSerializer
    permission_classes = [IsAdminUser]


class SEOViewSet(viewsets.ModelViewSet):
    queryset = SEOContent.objects.all()
    serializer_class = SEOSerializer
    permission_classes = [IsAdminUser]


class WishlistViewSet(viewsets.ModelViewSet):
    queryset = Wishlist.objects.none()
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Wishlist.objects.none()
        return Wishlist.objects.filter(user=self.request.user).select_related('service')

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(user=self.request.user)
        except IntegrityError:
            raise ValidationError({'service': 'Service already in your wishlist.'})


class EnquiryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Enquiry.objects.none()
    serializer_class = EnquirySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Enquiry.objects.none()
        qs = Enquiry.objects.select_related('service', 'lead')
        return qs if self.request.user.is_staff else qs.filter(user=self.request.user)

    @extend_schema(parameters=[OpenApiParameter('Idempotency-Key', str, OpenApiParameter.HEADER)], responses={201: EnquirySerializer, 200: EnquirySerializer})
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = request.headers.get('Idempotency-Key')
        if key is not None and (not key.strip() or len(key) > 100):
            raise ValidationError({'detail': 'Idempotency-Key must contain 1-100 characters.'})
        enquiry, created = create_enquiry(request.user, serializer.validated_data, key)
        return Response(self.get_serializer(enquiry).data, status=201 if created else 200)


class LeadViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['enquiry__requirement', 'enquiry__user__username', 'enquiry__service__name']
    ordering_fields = ['created_at', 'updated_at', 'status']

    def get_queryset(self):
        qs = Lead.objects.select_related('enquiry__service', 'enquiry__user', 'assigned_to').prefetch_related('predictions')
        for param, field in [('status', 'status'), ('source', 'enquiry__traffic_source'), ('service', 'enquiry__service_id'), ('assigned_to', 'assigned_to_id')]:
            value = self.request.query_params.get(param)
            if value:
                if param in {'service', 'assigned_to'} and not value.isdigit():
                    raise ValidationError({param: 'Use an integer ID.'})
                if param == 'status' and value not in Lead.Status.values:
                    raise ValidationError({'status': 'Unknown status.'})
                qs = qs.filter(**{field: value})
        return date_filter(self.request, qs)

    def partial_update(self, request, pk=None):
        lead = self.get_object()
        serializer = self.get_serializer(lead, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        lead = update_lead(lead, request.user, serializer.validated_data)
        return Response(self.get_serializer(lead).data)

    @extend_schema(methods=['GET'], responses=FollowUpSerializer(many=True))
    @extend_schema(methods=['POST'], request=FollowUpSerializer, responses={201: FollowUpSerializer})
    @action(detail=True, methods=['get', 'post'])
    def followup(self, request, pk=None):
        lead = self.get_object()
        if request.method == 'GET':
            return Response(FollowUpSerializer(lead.followups.all(), many=True).data)
        serializer = FollowUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(lead=lead, created_by=request.user)
        return Response(serializer.data, status=201)

    @extend_schema(responses=HistorySerializer(many=True))
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        return Response(HistorySerializer(self.get_object().history.all(), many=True).data)

    @extend_schema(responses=PredictionSerializer(many=True))
    @action(detail=True, methods=['get'])
    def predictions(self, request, pk=None):
        return Response(PredictionSerializer(self.get_object().predictions.all(), many=True).data)


class FollowUpViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LeadFollowUp.objects.all()
    serializer_class = FollowUpSerializer
    permission_classes = [IsAdminUser]

    def partial_update(self, request, pk=None):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if 'follow_up_date' in serializer.validated_data and serializer.validated_data['follow_up_date'] != instance.follow_up_date:
            serializer.save(reminded_at=None)
        else:
            serializer.save()
        return Response(serializer.data)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.none()
    serializer_class = ReviewSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        return [AllowAny()] if self.action in {'list', 'retrieve'} else [IsAuthenticated()]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Review.objects.none()
        qs = Review.objects.select_related('service')
        if self.action in {'partial_update', 'destroy'}:
            qs = qs.filter(user=self.request.user)
        elif not self.request.user.is_staff:
            qs = qs.filter(Q(is_approved=True) | Q(user_id=self.request.user.pk)).filter(service__is_active=True, service__category__is_active=True)
        service = self.request.query_params.get('service')
        if service:
            if not service.isdigit():
                raise ValidationError({'service': 'Use a service ID.'})
            qs = qs.filter(service_id=service)
        return qs

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(user=self.request.user)
        except IntegrityError:
            raise ValidationError({'service': 'You already reviewed this service.'})

    def perform_update(self, serializer):
        serializer.save(is_approved=False)


class ModerationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewModerationSerializer
    permission_classes = [IsAdminUser]

    def partial_update(self, request, pk=None):
        instance = self.get_object()
        if instance.user_id == request.user.pk:
            raise PermissionDenied('You cannot approve your own review.')
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        return Notification.objects.filter(recipient=self.request.user)

    def partial_update(self, request, pk=None):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordChangeView(generics.GenericAPIView):
    serializer_class = PasswordChangeSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])
        return Response({'message': 'Password changed. Sign in again.'})


class LogoutView(generics.GenericAPIView):
    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh = RefreshToken(serializer.validated_data['refresh'])
            if str(refresh['user_id']) != str(request.user.pk):
                raise PermissionDenied('Token does not belong to you.')
            refresh.blacklist()
        except TokenError:
            raise ValidationError({'refresh': 'Invalid refresh token.'})
        return Response(status=204)


class PredictView(generics.GenericAPIView):
    serializer_class = PredictRequestSerializer
    permission_classes = [IsAdminUser]

    @extend_schema(responses={201: PredictionSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = get_object_or_404(Lead.objects.select_related('enquiry'), pk=serializer.validated_data['lead_id'])
        return Response(PredictionSerializer(predict(lead)).data, status=201)


class UserManagementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = get_user_model().objects.order_by('id')
    serializer_class = UserManagementSerializer
    permission_classes = [SuperAdminOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get('role')
        if role == 'user':
            return qs.filter(is_staff=False, is_superuser=False)
        if role == 'admin':
            return qs.filter(is_staff=True, is_superuser=False)
        if role == 'superuser':
            return qs.filter(is_superuser=True)
        if role:
            raise ValidationError({'role': 'Use user, admin or superuser.'})
        return qs

    def partial_update(self, request, pk=None):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AnalyticsView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = LeadSerializer

    @extend_schema(responses=inline_serializer('AnalyticsSummary', fields={
        'leads': serializers.IntegerField(), 'converted': serializers.IntegerField(), 'closed': serializers.IntegerField(),
        'conversion_rate': serializers.FloatField(allow_null=True), 'conversion_rate_definition': serializers.CharField(),
        'by_status': serializers.ListField(child=serializers.DictField()), 'by_service': serializers.ListField(child=serializers.DictField()),
        'by_source': serializers.ListField(child=serializers.DictField()), 'due_followups': serializers.IntegerField(),
        'high_probability_leads': serializers.IntegerField(), 'average_approved_rating': serializers.FloatField(allow_null=True),
    }))
    def get(self, request):
        leads = date_filter(request, Lead.objects.all())
        total = leads.count()
        converted = leads.filter(status='CONVERTED').count()
        closed = leads.filter(status__in=['CONVERTED', 'NOT_CONVERTED']).count()
        return Response({
            'leads': total, 'converted': converted, 'closed': closed,
            'conversion_rate': round(converted / closed, 4) if closed else None,
            'conversion_rate_definition': 'Converted / closed leads, grouped by lead creation date.',
            'by_status': list(leads.values('status').annotate(count=Count('id')).order_by('status')),
            'by_service': list(leads.values('enquiry__service__name').annotate(count=Count('id')).order_by('-count')),
            'by_source': list(leads.values('enquiry__traffic_source').annotate(count=Count('id')).order_by('-count')),
            'due_followups': LeadFollowUp.objects.filter(completed=False, follow_up_date__lte=timezone.now(), lead__in=leads).count(),
            'high_probability_leads': leads.filter(predictions__probability_band='HIGH').distinct().count(),
            'average_approved_rating': Review.objects.filter(is_approved=True).aggregate(value=Avg('rating'))['value'],
        })
