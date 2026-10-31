from django.utils.functional import SimpleLazyObject

from .models import Branch

SESSION_KEY = "branch_id"


def current_branch(request):
    """The branch picked in the header dropdown; otherwise the oldest branch (Kisaasi), not the alphabetically
    first, so adding a branch doesn't change what everyone sees by default."""
    pk = request.session.get(SESSION_KEY)
    return (pk and Branch.objects.filter(pk=pk).first()) or Branch.objects.order_by("pk").first()


class BranchMiddleware:
    """Sets request.branch. Every view scopes members, visitors and services to it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.branch = SimpleLazyObject(lambda: current_branch(request))
        return self.get_response(request)
