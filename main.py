# main.py
# Goal: Run the email agent continuously, checking every 60 seconds
# This is the final combined version of all previous phases

# ── Step 1: Import libraries ───────────────────────────────────────────────────

import imaplib
import smtplib
import email
import email.mime.text
import email.mime.multipart
import os
import time
import logging          # handles writing to our log file professionally
from datetime import datetime
from dotenv import load_dotenv
import anthropic

# ── Step 2: Set up logging ─────────────────────────────────────────────────────

# Logging is like print() but it also:
#   - Adds a timestamp to every message automatically
#   - Saves messages to a file AND shows them in the terminal at the same time
#   - Has different levels: INFO (normal), WARNING (something odd), ERROR (problem)

logging.basicConfig(
    level=logging.INFO,

    # %(asctime)s   = timestamp like "2026-07-17 14:30:00"
    # %(levelname)s = INFO, WARNING, or ERROR
    # %(message)s   = the actual message we log
    format="%(asctime)s [%(levelname)s] %(message)s",

    handlers=[
        # This writes log messages to a file called agent.log
        logging.FileHandler("agent.log"),
        # This also shows log messages in the terminal
        logging.StreamHandler()
    ]
)

# ── Step 3: Load credentials ───────────────────────────────────────────────────

load_dotenv()

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")

if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, ANTHROPIC_API_KEY]):
    logging.error("Missing values in .env file. Please check GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and ANTHROPIC_API_KEY")
    exit()

# How many seconds to wait between each inbox check
# 60 = check once per minute
CHECK_INTERVAL = 60

# ── Step 4: System prompt ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a professional email assistant for a freelance photographer and IT student 
based in Osaka, Japan. Your job is to help manage incoming emails.

When you receive an email, you must do TWO things:

1. CLASSIFY the email into exactly one of these categories:
   - INQUIRY: Someone asking about services, prices, or availability
   - COMPLAINT: Someone expressing dissatisfaction or reporting a problem  
   - SPAM: Promotional emails, scams, or irrelevant messages
   - PERSONAL: Messages from friends, family, or personal contacts
   - OTHER: Anything that doesn't fit the above categories

2. WRITE A REPLY that is:
   - Professional but friendly in tone
   - Short and to the point (3-5 sentences maximum)
   - Appropriate for the category (don't reply to spam)
   - Written as if you are Prashant himself

Format your response EXACTLY like this — do not change the format:
CATEGORY: [category name]
REPLY:
[your reply here]

If the email is SPAM, use this exact reply:
CATEGORY: SPAM
REPLY:
No reply needed.
"""

# ── Step 5: Tracking file for replied emails ───────────────────────────────────

REPLIED_IDS_FILE = "replied_ids.txt"

def load_replied_ids():
    """Read the list of email IDs we have already replied to."""
    if not os.path.exists(REPLIED_IDS_FILE):
        return set()
    with open(REPLIED_IDS_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_replied_id(email_id):
    """Add a new email ID to our tracking file."""
    with open(REPLIED_IDS_FILE, "a") as f:
        f.write(email_id + "\n")

# ── Step 6: Claude client and reply function ───────────────────────────────────

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def get_claude_reply(sender, subject, body):
    """Send email content to Claude and return its response."""
    user_message = f"""
Please analyze this email and write a reply.

FROM: {sender}
SUBJECT: {subject}
BODY:
{body}
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text

def parse_claude_response(claude_text):
    """Split Claude's response into category and reply text."""
    category = "OTHER"
    reply    = ""
    lines    = claude_text.strip().split("\n")

    for i, line in enumerate(lines):
        if line.startswith("CATEGORY:"):
            category = line.replace("CATEGORY:", "").strip()
        if line.startswith("REPLY:"):
            reply = "\n".join(lines[i+1:]).strip()
            break

    return category, reply

# ── Step 7: Send email function ────────────────────────────────────────────────

def send_reply(to_address, original_subject, reply_body):
    """Send an email reply via Gmail SMTP."""
    msg = email.mime.multipart.MIMEMultipart()
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = to_address
    msg["Subject"] = f"Re: {original_subject}"
    msg.attach(email.mime.text.MIMEText(reply_body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)

# ── Step 8: Process inbox function ────────────────────────────────────────────

def check_and_reply():
    """
    One full cycle of the agent:
    1. Connect to Gmail
    2. Find unread emails
    3. For each one — analyze with Claude and send a reply
    4. Disconnect
    """

    # Load replied IDs fresh each cycle
    # (in case another process added IDs while we were sleeping)
    replied_ids = load_replied_ids()

    try:
        # Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("INBOX", readonly=False)

        # Search for unread emails
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()

        if not email_ids:
            logging.info("No new emails found")
            mail.logout()
            return

        logging.info(f"Found {len(email_ids)} unread email(s)")

        # Process each email
        for email_id in reversed(email_ids[-5:]):
            email_id_str = email_id.decode("utf-8")

            # Skip if already replied
            if email_id_str in replied_ids:
                logging.info(f"Skipping email {email_id_str} — already replied")
                continue

            # Fetch the email
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            sender  = msg.get("From", "")
            subject = msg.get("Subject", "No subject")

            # Extract just the email address
            if "<" in sender:
                sender_email = sender.split("<")[1].replace(">", "").strip()
            else:
                sender_email = sender.strip()

            # Safety check: never reply to ourselves
            if sender_email.lower() == GMAIL_ADDRESS.lower():
                logging.info(f"Skipping own email — {sender_email}")
                save_replied_id(email_id_str)
                continue

            # Get body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

            body = body[:2000]

            logging.info(f"Processing email from {sender_email} — Subject: {subject}")

            # Get Claude's reply
            try:
                claude_text      = get_claude_reply(sender_email, subject, body)
                category, reply  = parse_claude_response(claude_text)
                logging.info(f"Claude classified as: {category}")

                # Skip spam
                if category == "SPAM" or reply == "No reply needed.":
                    logging.info(f"Skipping spam email from {sender_email}")
                    save_replied_id(email_id_str)
                    continue

                # Send the reply
                send_reply(sender_email, subject, reply)
                logging.info(f"Reply sent to {sender_email}")

                # Mark as replied
                save_replied_id(email_id_str)

                # Wait between emails
                time.sleep(2)

            # If Claude or sending fails, log the error but don't crash
            except Exception as e:
                logging.error(f"Failed to process email from {sender_email}: {e}")
                continue

        mail.logout()

    # If Gmail connection fails, log the error but don't crash
    except Exception as e:
        logging.error(f"Gmail connection error: {e}")

# ── Step 9: The main loop ──────────────────────────────────────────────────────

def main():
    """
    Run the agent forever.
    Every CHECK_INTERVAL seconds, check for new emails and reply.
    Press Ctrl+C to stop.
    """
    logging.info("=" * 50)
    logging.info("Email Agent Started")
    logging.info(f"Checking inbox every {CHECK_INTERVAL} seconds")
    logging.info("Press Ctrl+C to stop")
    logging.info("=" * 50)

    # This loop runs forever until you press Ctrl+C
    while True:
        try:
            logging.info("Checking inbox...")
            check_and_reply()
            logging.info(f"Sleeping for {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)

        # Ctrl+C pressed — exit cleanly
        except KeyboardInterrupt:
            logging.info("Agent stopped by user. Goodbye!")
            break

        # Any other unexpected error — log it and keep running
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            logging.info("Recovering... will try again in 60 seconds")
            time.sleep(CHECK_INTERVAL)

# This line means: only run main() if we run THIS file directly
# (not if another file imports it)
if __name__ == "__main__":
    main()