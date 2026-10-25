"""Explicit invitation delivery; never report success before SMTP accepts mail."""

import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse


def configured(settings):
    url = urlparse(settings.public_url)
    return bool(
        settings.smtp_host
        and settings.smtp_from
        and url.scheme == "https"
        and url.netloc
        and not url.query
        and not url.fragment
    )


def send_invitation(settings, invitation, workspace, inviter):
    if not configured(settings):
        return {
            "status": "not_configured",
            "message": "Email delivery is not configured. Share the private invitation link directly.",
        }
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = invitation["email"]
    message["Subject"] = f"Invitation to {workspace} on PolicyLens"
    url = settings.public_url.rstrip("/") + "/join#" + invitation["token"]
    message.set_content(
        f"{inviter} invited you to {workspace} on PolicyLens as {invitation['role']}.\n\nAccept your invitation:\n{url}\n\nSign in with your existing account, or create your account on the invitation page. This invitation expires in 48 hours and works once. Membership is granted only after acceptance.\n\nIf you were not expecting this invitation, ignore this email."
    )
    transport = smtplib.SMTP_SSL if settings.smtp_security == "ssl" else smtplib.SMTP
    try:
        kwargs = {"timeout": 15}
        if settings.smtp_security == "ssl":
            kwargs["context"] = ssl.create_default_context()
        with transport(settings.smtp_host, settings.smtp_port, **kwargs) as smtp:
            if settings.smtp_security == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(
                    settings.smtp_username, settings.smtp_password.get_secret_value()
                )
            refused = smtp.send_message(message)
            if refused:
                return {
                    "status": "failed",
                    "message": "The mail server refused delivery. Share the invitation link or try a new invitation.",
                }
        return {
            "status": "sent",
            "message": "The mail server accepted the invitation for delivery. Check the recipient's inbox or spam folder.",
        }
    except (OSError, smtplib.SMTPException):
        return {
            "status": "failed",
            "message": "The invitation was created, but email delivery failed. Share the private link or try a new invitation.",
        }
