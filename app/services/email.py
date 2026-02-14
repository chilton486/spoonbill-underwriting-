import logging
from typing import Optional

from ..config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def _send(to_email: str, subject: str, html_content: str) -> bool:
        settings = get_settings()
        api_key = settings.sendgrid_api_key
        from_email = settings.email_from_address

        if not api_key:
            logger.info(f"Email not sent (no SENDGRID_API_KEY): to={to_email} subject={subject}")
            return False

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content,
            )
            sg = SendGridAPIClient(api_key)
            response = sg.send(message)
            logger.info(f"Email sent: to={to_email} subject={subject} status={response.status_code}")
            return response.status_code in (200, 201, 202)
        except Exception as e:
            logger.error(f"Email send failed: to={to_email} subject={subject} error={e}")
            return False

    @staticmethod
    def send_invite(to_email: str, invite_url: str, practice_name: str) -> bool:
        subject = f"You've been invited to join {practice_name} on Spoonbill"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Welcome to Spoonbill</h2>
            <p>You've been invited to manage <strong>{practice_name}</strong> on Spoonbill.</p>
            <p>Click the link below to set your password and get started:</p>
            <p><a href="{invite_url}" style="display: inline-block; padding: 12px 24px; background: #000; color: #fff; text-decoration: none; border-radius: 4px;">Set Your Password</a></p>
            <p style="color: #666; font-size: 0.875rem;">This link expires in 7 days. If it has expired, contact your Spoonbill representative for a new invite.</p>
        </div>
        """
        return EmailService._send(to_email, subject, html)

    @staticmethod
    def send_claim_approved(to_email: str, claim_token: str, amount_cents: int) -> bool:
        amount = f"${amount_cents / 100:,.2f}"
        subject = f"Claim {claim_token} Approved"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Claim Approved</h2>
            <p>Your claim <strong>{claim_token}</strong> for <strong>{amount}</strong> has been approved.</p>
            <p>Payment will be processed shortly. You can track the status in your Practice Portal.</p>
        </div>
        """
        return EmailService._send(to_email, subject, html)

    @staticmethod
    def send_payment_confirmed(to_email: str, claim_token: str, amount_cents: int) -> bool:
        amount = f"${amount_cents / 100:,.2f}"
        subject = f"Payment Confirmed for {claim_token}"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Payment Confirmed</h2>
            <p>Payment of <strong>{amount}</strong> for claim <strong>{claim_token}</strong> has been confirmed.</p>
            <p>View the full details in your Practice Portal.</p>
        </div>
        """
        return EmailService._send(to_email, subject, html)

    @staticmethod
    def send_payment_failed_internal(to_email: str, claim_token: str, failure_code: Optional[str], failure_message: Optional[str]) -> bool:
        subject = f"[INTERNAL] Payment Failed for {claim_token}"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Payment Failed</h2>
            <p>Payment for claim <strong>{claim_token}</strong> has failed.</p>
            <p><strong>Code:</strong> {failure_code or 'N/A'}</p>
            <p><strong>Message:</strong> {failure_message or 'N/A'}</p>
            <p>Action required: Review in the Internal Console and retry or resolve.</p>
        </div>
        """
        return EmailService._send(to_email, subject, html)
