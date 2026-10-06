import secrets
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APITestCase
from .models import AdminRecoveryRequest, EmployeeAccess

User = get_user_model()


class EmployeeTests(APITestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24) + 'a1'
        self.root = User.objects.create_superuser('root', 'root@example.com', self.password)
        self.user = User.objects.create_user('user', 'user@example.com', self.password)

    def create_employee(self):
        self.client.force_authenticate(self.root)
        response = self.client.post('/api/superuser/employees/', {'username': 'employee', 'email': 'employee@example.com'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response['Cache-Control'], 'no-store')
        return User.objects.get(username='employee'), response.data['temporary_password']

    def authenticate_password(self, password):
        self.client.force_authenticate(None)
        self.client.credentials()
        response = self.client.post('/api/admin/login/', {'username': 'employee', 'password': password}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])
        return response.data

    def test_only_superuser_can_create_employee_and_public_signup_is_removed(self):
        for user in [None, self.user]:
            self.client.force_authenticate(user)
            self.assertIn(self.client.post('/api/superuser/employees/', {'username': 'employee', 'email': 'employee@example.com'}).status_code, [401, 403])
        self.assertEqual(self.client.get('/admin-portal/signup/').status_code, 404)
        self.assertEqual(self.client.post('/api/admin/register/', {}).status_code, 404)
        self.assertNotContains(self.client.get('/admin-portal/'), 'Sign up')
        employee, password = self.create_employee()
        self.assertTrue(employee.is_staff)
        self.assertFalse(employee.is_superuser)
        self.assertTrue(employee.check_password(password))
        self.assertNotEqual(employee.password, password)
        self.assertEqual(self.client.post('/api/superuser/employees/', {'username': 'employee', 'email': 'different@example.com'}).status_code, 400)
        self.assertNotIn('password', str(self.client.get('/api/admin/accounts/').data))

    def test_temporary_password_blocks_generic_tokens_and_unlocks_after_change(self):
        employee, temporary = self.create_employee()
        tokens = self.authenticate_password(temporary)
        self.assertEqual(self.client.get('/api/leads/').status_code, 403)
        self.assertTrue(self.client.get('/api/auth/profile/').data['must_change_password'])
        same = {'current_password': temporary, 'new_password': temporary, 'confirm_password': temporary}
        self.assertEqual(self.client.post('/api/auth/password/change/', same).status_code, 400)
        new = secrets.token_urlsafe(24) + 'b2'
        self.assertEqual(self.client.post('/api/auth/password/change/', dict(current_password=temporary, new_password=new, confirm_password=new)).status_code, 200)
        self.assertEqual(self.client.get('/api/leads/').status_code, 401)
        self.authenticate_password(new)
        self.assertEqual(self.client.get('/api/leads/').status_code, 200)
        self.assertFalse(EmployeeAccess.objects.get(user=employee).must_change_password)

    def test_recovery_is_private_deduplicated_reviewed_and_revokes_sessions(self):
        employee, temporary = self.create_employee()
        tokens = self.authenticate_password(temporary)
        self.client.credentials()
        responses = [self.client.post('/api/admin/recovery-request/', {'email': email, 'reason': 'Forgot my credentials'}) for email in ['employee@example.com', 'missing@example.com', 'employee@example.com']]
        self.assertEqual(responses[0].data, responses[1].data)
        self.assertEqual(AdminRecoveryRequest.objects.count(), 1)
        application = AdminRecoveryRequest.objects.get()
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/superuser/recovery-requests/').status_code, 403)
        url = f'/api/superuser/recovery-requests/{application.pk}/decision/'
        self.assertEqual(self.client.post(url, {'decision': 'RESET'}).status_code, 403)
        self.client.force_authenticate(self.root)
        response = self.client.post(url, {'decision': 'RESET'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['credentials']['username'], employee.username)
        self.assertNotEqual(response.data['credentials']['temporary_password'], temporary)
        self.assertEqual(self.client.post(url, {'decision': 'RESET'}).status_code, 400)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post('/api/auth/refresh/', {'refresh': tokens['refresh']}).status_code, 401)
        self.authenticate_password(response.data['credentials']['temporary_password'])
        self.assertEqual(self.client.get('/api/leads/').status_code, 403)

    def test_rejected_recovery_does_not_reset_password_and_cannot_target_superuser(self):
        employee, temporary = self.create_employee()
        self.client.force_authenticate(None)
        self.client.post('/api/admin/recovery-request/', {'email': self.root.email})
        self.assertEqual(AdminRecoveryRequest.objects.count(), 0)
        self.client.post('/api/admin/recovery-request/', {'email': employee.email})
        application = AdminRecoveryRequest.objects.get()
        self.client.force_authenticate(self.root)
        response = self.client.post(f'/api/superuser/recovery-requests/{application.pk}/decision/', {'decision': 'REJECT'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['credentials'])
        employee.refresh_from_db()
        self.assertTrue(employee.check_password(temporary))
        self.assertEqual(self.client.post('/api/admin/reset-password/', {'uid': urlsafe_base64_encode(force_bytes(employee.pk)), 'token': default_token_generator.make_token(employee), 'new_password': self.password, 'confirm_password': self.password}).status_code, 404)
