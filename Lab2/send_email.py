import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Core send function
def send_email(
    smtp_host: str,
    smtp_port: int,
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    subject: str,
    body: str,
    use_tls: bool = True,
) -> bool:

    # Build the MIME message
    msg = MIMEMultipart("alternative")
    msg["From"]    = sender_email
    msg["To"]      = recipient_email
    msg["Subject"] = subject

    # Attach plain-text part (HTML part can be added here too)
    msg.attach(MIMEText(body, "plain"))

    log.info("Preparing to send e-mail to %s via %s:%s", recipient_email, smtp_host, smtp_port)

    try:
        if use_tls:
            # STARTTLS connection (port 587)
            log.info("Establishing TCP connection with %s:%s (STARTTLS)…", smtp_host, smtp_port)
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.set_debuglevel(0)          # set to 1 for raw SMTP dialogue

                # Identify ourselves to the server
                server.ehlo()

                # Upgrade the plain TCP socket to TLS
                server.starttls(context=ssl.create_default_context())
                server.ehlo()                     # re-identify over TLS

                # Authenticate
                log.info("Authenticating as %s…", sender_email)
                server.login(sender_email, sender_password)

                # Dialogue: DATA command + message body
                log.info("Sending message…")
                server.sendmail(sender_email, recipient_email, msg.as_string())

                # Connection closed automatically by context manager (QUIT sent)
                log.info("TCP connection closed.")
        else:
            # Implicit SSL connection (port 465)
            log.info("Establishing TCP connection with %s:%s (SSL)…", smtp_host, smtp_port)
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=15) as server:
                server.set_debuglevel(0)
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, msg.as_string())
                log.info("TCP connection closed.")

        log.info("E-mail sent successfully to %s", recipient_email)
        return True

    except smtplib.SMTPAuthenticationError as exc:
        log.error("Authentication failed – check your credentials. Detail: %s", exc)
    except smtplib.SMTPRecipientsRefused as exc:
        log.error("Recipient refused by server: %s", exc)
    except smtplib.SMTPException as exc:
        log.error("SMTP error occurred: %s", exc)
    except TimeoutError:
        log.error("Connection timed out while connecting to %s:%s", smtp_host, smtp_port)
    except Exception as exc:                          # catch-all safety net
        log.error("Unexpected error: %s", exc)

    return False

# Quick-test entry-point
if __name__ == "__main__":
    SMTP_HOST      = "smtp.gmail.com"                   # Gmail SMTP host
    SMTP_PORT      = 587                                # STARTTLS
    SENDER         = "ymohammedjoe1@gmail.com"          # Gmail address
    PASSWORD       = os.environ.get("EMAIL_PASSWORD")   # Gmail app password
    RECIPIENT      = "youssef.xd777@gmail.com"          # any valid address
    SUBJECT        = "Test From My Code"
    BODY           = (
        "Hello!\n\n"
        "This is a test e-mail sent by the Python SMTP client\n\n"
        "Regards,\nThe Email Client"
    )

    success = send_email(
        smtp_host       = SMTP_HOST,
        smtp_port       = SMTP_PORT,
        sender_email    = SENDER,
        sender_password = PASSWORD,
        recipient_email = RECIPIENT,
        subject         = SUBJECT,
        body            = BODY,
    )

    print("Send status:", "SUCCESS" if success else "FAILED")