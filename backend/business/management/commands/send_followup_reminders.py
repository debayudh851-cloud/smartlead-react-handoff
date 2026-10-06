from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from business.models import LeadFollowUp, Notification


class Command(BaseCommand):
    help = 'Create idempotent in-app due follow-up reminders; schedule externally.'

    @transaction.atomic
    def handle(self, *args, **options):
        count = 0
        for followup in LeadFollowUp.objects.select_for_update().filter(completed=False, reminded_at=None, follow_up_date__lte=timezone.now()).select_related('lead', 'created_by'):
            recipient = followup.lead.assigned_to or followup.created_by
            if recipient.is_active and recipient.is_staff:
                _, created = Notification.objects.get_or_create(event_key=f'due:{followup.pk}:{followup.follow_up_date.isoformat()}', defaults={'recipient': recipient, 'lead': followup.lead, 'kind': 'FOLLOWUP_DUE', 'message': f'Follow-up #{followup.pk} is due for lead #{followup.lead_id}.'})
                followup.reminded_at = timezone.now()
                followup.save(update_fields=['reminded_at'])
                count += int(created)
        self.stdout.write(f'{count} due reminder(s) created.')
