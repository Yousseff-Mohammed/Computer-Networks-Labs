import imaplib
import email
import ssl
import logging
from email.header import decode_header
from email.message import Message
from typing import Optional
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Helper: decode RFC-2047 encoded header values safely
def _decode_header_value(raw_value: str) -> str:
    parts = decode_header(raw_value)
    decoded_parts = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return " ".join(decoded_parts)

# Helper: extract the plain-text body from a (possibly multipart) message
def _extract_body(msg: email.message.Message) -> str:
    plain_body = None
    html_body  = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition  = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in disposition:
                continue

            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            charset = part.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")

            if content_type == "text/plain" and plain_body is None:
                plain_body = decoded
            elif content_type == "text/html" and html_body is None:
                html_body = decoded
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        if payload:
            if msg.get_content_type() == "text/plain":
                plain_body = payload.decode(charset, errors="replace")
            else:
                html_body = payload.decode(charset, errors="replace")

    return plain_body or html_body or "(no readable body found)"

# Core fetch function
def fetch_latest_email(
    imap_host: str,
    imap_port: int,
    email_address: str,
    password: str,
    mailbox: str = "INBOX",
    n: int = 1,
) -> Optional[dict]:

    log.info("Connecting to IMAP server %s:%s…", imap_host, imap_port)

    try:
        # Open TCP connection and wrap in SSL
        ctx  = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(imap_host, imap_port, ssl_context=ctx)

        log.info("TCP connection established. Authenticating as %s…", email_address)

        # LOGIN command
        mail.login(email_address, password)
        log.info("Authenticated successfully.")

        # SELECT mailbox
        status, messages = mail.select(mailbox, readonly=True)
        if status != "OK":
            log.error("Could not open mailbox '%s': %s", mailbox, messages)
            mail.logout()
            return None

        total_messages = int(messages[0])
        log.info("Mailbox '%s' selected – %d message(s) present.", mailbox, total_messages)

        if total_messages == 0:
            log.warning("Mailbox is empty.")
            mail.logout()
            return None

        # SEARCH for all messages; take the latest n IDs
        status, data = mail.search(None, "ALL")
        if status != "OK":
            log.error("SEARCH command failed.")
            mail.logout()
            return None

        mail_ids   = data[0].split()
        latest_ids = mail_ids[-n:]                # last n message IDs
        latest_id  = latest_ids[-1]               # the very last one

        # FETCH the raw RFC-822 message
        log.info("Fetching message ID %s…", latest_id.decode())
        status, msg_data = mail.fetch(latest_id, "(RFC822)")
        if status != "OK":
            log.error("FETCH command failed for message ID %s.", latest_id)
            mail.logout()
            return None

        # Parse the raw bytes into a Message object
        raw_email = msg_data[0][1]
        msg       = email.message_from_bytes(raw_email)

        result = {
            "from"   : _decode_header_value(msg.get("From",    "N/A")),
            "to"     : _decode_header_value(msg.get("To",      "N/A")),
            "subject": _decode_header_value(msg.get("Subject", "N/A")),
            "date"   : msg.get("Date", "N/A"),
            "body"   : _extract_body(msg),
        }

        # LOGOUT – closes the TCP connection cleanly
        mail.logout()
        log.info("TCP connection closed (LOGOUT sent).")

        return result

    except imaplib.IMAP4.error as exc:
        log.error("IMAP protocol error: %s", exc)
    except TimeoutError:
        log.error("Connection timed out while connecting to %s:%s", imap_host, imap_port)
    except ssl.SSLError as exc:
        log.error("SSL/TLS error: %s", exc)
    except Exception as exc:
        log.error("Unexpected error: %s", exc)

    return None


# Pretty-print helper
def print_email(email_dict: dict) -> None:
    separator = "─" * 60
    print(separator)
    print(f"From    : {email_dict['from']}")
    print(f"To      : {email_dict['to']}")
    print(f"Subject : {email_dict['subject']}")
    print(f"Date    : {email_dict['date']}")
    print(separator)
    print(email_dict['body'])
    print(separator)

# Quick-test entry-point
if __name__ == "__main__":
    IMAP_HOST = "imap.gmail.com"                    # Gmail IMAP host
    IMAP_PORT = 993                                 # IMAPS (SSL)
    EMAIL     = "ymohammedjoe1@gmail.com"           # Gmail address
    PASSWORD  = os.environ.get("EMAIL_PASSWORD")    # Google App Password for IMAP authentication

    result = fetch_latest_email(
        imap_host     = IMAP_HOST,
        imap_port     = IMAP_PORT,
        email_address = EMAIL,
        password      = PASSWORD,
    )

    if result:
        print("\n── Latest E-Mail ──")
        print_email(result)
    else:
        print("No e-mail retrieved.")