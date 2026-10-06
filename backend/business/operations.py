import logging
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Enquiry, Lead, LeadHistory, Notification

logger = logging.getLogger(__name__)


def notify_staff(kind, message, lead):
    for user in get_user_model().objects.filter(is_active=True, is_staff=True):
        Notification.objects.create(recipient=user, kind=kind, message=message, lead=lead)


@transaction.atomic
def create_enquiry(user, data, key=None):
    # Serialize submissions from the same user, including concurrent retries.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    if key:
        existing = Enquiry.objects.filter(user=user, idempotency_key=key).first()
        if existing:
            for name, value in data.items():
                if getattr(existing, name) != value:
                    raise ValidationError({'detail': 'Idempotency-Key already used for a different enquiry.'})
            return existing, False
    enquiry = Enquiry.objects.create(user=user, previous_enquiries=Enquiry.objects.filter(user=user).count(), idempotency_key=key, **data)
    lead = Lead.objects.create(enquiry=enquiry)
    LeadHistory.objects.create(lead=lead, actor=user, changes={'status': {'from': None, 'to': 'NEW'}})
    # In-app notifications share the transaction; all records commit together.
    notify_staff('NEW_ENQUIRY', f'New enquiry for {enquiry.service.name}', lead)
    return enquiry, True


TRANSITIONS = {
    'NEW': {'CONTACTED', 'NOT_CONVERTED'},
    'CONTACTED': {'FOLLOW_UP', 'QUALIFIED', 'CONVERTED', 'NOT_CONVERTED'},
    'FOLLOW_UP': {'CONTACTED', 'QUALIFIED', 'CONVERTED', 'NOT_CONVERTED'},
    'QUALIFIED': {'FOLLOW_UP', 'CONVERTED', 'NOT_CONVERTED'},
    'CONVERTED': set(), 'NOT_CONVERTED': set(),
}


@transaction.atomic
def update_lead(lead, actor, data):
    lead = Lead.objects.select_for_update().get(pk=lead.pk)
    changes = {}
    status = data.get('status', lead.status)
    if status != lead.status:
        if status not in TRANSITIONS[lead.status]:
            raise ValidationError({'status': f'Cannot transition from {lead.status} to {status}.'})
        changes['status'] = {'from': lead.status, 'to': status}
        lead.status = status
        lead.converted_at = timezone.now() if status == 'CONVERTED' else None
    if 'assigned_to' in data:
        assignee = data['assigned_to']
        new_id = assignee.pk if assignee else None
        if lead.assigned_to_id != new_id:
            changes['assigned_to'] = {'from': lead.assigned_to_id, 'to': new_id}
            lead.assigned_to = assignee
    if changes:
        lead.save()
        LeadHistory.objects.create(lead=lead, actor=actor, changes=changes)
        if 'status' in changes:
            Notification.objects.create(recipient=lead.enquiry.user, kind='ENQUIRY_STATUS', message=f'Your enquiry status is {lead.status}.', lead=lead)
        if 'assigned_to' in changes and lead.assigned_to:
            Notification.objects.create(recipient=lead.assigned_to, kind='LEAD_ASSIGNED', message=f'Lead #{lead.pk} assigned to you.', lead=lead)
    return lead
