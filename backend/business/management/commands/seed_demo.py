"""Seed fictional local demo records; credentials never enter source control."""
import secrets
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from business.models import EmployeeAccess, Enquiry, LeadFollowUp, Review, Service, Wishlist
from business.operations import create_enquiry, update_lead
from business.predictor import predict


class Command(BaseCommand):
    help = 'Add fictional demo users, admins and requirements; save new credentials only to ignored LOCAL_ACCESS.txt.'

    def add_arguments(self, parser):
        parser.add_argument('--with-privileged-accounts', action='store_true', help='Explicitly create demo admin and superuser accounts for local testing.')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo seeding is enabled only with DEBUG=True.')
        User = get_user_model()
        credentials = []
        with transaction.atomic():
            accounts = {}
            specifications = [('demo_user', False, False)]
            if options['with_privileged_accounts']:
                specifications += [('demo_admin', True, False), ('demo_superuser', True, True)]
            for name, staff, root in specifications:
                user = User.objects.filter(username=name).first()
                email = name + '@example.com'
                if user and (user.email != email or user.is_staff != staff or user.is_superuser != root):
                    raise CommandError(f'{name} is already in use or has been modified; existing accounts were left unchanged.')
                if not user:
                    password = secrets.token_urlsafe(24)
                    user = User.objects.create_user(name, email, password, is_staff=staff, is_superuser=root, first_name='Demo', last_name=name.removeprefix('demo_').replace('_', ' ').title())
                    credentials.append(f'{name}: {password}')
                accounts[name] = user
            user = accounts['demo_user']
            admin = accounts.get('demo_admin')
            if admin:
                EmployeeAccess.objects.get_or_create(user=admin, defaults={'must_change_password': True, 'provisioned_by': accounts['demo_superuser']})
            call_command('seed_services')
            cases = [
                ('web-development', 'Build a responsive website for a fictional bakery with a menu and enquiry form.', '55000', 'NEW'),
                ('mobile-app-development', 'Develop an appointment booking app for a fictional fitness studio.', '120000', 'CONTACTED'),
                ('ui-ux-design', 'Design an accessible dashboard and clickable prototype for a fictional startup.', '45000', 'FOLLOW_UP'),
                ('digital-marketing', 'Plan a three-month search and social campaign for a fictional local shop.', '30000', 'CONVERTED'),
                ('ai-ml-solutions', 'Create a demonstration customer enquiry classification tool.', '90000', 'QUALIFIED'),
            ]
            for index, (slug, requirement, budget, status) in enumerate(cases):
                service = Service.objects.get(slug=slug)
                key = f'fictional-demo-{slug}'
                enquiry = Enquiry.objects.filter(user=user, idempotency_key=key).first()
                if not enquiry:
                    enquiry, _ = create_enquiry(user, {'service': service, 'requirement': '[DEMO] ' + requirement, 'contact_email': user.email, 'contact_phone': '', 'budget': budget, 'traffic_source': 'Google', 'total_visits': index+2, 'time_on_website': 300+index*150, 'page_views_per_visit': 2.0}, key=key)
                    lead = update_lead(enquiry.lead, admin, {'assigned_to': admin})
                    if status != 'NEW':
                        lead = update_lead(lead, admin, {'status': 'CONTACTED'})
                        if status != 'CONTACTED':
                            lead = update_lead(lead, admin, {'status': status})
                    if status == 'FOLLOW_UP':
                        LeadFollowUp.objects.create(lead=lead, created_by=admin or user, notes='[DEMO] Discuss prototype scope and timeline.', follow_up_date=timezone.now()+timedelta(days=1))
                    predict(lead)
                Wishlist.objects.get_or_create(user=user, service=service)
            Review.objects.get_or_create(user=user, service=Service.objects.get(slug='digital-marketing'), defaults={'rating': 5, 'comment': '[DEMO] Clear project planning and helpful communication.', 'is_approved': True})
        destination = Path(settings.BASE_DIR) / 'LOCAL_ACCESS.txt'
        if credentials:
            with destination.open('a', encoding='utf-8') as output:
                output.write('\nLOCAL DEMO ACCESS — fictional records; never publish this file.\n')
                output.write('\n'.join(credentials) + '\n')
                output.write('User: /user/ | Admin: /admin-portal/ | Superuser: /superuser/\n')
        self.stdout.write(self.style.SUCCESS('Demo ready: five requirements, follow-up, review, wishlist and actual demo model scores.'))
        self.stdout.write(f'Local login details: {destination}')
