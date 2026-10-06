from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at', '-pk']


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=30, blank=True)


class Category(Timestamped):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Service(Timestamped):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='services')
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    features = models.JSONField(default=list)
    starting_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)

    class Meta(Timestamped.Meta):
        constraints = [models.CheckConstraint(condition=models.Q(starting_price__gte=0), name='service_price_nonnegative')]

    def __str__(self):
        return self.name


class ServiceImage(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='services/')
    alt_text = models.CharField(max_length=200)


class ServicePackage(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    features = models.JSONField(default=list)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(price__gte=0), name='package_price_nonnegative')]


class Wishlist(Timestamped):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)

    class Meta(Timestamped.Meta):
        constraints = [models.UniqueConstraint(fields=['user', 'service'], name='unique_wishlist')]


class Enquiry(Timestamped):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='enquiries')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='enquiries')
    requirement = models.TextField(max_length=5000)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    traffic_source = models.CharField(max_length=120)
    keyword = models.CharField(max_length=200, blank=True)
    landing_page = models.CharField(max_length=500, blank=True)
    campaign = models.CharField(max_length=120, blank=True)
    total_visits = models.PositiveIntegerField(default=0)
    page_views_per_visit = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1000)])
    time_on_website = models.PositiveIntegerField(default=0)
    previous_enquiries = models.PositiveIntegerField(default=0, editable=False)
    idempotency_key = models.CharField(max_length=100, null=True, blank=True)

    class Meta(Timestamped.Meta):
        constraints = [
            models.UniqueConstraint(fields=['user', 'idempotency_key'], name='unique_enquiry_request'),
            models.CheckConstraint(condition=models.Q(budget__gte=0), name='enquiry_budget_nonnegative'),
        ]


class Lead(Timestamped):
    class Status(models.TextChoices):
        NEW = 'NEW'
        CONTACTED = 'CONTACTED'
        FOLLOW_UP = 'FOLLOW_UP'
        QUALIFIED = 'QUALIFIED'
        CONVERTED = 'CONVERTED'
        NOT_CONVERTED = 'NOT_CONVERTED'

    enquiry = models.OneToOneField(Enquiry, on_delete=models.PROTECT, related_name='lead')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_leads')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    converted_at = models.DateTimeField(null=True, blank=True)


class LeadFollowUp(Timestamped):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='followups')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    notes = models.TextField(max_length=5000)
    follow_up_date = models.DateTimeField(db_index=True)
    completed = models.BooleanField(default=False)
    reminded_at = models.DateTimeField(null=True, blank=True)


class LeadHistory(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='history')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    changes = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class Review(Timestamped):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(max_length=2000)
    is_approved = models.BooleanField(default=False)

    class Meta(Timestamped.Meta):
        constraints = [
            models.UniqueConstraint(fields=['user', 'service'], name='unique_service_review'),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='review_rating_range'),
        ]


class SEOContent(Timestamped):
    service = models.OneToOneField(Service, on_delete=models.CASCADE, related_name='seo')
    title = models.CharField(max_length=160)
    meta_description = models.CharField(max_length=320)
    keywords = models.JSONField(default=list)
    content = models.TextField(blank=True)


class Notification(Timestamped):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=40)
    message = models.CharField(max_length=500)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, null=True)
    is_read = models.BooleanField(default=False)
    event_key = models.CharField(max_length=160, unique=True, null=True, blank=True)


class MLPrediction(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='predictions')
    probability = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    probability_band = models.CharField(max_length=10)
    model_version = models.CharField(max_length=100)
    features = models.JSONField()
    is_demo = models.BooleanField(default=True)
    predicted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-predicted_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(probability__gte=0, probability__lte=1), name='prediction_probability_range')]
