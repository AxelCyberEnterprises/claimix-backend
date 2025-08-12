"""
email_utils.py
──────────────────────────────────────────────────────────────────────────────
E-mail sending functionality for the Claimix backend.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
from dotenv import load_dotenv

# Load environment variables from the root .env file
import os
from pathlib import Path

# Get the root directory (one level up from this file's directory)
root_dir = Path(__file__).parent.parent
load_dotenv(root_dir / '.env')
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("IMAP_USERNAME", "")
SMTP_PASSWORD = os.getenv("IMAP_PASSWORD", "")

def send_email(to: str, subject: str, html: str, *, retry: bool = True) -> None:
    """
    Send an HTML e-mail using STARTTLS on port 587. Includes one optional retry.
    
    Args:
        to: Recipient email address
        subject: Email subject
        html: Email content in HTML format
        retry: Whether to retry once if sending fails
    """
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD]):
        print("[EMAIL] Missing SMTP configuration. Email not sent.")
        return

    try:
        # Create message
        msg = EmailMessage()
        msg["From"] = SMTP_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(html, subtype="html")
        
        # Debug log
        print(f"[EMAIL] Connecting to {SMTP_HOST}:{SMTP_PORT}...")
        
        # Create SMTP connection
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
            
        finally:
            # Always close the connection
            server.quit()
            
    except Exception as e:
        error_msg = f"[EMAIL] Failed to send email: {str(e)}"
        print(error_msg)
        if retry:
            print("[EMAIL] Retrying...")
            send_email(to, subject, html, retry=False)
        else:
            print(error_msg)
            # Don't raise the exception to prevent crashing the application
