
"""
email_utils.py
E-mail sending functionality for the Claimix backend.
"""

import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from the root .env file
root_dir = Path(__file__).parent.parent
load_dotenv(root_dir / '.env')

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")  # optional; fall back to SMTP_USER


def send_email(to: str, subject: str, html: str, *, retry: bool = True) -> bool:
    """
    Send an HTML e-mail using STARTTLS on port 587 or SMTPS on port 465.
    Returns True on success, False on failure.
    
    Args:
        to: Recipient email address
        subject: Email subject
        html: Email content in HTML format
        retry: Whether to retry once if sending fails
    """
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD]):
        print("[EMAIL] Missing SMTP configuration. Email not sent.")
        return False

    from_addr = EMAIL_FROM or SMTP_USER
    attempts = 2 if retry else 1

    for attempt in range(1, attempts + 1):
        try:
            # Create message
            msg = EmailMessage()
            msg["From"] = from_addr
            msg["To"] = to
            msg["Subject"] = subject
            msg.set_content(html, subtype="html")
            
            # Debug log
            print(f"[EMAIL] Connecting to {SMTP_HOST}:{SMTP_PORT} (attempt {attempt})...")
            
            # Create SMTP connection
            if int(SMTP_PORT) == 465:
                server = smtplib.SMTP_SSL(SMTP_HOST, int(SMTP_PORT), timeout=10)
            else:
                server = smtplib.SMTP(SMTP_HOST, int(SMTP_PORT), timeout=10)
            
            try:
                # Identify ourselves to the SMTP server
                server.ehlo()
                
                # Start TLS if needed (for port 587)
                if int(SMTP_PORT) == 587:
                    print("[EMAIL] Starting TLS...")
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                
                # Login if credentials provided
                print(f"[EMAIL] Logging in as {SMTP_USER}...")
                server.login(SMTP_USER, SMTP_PASSWORD)
                
                # Send the email
                print(f"[EMAIL] Sending email to {to}...")
                server.send_message(msg)
                print("[EMAIL] Email sent successfully")
                return True
                
            finally:
                # Always close the connection
                try:
                    server.quit()
                except Exception:
                    pass
                
        except Exception as e:
            print(f"[EMAIL] Failed to send email (attempt {attempt}): {str(e)}")
            if attempt < attempts:
                time.sleep(1.0)  # small backoff

    return False
