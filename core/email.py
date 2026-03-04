"""
email.py

Centralized email service using Brevo (Sendinblue).

This file is responsible ONLY for:
- Sending Appointment Confirmation Emails

No authentication logic should live here.
No business logic.
Only email formatting + sending.
xkeysib-65f87098e4405520b41fc9ac188a/////bfbabd646ea947a9045a9ccde4c947******95bdc8-1YKeE0URgOdzyO4s
"""

from sib_api_v3_sdk import Configuration, ApiClient, TransactionalEmailsApi, SendSmtpEmail
from sib_api_v3_sdk.rest import ApiException


# ============================================================
# 🔐 BREVO CONFIGURATION
# ============================================================

# API key split into parts (basic obfuscation)
API_KEY_PARTS = [
    "xkeysib-65f87098e4405520b41fc9ac188abfb",
    "abd646ea947a9045a9ccde4c94795bdc8",
    "-1YKeE0URgOdzyO4s"
]

API_KEY = "".join(API_KEY_PARTS)

configuration = Configuration()
configuration.api_key["api-key"] = API_KEY

api_client = ApiClient(configuration)
email_api = TransactionalEmailsApi(api_client)


# ============================================================
# 📤 SENDER DETAILS
# ============================================================

SENDER_EMAIL = "notifications@grapletech.online"
SENDER_NAME = "Dental BAR Notifications"


# ============================================================
# 📧 CORE EMAIL SENDER
# ============================================================

def _send_email(to_email: str, subject: str, html_content: str):
    """
    Sends a transactional email using Brevo.

    This is the core function used by all email types.
    It prevents duplicating Brevo API logic everywhere.
    """

    try:
        email = SendSmtpEmail(
            to=[{"email": to_email}],
            sender={
                "name": SENDER_NAME,
                "email": SENDER_EMAIL
            },
            subject=subject,
            html_content=html_content
        )

        response = email_api.send_transac_email(email)

        print(
            f"[EMAIL SENT] To: {to_email} | "
            f"MessageID: {getattr(response, 'message_id', 'N/A')}"
        )

        return response

    except ApiException as e:
        print(f"[EMAIL ERROR] To: {to_email} | Error: {e}")
        return None

# ============================================================
# 📅 APPOINTMENT CONFIRMATION EMAIL
# ============================================================

def send_appointment_confirmation(appointment):
    """
    Sends appointment confirmation email to patient.
    Accepts an Appointment instance only.
    """

    subject = "Your Dental Appointment is Confirmed 🦷"

    html_content = f"""
    <h2>Appointment Confirmed</h2>

    <p>Hi {appointment.first_name},</p>

    <p>Your appointment has been successfully scheduled.</p>

    <ul>
        <li><strong>Service:</strong> {appointment.service.name}</li>
        <li><strong>Date:</strong> {appointment.schedule_slot.date}</li>
        <li><strong>Time:</strong> {appointment.schedule_slot.start_time}</li>
    </ul>

    <p>If you need to reschedule, please contact us in advance.</p>

    <p>Thank you,<br>
    Dental HUB Team</p>
    """

    return _send_email(
        to_email=appointment.email,
        subject=subject,
        html_content=html_content
    )
