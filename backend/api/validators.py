import re
from django.core.exceptions import ValidationError


class LetterNumberPasswordValidator:
    def validate(self, password, user=None):
        if not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
            raise ValidationError('Password must contain at least one letter and one number.', code='password_letter_number')

    def get_help_text(self):
        return 'Your password must contain at least one letter and one number.'


class DifferentPasswordValidator:
    def validate(self, password, user=None):
        if user is not None and user.pk and user.check_password(password):
            raise ValidationError('New password must be different from your current password.', code='password_unchanged')

    def get_help_text(self):
        return 'Your new password must be different from your current password.'


def validate_single_at_email(value):
    if value.count('@') != 1:
        raise ValidationError('Email must contain exactly one @ symbol.', code='invalid_email')
