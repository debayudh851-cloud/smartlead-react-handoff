from datetime import timedelta
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Category, Service, Enquiry, Lead, LeadHistory, Notification, Review, Wishlist, LeadFollowUp, MLPrediction

User = get_user_model()
PASSWORD = secrets.token_urlsafe(24) + 'a1'


class WorkflowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('customer', 'customer@example.com', PASSWORD)
        self.other = User.objects.create_user('other', 'other@example.com', PASSWORD)
        self.staff = User.objects.create_user('staff', 'staff@example.com', PASSWORD, is_staff=True)
        self.root = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.category = Category.objects.create(name='Development', slug='development')
        self.service = Service.objects.create(category=self.category, name='Web', slug='web', description='Business websites', starting_price=40000)

    def login(self, user):
        self.client.force_authenticate(user)

    def submit(self, **kwargs):
        self.login(self.user)
        body = {'service': self.service.pk, 'requirement': 'Business website', 'contact_email': self.user.email, 'budget': '50000', 'traffic_source': 'Google', 'total_visits': 3, 'page_views_per_visit': 2, 'time_on_website': 500}
        body.update(kwargs)
        return self.client.post('/api/enquiries/', body, format='json')

    def test_complete_business_workflow(self):
        self.assertEqual(self.client.get('/api/services/').status_code, 200)
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        lead = Lead.objects.get(pk=response.data['lead_id'])
        self.assertEqual(Enquiry.objects.count(), 1)
        self.assertTrue(Notification.objects.filter(recipient=self.staff, kind='NEW_ENQUIRY').exists())
        self.login(self.staff)
        response = self.client.patch(f'/api/leads/{lead.pk}/', {'status': 'CONTACTED', 'assigned_to': self.staff.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.post(f'/api/leads/{lead.pk}/followup/', {'notes': 'Call tomorrow', 'follow_up_date': (timezone.now()+timedelta(days=1)).isoformat()}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        with patch('business.views.predict') as predictor:
            predictor.return_value = MLPrediction.objects.create(lead=lead, probability=.81, probability_band='HIGH', model_version='test', features={})
            self.assertEqual(self.client.post('/api/ml/predict/', {'lead_id': lead.pk}, format='json').status_code, 201)
        self.assertEqual(self.client.patch(f'/api/leads/{lead.pk}/', {'status': 'CONVERTED'}, format='json').status_code, 200)
        lead.refresh_from_db()
        self.assertIsNotNone(lead.converted_at)
        self.assertEqual(lead.history.count(), 3)
        stats = self.client.get('/api/analytics/summary/').data
        self.assertEqual(stats['converted'], 1)
        self.assertEqual(stats['conversion_rate'], 1)
        self.login(self.user)
        self.assertEqual(self.client.get('/api/enquiries/').data['results'][0]['status'], 'CONVERTED')
        self.assertTrue(Notification.objects.filter(recipient=self.user, kind='ENQUIRY_STATUS').exists())

    def test_ownership_and_role_boundaries(self):
        enquiry = self.submit().data
        self.login(self.other)
        self.assertEqual(self.client.get(f'/api/enquiries/{enquiry["id"]}/').status_code, 404)
        self.assertEqual(self.client.get('/api/leads/').status_code, 403)
        self.assertEqual(self.client.post('/api/ml/predict/', {'lead_id': enquiry['lead_id']}, format='json').status_code, 403)
        self.assertEqual(self.client.post('/api/services/', {}, format='json').status_code, 403)
        self.login(self.staff)
        self.assertEqual(self.client.get('/api/admin/users/').status_code, 403)
        self.assertEqual(self.client.get('/api/admin/accounts/').status_code, 403)
        self.login(self.root)
        self.assertEqual(self.client.get('/api/admin/accounts/').status_code, 200)

    def test_transaction_rolls_back_when_lead_creation_fails(self):
        with patch('business.operations.Lead.objects.create', side_effect=RuntimeError('test failure')):
            with self.assertRaises(RuntimeError):
                self.submit()
        self.assertEqual(Enquiry.objects.count(), 0)
        self.assertEqual(Lead.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_idempotency_replay_and_conflict(self):
        self.login(self.user)
        body = {'service': self.service.pk, 'requirement': 'Website', 'contact_email': self.user.email, 'budget': '1000', 'traffic_source': 'Google'}
        first = self.client.post('/api/enquiries/', body, format='json', HTTP_IDEMPOTENCY_KEY='request-1')
        second = self.client.post('/api/enquiries/', body, format='json', HTTP_IDEMPOTENCY_KEY='request-1')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['id'], second.data['id'])
        body['requirement'] = 'Different'
        self.assertEqual(self.client.post('/api/enquiries/', body, format='json', HTTP_IDEMPOTENCY_KEY='request-1').status_code, 400)
        self.assertEqual(Lead.objects.count(), 1)

    def test_validation_filters_archive_and_transitions(self):
        self.assertEqual(self.submit(budget='-1').status_code, 400)
        self.assertEqual(self.submit(page_views_per_visit=-2).status_code, 400)
        lead = Lead.objects.get(pk=self.submit().data['lead_id'])
        self.login(self.staff)
        self.assertEqual(self.client.patch(f'/api/leads/{lead.pk}/', {'status': 'CONVERTED'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/leads/{lead.pk}/', {'assigned_to': self.other.pk}, format='json').status_code, 400)
        self.assertEqual(self.client.get('/api/leads/?date_from=bad').status_code, 400)
        self.assertEqual(self.client.get('/api/leads/?service=bad').status_code, 400)
        self.assertEqual(self.client.get('/api/leads/?status=NEW').data['count'], 1)
        self.assertEqual(self.client.delete(f'/api/services/{self.service.pk}/').status_code, 204)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/services/').data['count'], 0)
        self.assertEqual(self.submit().status_code, 400)

    def test_wishlist_reviews_notifications_and_profile(self):
        self.login(self.user)
        saved = self.client.post('/api/wishlist/', {'service': self.service.pk}, format='json')
        self.assertEqual(saved.status_code, 201)
        self.assertEqual(self.client.post('/api/wishlist/', {'service': self.service.pk}, format='json').status_code, 400)
        review = self.client.post('/api/reviews/', {'service': self.service.pk, 'rating': 5, 'comment': 'Good'}, format='json')
        self.assertEqual(review.status_code, 201, review.data)
        self.assertFalse(review.data['is_approved'])
        self.assertEqual(self.client.patch('/api/auth/profile/', {'first_name': 'Customer', 'phone': '123', 'is_staff': True}, format='json').status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.login(self.other)
        self.assertEqual(self.client.delete(f'/api/wishlist/{saved.data["id"]}/').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/reviews/{review.data["id"]}/', {'comment': 'Changed'}, format='json').status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/reviews/').data['count'], 0)
        self.login(self.staff)
        self.assertEqual(self.client.patch(f'/api/admin/reviews/{review.data["id"]}/', {'is_approved': True}, format='json').status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/reviews/').data['count'], 1)

    def test_logout_and_password_change_revoke_tokens(self):
        token = RefreshToken.for_user(self.user)
        self.login(self.user)
        self.assertEqual(self.client.post('/api/auth/logout/', {'refresh': str(token)}, format='json').status_code, 204)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post('/api/auth/refresh/', {'refresh': str(token)}, format='json').status_code, 401)
        other_token = RefreshToken.for_user(self.other)
        self.login(self.user)
        self.assertEqual(self.client.post('/api/auth/logout/', {'refresh': str(other_token)}, format='json').status_code, 403)
        old = RefreshToken.for_user(self.user)
        new_password = secrets.token_urlsafe(24) + 'b2'
        self.assertEqual(self.client.post('/api/auth/password/change/', {'current_password': PASSWORD, 'new_password': new_password, 'confirm_password': new_password}, format='json').status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post('/api/auth/refresh/', {'refresh': str(old)}, format='json').status_code, 401)

    def test_reminders_are_idempotent_and_private(self):
        lead = Lead.objects.get(pk=self.submit().data['lead_id'])
        lead.assigned_to = self.staff
        lead.save()
        followup = LeadFollowUp.objects.create(lead=lead, created_by=self.staff, notes='Due', follow_up_date=timezone.now()-timedelta(hours=1))
        call_command('send_followup_reminders')
        call_command('send_followup_reminders')
        note = Notification.objects.get(kind='FOLLOWUP_DUE')
        self.login(self.other)
        self.assertEqual(self.client.patch(f'/api/notifications/{note.pk}/', {'is_read': True}, format='json').status_code, 404)

    def test_model_unavailable_and_demo_prediction_storage(self):
        lead = Lead.objects.get(pk=self.submit().data['lead_id'])
        self.login(self.staff)
        with override_settings(ML_MODEL_PATH='nonexistent.joblib'):
            self.assertEqual(self.client.post('/api/ml/predict/', {'lead_id': lead.pk}, format='json').status_code, 503)
        self.assertEqual(Lead.objects.count(), 1)
        with patch('business.predictor.load_model') as loader, TemporaryDirectory() as directory:
            model_path = Path(directory)/'test.joblib'
            model_path.touch()
            import numpy as np
            loader.return_value = {'version': 'test', 'pipeline': type('Model', (), {'predict_proba': lambda self, X: np.array([[.19, .81]])})()}
            with override_settings(ML_MODEL_PATH=str(model_path)):
                for _ in range(2):
                    response = self.client.post('/api/ml/predict/', {'lead_id': lead.pk}, format='json')
                    self.assertEqual(response.status_code, 201)
                    self.assertEqual(response.data['probability_band'], 'HIGH')
                    self.assertTrue(response.data['is_demo'])
        self.assertEqual(Notification.objects.filter(kind='HIGH_PROBABILITY', recipient=self.staff).count(), 1)

    def test_catalog_seed_and_frontend(self):
        call_command('seed_services')
        call_command('seed_services')
        self.assertEqual(Service.objects.filter(slug='web-development').count(), 1)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SMARTLEAD')
        self.assertEqual(self.client.get('/api/services/?search=Web').status_code, 200)
        self.assertEqual(self.client.get('/api/services/?min_price=nan').status_code, 400)
