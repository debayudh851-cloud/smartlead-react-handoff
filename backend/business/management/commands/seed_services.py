from django.core.management.base import BaseCommand
from django.db import transaction
from business.models import Category, Service, ServicePackage, SEOContent


class Command(BaseCommand):
    help = 'Create/update sample service catalogue without creating users or credentials.'

    @transaction.atomic
    def handle(self, *args, **options):
        for category, name, slug, price in [
            ('Software Development', 'Web Development', 'web-development', 40000),
            ('Software Development', 'Mobile App Development', 'mobile-app-development', 75000),
            ('Design', 'UI/UX Design', 'ui-ux-design', 25000),
            ('Marketing', 'Digital Marketing', 'digital-marketing', 20000),
            ('Artificial Intelligence', 'AI/ML Solutions', 'ai-ml-solutions', 60000),
        ]:
            from django.utils.text import slugify
            cat, _ = Category.objects.get_or_create(name=category, defaults={'slug': slugify(category)})
            service, _ = Service.objects.get_or_create(slug=slug, defaults={'category': cat, 'name': name, 'description': f'Professional {name.lower()} tailored to your business. Submit an enquiry to discuss requirements.', 'features': ['Discovery consultation', 'Project planning', 'Quality assurance'], 'starting_price': price})
            ServicePackage.objects.get_or_create(service=service, name='Starter', defaults={'price': price, 'description': 'Starting package; final scope is agreed after enquiry.', 'features': ['Consultation', 'Delivery plan']})
            SEOContent.objects.get_or_create(service=service, defaults={'title': name + ' | SMARTLEAD', 'meta_description': service.description[:320], 'keywords': [name.lower()]})
        self.stdout.write(self.style.SUCCESS('Sample service catalogue ready.'))
