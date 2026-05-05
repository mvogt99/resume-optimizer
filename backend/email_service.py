"""ZOHO SMTP email service for Resume Optimizer."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

ZOHO_SMTP_HOST = os.environ.get("ZOHO_IMAP_OUT_SERVER", "smtppro.zoho.com")
ZOHO_SMTP_PORT = int(os.environ.get("ZOHO_IMAP_OUT_PORT", "465"))
ZOHO_USERNAME = os.environ.get("ZOHO_USERNAME", "contact@concurrentonline.ai")
ZOHO_PASSWORD = os.environ.get("SMTP_PASSWORD") or os.environ.get("ZOHO_PASSWORD", "")
ADMIN_EMAIL = "mvogt99@gmail.com"


def send_approval_request(new_user_email: str, approve_url: str, reject_url: str, env_name: str) -> bool:
    """Send approval request email to admin via ZOHO SMTP.

    Args:
        new_user_email: Email address of the new user requesting access
        approve_url: URL for admin to approve the request
        reject_url: URL for admin to reject the request
        env_name: Environment name (e.g., "Development", "Production")

    Returns:
        True on success, False on failure (never raises)
    """
    try:
        subject = f"Resume Optimizer Access Request - {env_name}"
        html_body = f"""
        <html>
            <body style="font-family: sans-serif; color: #333;">
                <h2 style="color: #1f2937;">New Registration Request</h2>
                <p><b>Email:</b> {new_user_email}</p>
                <p><b>Environment:</b> {env_name}</p>
                <br>
                <p>
                    <a href="{approve_url}" style="background:#22c55e;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;margin-right:16px;display:inline-block;font-weight:bold;">✓ Approve Access</a>
                    <a href="{reject_url}" style="background:#ef4444;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block;font-weight:bold;">✗ Reject Request</a>
                </p>
                <br>
                <p style="color:#666;font-size:12px;">Links expire in 7 days.</p>
            </body>
        </html>
        """

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = ZOHO_USERNAME
        msg["To"] = ADMIN_EMAIL

        # Attach HTML
        msg.attach(MIMEText(html_body, "html"))

        # Send via ZOHO SMTP_SSL
        with smtplib.SMTP_SSL(ZOHO_SMTP_HOST, ZOHO_SMTP_PORT, timeout=10) as server:
            server.login(ZOHO_USERNAME, ZOHO_PASSWORD)
            server.send_message(msg)

        logger.info("Approval request email sent to admin for user %s", new_user_email)
        return True

    except Exception as e:
        logger.warning("Failed to send approval request email for user %s: %s", new_user_email, e)
        return False


def send_password_reset(user_email: str, reset_url: str, env_name: str) -> bool:
    """Send password reset email via ZOHO SMTP.

    Args:
        user_email: Email address of the user
        reset_url: URL containing reset token
        env_name: Environment name (e.g., "Development", "Production")

    Returns:
        True on success, False on failure (never raises)
    """
    try:
        subject = f"Resume Optimizer — Password Reset"
        html_body = f"""
        <html>
            <body style="font-family: sans-serif; color: #333;">
                <h2 style="color: #1f2937;">Password Reset Request</h2>
                <p>Click the button below to reset your password. This link expires in <b>15 minutes</b> and can only be used once.</p>
                <br>
                <a href="{reset_url}" style="background:#3b82f6;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block;">Reset Password</a>
                <br><br>
                <p style="color:#666;font-size:12px;">If you did not request a password reset, you can safely ignore this email.</p>
            </body>
        </html>
        """

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = ZOHO_USERNAME
        msg["To"] = user_email

        # Attach HTML
        msg.attach(MIMEText(html_body, "html"))

        # Send via ZOHO SMTP_SSL
        with smtplib.SMTP_SSL(ZOHO_SMTP_HOST, ZOHO_SMTP_PORT, timeout=10) as server:
            server.login(ZOHO_USERNAME, ZOHO_PASSWORD)
            server.send_message(msg)

        logger.info("Password reset email sent to %s", user_email)
        return True

    except Exception as e:
        logger.warning("Failed to send password reset email to %s: %s", user_email, e)
        return False
