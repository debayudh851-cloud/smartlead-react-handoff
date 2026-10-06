from django.shortcuts import redirect
from .models import EmployeeAccess


class EmployeePasswordMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/') and request.user.is_authenticated and request.user.is_staff and not request.user.is_superuser and EmployeeAccess.objects.filter(user=request.user, must_change_password=True).exists():
            return redirect('/admin-portal/')
        return self.get_response(request)
