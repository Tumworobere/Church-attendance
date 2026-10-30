from django.conf import settings


def church(request):
    return {"CHURCH_NAME": settings.CHURCH_NAME, "CHURCH_BRANCH": settings.CHURCH_BRANCH}
