from .managers import clear_current_business, set_current_business


class CurrentBusinessMiddleware:
    """Stash the negocio of the logged-in user in a threadlocal for the duration
    of the request so TenantManager can filter by it automatically."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        negocio = None
        if user is not None and user.is_authenticated:
            negocio = getattr(user, "negocio", None)
        set_current_business(negocio)
        try:
            response = self.get_response(request)
        finally:
            clear_current_business()
        return response
