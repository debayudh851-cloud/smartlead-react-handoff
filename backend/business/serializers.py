import math
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Category, Service, ServiceImage, ServicePackage, Wishlist, Enquiry, Lead, LeadFollowUp, LeadHistory, Review, SEOContent, Notification, MLPrediction


User = get_user_model()


def string_list(value):
    if not isinstance(value, list) or len(value) > 50 or any(not isinstance(item, str) or len(item) > 500 for item in value):
        raise serializers.ValidationError('Expected at most 50 strings, each at most 500 characters.')
    return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class ImageSerializer(serializers.ModelSerializer):
    def validate_image(self, image):
        if image.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Image must be at most 5 MB.')
        if image.image.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise serializers.ValidationError('Use JPEG, PNG or WEBP images.')
        return image

    class Meta:
        model = ServiceImage
        fields = '__all__'


class PackageSerializer(serializers.ModelSerializer):
    validate_features = staticmethod(string_list)

    class Meta:
        model = ServicePackage
        fields = '__all__'


class SEOSerializer(serializers.ModelSerializer):
    validate_keywords = staticmethod(string_list)

    class Meta:
        model = SEOContent
        fields = '__all__'


class ServiceSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, read_only=True)
    packages = PackageSerializer(many=True, read_only=True)
    seo = SEOSerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    validate_features = staticmethod(string_list)

    class Meta:
        model = Service
        fields = '__all__'


class WishlistSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)

    class Meta:
        model = Wishlist
        fields = ['id', 'service', 'service_name', 'created_at']

    def validate_service(self, value):
        if not value.is_active or not value.category.is_active:
            raise serializers.ValidationError('Service is unavailable.')
        return value


class EnquirySerializer(serializers.ModelSerializer):
    lead_id = serializers.IntegerField(source='lead.id', read_only=True)
    status = serializers.CharField(source='lead.status', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)

    class Meta:
        model = Enquiry
        fields = '__all__'
        read_only_fields = ['user', 'previous_enquiries', 'idempotency_key']

    def validate_service(self, value):
        if not value.is_active or not value.category.is_active:
            raise serializers.ValidationError('Service is unavailable.')
        return value

    def validate_page_views_per_visit(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError('Value must be finite.')
        return value


class PredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLPrediction
        fields = '__all__'
        read_only_fields = ['lead', 'probability', 'probability_band', 'model_version', 'features', 'is_demo', 'predicted_at']


class LeadSerializer(serializers.ModelSerializer):
    enquiry = EnquirySerializer(read_only=True)
    latest_prediction = serializers.SerializerMethodField()

    @extend_schema_field(PredictionSerializer(allow_null=True))
    def get_latest_prediction(self, obj):
        prediction = obj.predictions.first()
        return PredictionSerializer(prediction).data if prediction else None

    class Meta:
        model = Lead
        fields = ['id', 'enquiry', 'assigned_to', 'status', 'converted_at', 'created_at', 'updated_at', 'latest_prediction']
        read_only_fields = ['converted_at']

    def validate_assigned_to(self, value):
        if value and not (value.is_active and value.is_staff):
            raise serializers.ValidationError('Assignee must be an active staff member.')
        return value


class FollowUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadFollowUp
        fields = '__all__'
        read_only_fields = ['lead', 'created_by', 'reminded_at']

    def validate_follow_up_date(self, value):
        from django.utils import timezone
        if value < timezone.now():
            raise serializers.ValidationError('Schedule a future follow-up.')
        return value


class HistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadHistory
        fields = '__all__'


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['user', 'is_approved']

    def validate_service(self, value):
        if not value.is_active or not value.category.is_active:
            raise serializers.ValidationError('Service is unavailable.')
        return value


class ReviewModerationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['id', 'user', 'service', 'rating', 'comment', 'is_approved']
        read_only_fields = ['user', 'service', 'rating', 'comment']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'kind', 'message', 'lead', 'is_read', 'created_at']
        read_only_fields = ['kind', 'message', 'lead', 'created_at']


class ProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def get_role(self, obj) -> str:
        return 'SUPER_ADMIN' if obj.is_superuser else 'ADMIN' if obj.is_staff else 'GENERAL_USER'

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone', 'role']
        read_only_fields = ['id', 'username', 'email']

    def to_representation(self, obj):
        data = super().to_representation(obj)
        data['phone'] = getattr(getattr(obj, 'profile', None), 'phone', '')
        return data

    def update(self, instance, validated_data):
        from .models import Profile
        phone = validated_data.pop('phone', None)
        instance = super().update(instance, validated_data)
        if phone is not None:
            Profile.objects.update_or_create(user=instance, defaults={'phone': phone})
        return instance


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, data):
        user = self.context['request'].user
        if not user.check_password(data['current_password']):
            raise serializers.ValidationError({'current_password': 'Incorrect password.'})
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        try:
            validate_password(data['new_password'], user)
        except ValidationError as exc:
            raise serializers.ValidationError({'new_password': exc.messages})
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class PredictRequestSerializer(serializers.Serializer):
    lead_id = serializers.IntegerField(min_value=1)


class UserManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_active', 'is_staff', 'is_superuser']
        read_only_fields = ['id', 'username', 'email']

    def validate(self, attrs):
        if attrs.get('is_superuser', self.instance.is_superuser) and not attrs.get('is_staff', self.instance.is_staff):
            raise serializers.ValidationError('A super-admin must also be staff.')
        if self.instance.pk == self.context['request'].user.pk and any(attrs.get(field) is False for field in ['is_active', 'is_staff', 'is_superuser']):
            raise serializers.ValidationError('You cannot demote or deactivate your own super-admin account.')
        return attrs
