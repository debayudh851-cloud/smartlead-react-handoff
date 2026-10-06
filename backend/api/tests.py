from datetime import timedelta
import secrets
from unittest.mock import patch
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator as generator
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

PASSWORD = secrets.token_urlsafe(24) + 'a1'
NEW = secrets.token_urlsafe(24) + 'b2'

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BackendTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', PASSWORD)
        self.user = User.objects.create_user('member', 'member@example.com', PASSWORD)

    def post(self, url, data):
        return self.client.post(url, data, format='json')

    def reset_data(self, user=None):
        user = user or self.admin
        return dict(uid=urlsafe_base64_encode(force_bytes(user.pk)), token=generator.make_token(user), new_password=NEW, confirm_password=NEW)

    def test_registration(self):
        response = self.post('/api/user/register/', dict(username='fresh', email='FRESH@example.com', password=PASSWORD, is_staff=True, is_superuser=True))
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='fresh')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertNotIn('password', response.data['user'])
        self.assertIn('access', response.data['tokens'])
        self.assertEqual(user.email, 'fresh@example.com')

    def test_registration_validation(self):
        for data in [dict(username='member', email='fresh@example.com', password=PASSWORD), dict(username='fresh', email='MEMBER@example.com', password=PASSWORD), dict(username='fresh', email='bad', password=PASSWORD), dict(username='fresh', email='', password=PASSWORD), dict(username='fresh', email='fresh@example.com', password='12345678'), {}]:
            with self.subTest(data=data):
                self.assertEqual(self.post('/api/user/register/', data).status_code, 400)

    def test_permissions(self):
        self.assertEqual(self.client.get('/api/admin/users/').status_code, 401)
        for user, expected in [(self.user, 403), (self.admin, 200)]:
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
            response = self.client.get('/api/admin/users/')
            self.assertEqual(response.status_code, expected)
            if expected == 200:
                self.assertEqual(response.data['count'], 2)
                self.assertEqual(set(response.data['users'][0]), {'id', 'username', 'email', 'is_staff', 'date_joined'})
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid')
        self.assertEqual(self.client.get('/api/admin/users/').status_code, 401)

    def test_login_refresh(self):
        response = self.post('/api/token/', dict(username='admin', password=PASSWORD))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post('/api/token/refresh/', dict(refresh=response.data['refresh'])).status_code, 200)
        self.assertEqual(self.post('/api/token/', dict(username='admin', password='wrong')).status_code, 401)
        self.assertEqual(self.post('/api/token/refresh/', dict(refresh='invalid')).status_code, 401)

    def test_forgot_password(self):
        responses = [self.post('/api/admin/forgot-password/', dict(email=email)) for email in ['ADMIN@example.com', 'missing@example.com', 'member@example.com']]
        self.assertTrue(all(r.status_code == 200 for r in responses))
        self.assertEqual(responses[0].data, responses[1].data)
        self.assertEqual(responses[1].data, responses[2].data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(settings.FRONTEND_URL + '/admin/reset-password/', mail.outbox[0].body)
        self.assertEqual(self.post('/api/admin/forgot-password/', dict(email='bad')).status_code, 400)

    def test_reset_revokes_tokens(self):
        refresh = RefreshToken.for_user(self.admin)
        access = str(refresh.access_token)
        data = self.reset_data()
        self.assertEqual(self.post('/api/admin/reset-password/', data).status_code, 200)
        self.assertEqual(self.post('/api/admin/reset-password/', data).status_code, 400)
        self.assertEqual(self.post('/api/token/', dict(username='admin', password=PASSWORD)).status_code, 401)
        self.assertEqual(self.post('/api/token/', dict(username='admin', password=NEW)).status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(self.client.get('/api/admin/users/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.post('/api/token/refresh/', dict(refresh=str(refresh))).status_code, 401)

    def test_invalid_reset(self):
        for changes in [dict(uid='!!!!'), dict(uid='OTk5OTk5'), dict(token='invalid'), dict(confirm_password='different'), dict(new_password='12345678', confirm_password='12345678')]:
            data = self.reset_data()
            data.update(changes)
            with self.subTest(changes=changes):
                self.assertEqual(self.post('/api/admin/reset-password/', data).status_code, 400)
        self.assertEqual(self.post('/api/admin/reset-password/', self.reset_data(self.user)).status_code, 400)

    def test_reset_expiry(self):
        data = self.reset_data()
        with patch.object(generator, '_now', return_value=generator._now() + timedelta(hours=2)):
            self.assertEqual(self.post('/api/admin/reset-password/', data).status_code, 400)

    def test_expired_jwts(self):
        refresh = RefreshToken.for_user(self.admin)
        access = refresh.access_token
        access.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(self.client.get('/api/admin/users/').status_code, 401)
        self.client.credentials()
        refresh.set_exp(lifetime=timedelta(seconds=-1))
        self.assertEqual(self.post('/api/token/refresh/', dict(refresh=str(refresh))).status_code, 401)

    def test_inactive_deleted_refresh(self):
        refresh = str(RefreshToken.for_user(self.user))
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.post('/api/token/refresh/', dict(refresh=refresh)).status_code, 401)
        self.user.delete()
        self.assertEqual(self.post('/api/token/refresh/', dict(refresh=refresh)).status_code, 401)

    def test_cors(self):
        response = self.client.options('/api/user/register/', HTTP_ORIGIN='http://localhost:5173', HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST')
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://localhost:5173')
        response = self.client.options('/api/user/register/', HTTP_ORIGIN='https://untrusted.example', HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST')
        self.assertNotIn('Access-Control-Allow-Origin', response)

    def test_user_forgot_password_email(self):
        responses = [self.post('/api/user/forgot-password/', dict(email=email)) for email in ['MEMBER@example.com', 'missing@example.com', 'admin@example.com']]
        self.assertTrue(all(r.status_code == 200 for r in responses))
        self.assertTrue(all(r.data == responses[0].data for r in responses))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/user/reset-password/', mail.outbox[0].body)

    def test_user_reset_and_jwt_revocation(self):
        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)
        data = self.reset_data(self.user)
        self.assertEqual(self.post('/api/user/reset-password/', data).status_code, 200)
        self.assertEqual(self.post('/api/user/reset-password/', data).status_code, 400)
        self.assertEqual(self.post('/api/token/', dict(username='member', password=NEW)).status_code, 200)
        self.assertEqual(self.post('/api/token/', dict(username='member', password=PASSWORD)).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(self.client.get('/api/admin/users/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.post('/api/token/refresh/', dict(refresh=str(refresh))).status_code, 401)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    def test_user_reset_rejects_admin_and_invalid_requests(self):
        self.assertEqual(self.post('/api/user/reset-password/', self.reset_data(self.admin)).status_code, 400)
        for changes in [dict(uid='!!!!'), dict(token='invalid'), dict(confirm_password='different'), dict(new_password='12345678', confirm_password='12345678')]:
            data = self.reset_data(self.user)
            data.update(changes)
            with self.subTest(changes=changes):
                self.assertEqual(self.post('/api/user/reset-password/', data).status_code, 400)
        data = self.reset_data(self.user)
        with patch.object(generator, '_now', return_value=generator._now() + timedelta(hours=2)):
            self.assertEqual(self.post('/api/user/reset-password/', data).status_code, 400)

    def test_username_recovery(self):
        responses = [self.post('/api/user/forgot-username/', dict(email=email)) for email in ['MEMBER@example.com', 'missing@example.com', 'admin@example.com']]
        self.assertTrue(all(r.status_code == 200 for r in responses))
        self.assertTrue(all(r.data == responses[0].data for r in responses))
        self.assertNotIn('member', str(responses[0].data))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('member', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['member@example.com'])
        self.assertEqual(self.post('/api/user/forgot-username/', dict(email='bad')).status_code, 400)

    def test_inactive_user_recovery(self):
        data = self.reset_data(self.user)
        self.user.is_active = False
        self.user.save()
        self.post('/api/user/forgot-password/', dict(email=self.user.email))
        self.post('/api/user/forgot-username/', dict(email=self.user.email))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.post('/api/user/reset-password/', data).status_code, 400)

    def test_required_registration_fields(self):
        valid = dict(username='fresh', email='fresh@example.com', password=PASSWORD)
        for field in valid:
            for value in ['', '   ', None]:
                data = dict(valid, **{field: value})
                with self.subTest(field=field, value=value):
                    response = self.post('/api/user/register/', data)
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(field, response.data)
            data = valid.copy()
            del data[field]
            self.assertEqual(self.post('/api/user/register/', data).status_code, 400)

    def test_email_and_recovery_required_fields(self):
        for path in ['/api/user/forgot-password/', '/api/user/forgot-username/', '/api/admin/forgot-password/']:
            for data in [{}, dict(email=''), dict(email='   '), dict(email=None), dict(email='invalid.example.com'), dict(email='a@@example.com'), dict(email='"a@b"@example.com')]:
                with self.subTest(path=path, data=data):
                    self.assertEqual(self.post(path, data).status_code, 400)

    def test_password_letters_numbers_and_length(self):
        for password in ['OnlyLettersHere', '1234567890', 'Ab1!x', '!!!!!!!!']:
            with self.subTest(password=password):
                self.assertEqual(self.post('/api/user/register/', dict(username='fresh', email='fresh@example.com', password=password)).status_code, 400)
                for user, role in [(self.user, 'user'), (self.admin, 'admin')]:
                    data = self.reset_data(user)
                    data.update(new_password=password, confirm_password=password)
                    self.assertEqual(self.post(f'/api/{role}/reset-password/', data).status_code, 400)

    def test_reset_current_password_rejected_without_consuming_token(self):
        for user, role in [(self.user, 'user'), (self.admin, 'admin')]:
            data = self.reset_data(user)
            data.update(new_password=PASSWORD, confirm_password=PASSWORD)
            response = self.post(f'/api/{role}/reset-password/', data)
            self.assertEqual(response.status_code, 400)
            self.assertIn('different', str(response.data['new_password']))
            user.refresh_from_db()
            self.assertTrue(user.check_password(PASSWORD))
            data.update(new_password=NEW, confirm_password=NEW)
            self.assertEqual(self.post(f'/api/{role}/reset-password/', data).status_code, 200)

    def test_reset_required_fields(self):
        for user, role in [(self.user, 'user'), (self.admin, 'admin')]:
            valid = self.reset_data(user)
            for field in valid:
                for value in ['', '   ', None]:
                    data = dict(valid, **{field: value})
                    with self.subTest(role=role, field=field, value=value):
                        self.assertEqual(self.post(f'/api/{role}/reset-password/', data).status_code, 400)
                data = valid.copy()
                del data[field]
                self.assertEqual(self.post(f'/api/{role}/reset-password/', data).status_code, 400)
