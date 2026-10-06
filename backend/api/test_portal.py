from django.test import TestCase
from django.urls import resolve
from django.contrib.staticfiles import finders


class PortalTests(TestCase):
    def test_home_and_reset_links(self):
        for path in ['/accounts/', '/user/reset-password/MQ/example-token/', '/admin/reset-password/MQ/example-token/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Account portal')
            self.assertContains(response, '/static/api/portal.js')

    def test_all_handoff_endpoints_resolve(self):
        for path in ['user/register/', 'user/forgot-password/', 'user/reset-password/',
                     'user/forgot-username/', 'admin/users/', 'admin/forgot-password/',
                     'admin/reset-password/', 'token/', 'token/refresh/']:
            self.assertIsNotNone(resolve('/api/' + path).func)

    def test_interface_assets_available(self):
        for path in ['api/portal.js', 'api/portal.css']:
            self.assertIsNotNone(finders.find(path))
