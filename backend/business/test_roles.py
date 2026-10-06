import secrets
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.test import override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from .models import AdminRegistration, Category, Service, Enquiry, Lead

User = get_user_model()


class RolePortalTests(APITestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24)
        self.user = User.objects.create_user('user', 'user@example.com', self.password)
        self.admin = User.objects.create_user('admin', 'admin@example.com', self.password, is_staff=True)
        self.root = User.objects.create_superuser('root', 'root@example.com', self.password)

    def test_three_login_interfaces_enforce_roles(self):
        for role, user in [('user', self.user), ('admin', self.admin), ('superuser', self.root)]:
            for target in ['user', 'admin', 'superuser']:
                response = self.client.post(f'/api/{target}/login/', {'username': user.username, 'password': self.password})
                self.assertEqual(response.status_code, 200 if target == role else 401, response.data)
        for url, title in [('/user/', 'User portal'), ('/admin-portal/', 'Admin portal'), ('/superuser/', 'Superuser portal')]:
            self.assertContains(self.client.get(url), title)
        self.assertNotContains(self.client.get('/superuser/'), 'id="role-register"')

    def test_admin_registration_approval_and_requirement_access(self):
        response = self.client.post('/api/admin/register/', {'username': 'applicant', 'email': 'applicant@example.com', 'password': self.password, 'is_staff': True, 'is_superuser': True})
        self.assertEqual(response.status_code, 201, response.data)
        candidate = User.objects.get(username='applicant')
        self.assertFalse(candidate.is_staff)
        self.assertFalse(candidate.is_superuser)
        application = AdminRegistration.objects.get(user=candidate)
        login = {'username': candidate.username, 'password': self.password}
        self.assertEqual(self.client.post('/api/admin/login/', login).status_code, 401)
        self.client.force_authenticate(candidate)
        self.assertEqual(self.client.get('/api/leads/').status_code, 403)
        self.assertEqual(self.client.get('/api/superuser/admin-registrations/').status_code, 403)
        decision = f'/api/superuser/admin-registrations/{application.pk}/decision/'
        self.assertEqual(self.client.post(decision, {'status': 'APPROVED'}).status_code, 403)
        self.client.force_authenticate(self.root)
        self.assertEqual(self.client.post(decision, {'status': 'APPROVED'}).status_code, 200)
        self.assertEqual(self.client.post(decision, {'status': 'REJECTED'}).status_code, 400)
        candidate.refresh_from_db()
        application.refresh_from_db()
        self.assertTrue(candidate.is_staff)
        self.assertEqual(application.reviewed_by, self.root)
        category = Category.objects.create(name='Design', slug='design')
        service = Service.objects.create(category=category, name='Design', slug='design', starting_price=100)
        enquiry = Enquiry.objects.create(user=self.user, service=service, requirement='Need a website', contact_email=self.user.email, budget=100)
        Lead.objects.create(enquiry=enquiry)
        self.client.force_authenticate(candidate)
        self.assertEqual(self.client.get('/api/leads/').data['count'], 1)
        self.assertEqual(self.client.get('/api/admin/accounts/').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post('/api/admin/login/', login).status_code, 200)

    def test_superuser_can_view_users_and_admins_and_reject_applications(self):
        application = AdminRegistration.objects.create(user=self.user)
        self.client.force_authenticate(self.root)
        for role, username in [('user', 'user'), ('admin', 'admin'), ('superuser', 'root')]:
            response = self.client.get('/api/admin/accounts/', {'role': role})
            self.assertEqual([a['username'] for a in response.data['results']], [username])
        response = self.client.post(f'/api/superuser/admin-registrations/{application.pk}/decision/', {'status': 'REJECTED'})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertEqual(self.client.patch(f'/api/admin/accounts/{self.root.pk}/', {'is_active': False}).status_code, 400)

    def test_public_user_registration_cannot_elevate_access(self):
        response = self.client.post('/api/user/register/', {'username': 'newuser', 'email': 'new@example.com', 'password': self.password, 'is_staff': True, 'is_superuser': True})
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='newuser')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_demo_seed_is_repeatable_and_keeps_credentials_local(self):
        with TemporaryDirectory() as directory, override_settings(DEBUG=True, BASE_DIR=Path(directory)):
            call_command('seed_demo')
            access_file = Path(directory) / 'LOCAL_ACCESS.txt'
            original = access_file.read_text(encoding='utf-8')
            call_command('seed_demo')
            self.assertEqual(access_file.read_text(encoding='utf-8'), original)
            self.assertEqual(Enquiry.objects.filter(user__username='demo_user').count(), 5)
            self.assertFalse(User.objects.filter(username__in=['demo_admin', 'demo_superuser']).exists())
            self.assertFalse(User.objects.get(username='demo_pending_admin').is_staff)
            self.assertEqual(Lead.objects.filter(enquiry__user__username='demo_user', status='CONVERTED').count(), 1)
