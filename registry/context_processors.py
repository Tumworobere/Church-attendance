from django.conf import settings

from .models import Branch


def church(request):
    return {
        "CHURCH_NAME": settings.CHURCH_NAME,
        "branch": getattr(request, "branch", None),
        "branches": Branch.objects.all,  # callable: only queried if the template uses it
    }
