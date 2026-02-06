from .models import User

def redirect_user_by_role(user):
    if user.is_superuser:
        return "admin:index"

    if user.role == User.STAFF:
        return "staff_dashboard"

    if user.role == User.DENTIST:
        return "dentist_dashboard"

    if user.role == User.PATIENT:
        return "index"

    return "login"
