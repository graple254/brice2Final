import uuid

from django.utils.deprecation import MiddlewareMixin
from .models import Visitor


class VisitorTrackingMiddleware(MiddlewareMixin):
    """
    Tracks anonymous visitors once per session.
    No blocking calls. No external APIs.
    """

    def process_request(self, request):
        if not request.session.session_key:
            request.session.create()

        session_id = request.session.session_key

        # Already tracked
        if Visitor.objects.filter(session_id=session_id).exists():
            return

        Visitor.objects.create(
            session_id=session_id,
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
        )

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")
