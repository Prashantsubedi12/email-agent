# main.py
# Upgraded version — uses PostgreSQL instead of replied_ids.txt
# Everything else is identical to the version we built in Phase 5

# ── Step 1: Import libraries ───────────────────────────────────────────────────

import imaplib
import smtplib
import email
import email.mime.text
import email.mime.multipart
import os
import time
import logging
from dotenv import load_dotenv
import anthropic
import psycopg2  # NEW: PostgreSQL database library

# ── Step 2: Set up logging ─────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("agent.log"),
        logging.StreamHandler()
    ]
)

# ── Step 3: Load credentials ───────────────────────────────────────────────────

load_dotenv()

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
DATABASE_URL       = os.getenv("DATABASE_URL")  # NEW: database connection string

if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, ANTHROPIC_API_KEY]):
    logging.error("Missing values in .env file")
    exit()

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

# ── Step 5: Database functions ─────────────────────────────────────────────────

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(DATABASE_URL)

def setup_database():
    """
    Create the tables we need if they don't exist yet.
    This runs once every time the agent starts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: tracks which emails we already replied to
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS replied_emails (
            id SERIAL PRIMARY KEY,
            email_id VARCHAR(255) UNIQUE NOT NULL,
            replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 2: stores full email history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_history (
            id SERIAL PRIMARY KEY,
            sender VARCHAR(500),
            subject VARCHAR(500),
            body TEXT,
            category VARCHAR(50),
            reply_sent TEXT,
            status VARCHAR(50) DEFAULT 'sent',
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    logging.info("Database ready")

def has_replied(email_id):
    """Check if we already replied to this email ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM replied_emails WHERE email_id = %s",
        (email_id,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result is not None

def mark_as_replied(email_id):
    """Mark an email ID as replied in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO replied_emails (email_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (email_id,)
    )
    conn.commit()
    cursor.close()
    conn.close()

def save_email_history(sender, subject, body, category, reply, status):
    """Save a processed email to the history table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO email_history 
        (sender, subject, body, category, reply_sent, status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (sender, subject, body[:2000], category, reply, status))
    conn.commit()
    cursor.close()
    conn.close()

# ── Step 6: Claude functions ───────────────────────────────────────────────────

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

# ── Step 8: Main check function ────────────────────────────────────────────────

def check_and_reply():
    """One full cycle — connect, read, analyze, reply, disconnect."""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("INBOX", readonly=False)

        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()

        if not email_ids:
            logging.info("No new emails found")
            mail.logout()
            return

        logging.info(f"Found {len(email_ids)} unread email(s)")

        for email_id in reversed(email_ids[-5:]):
            email_id_str = email_id.decode("utf-8")

            # Check database instead of text file
            if has_replied(email_id_str):
                logging.info(f"Skipping {email_id_str} — already replied")
                continue

            status, msg_data = mail.fetch(email_id, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            sender  = msg.get("From", "")
            subject = msg.get("Subject", "No subject")

            if "<" in sender:
                sender_email = sender.split("<")[1].replace(">", "").strip()
            else:
                sender_email = sender.strip()

            if sender_email.lower() == GMAIL_ADDRESS.lower():
                logging.info(f"Skipping own email")
                mark_as_replied(email_id_str)
                continue

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

            body = body[:2000]

            logging.info(f"Processing: {sender_email} — {subject}")

            try:
                claude_text     = get_claude_reply(sender_email, subject, body)
                category, reply = parse_claude_response(claude_text)
                logging.info(f"Category: {category}")

                if category == "SPAM" or reply == "No reply needed.":
                    logging.info("Skipping spam")
                    save_email_history(sender_email, subject, body, category, "", "skipped_spam")
                    mark_as_replied(email_id_str)
                    continue

                send_reply(sender_email, subject, reply)
                logging.info(f"Reply sent to {sender_email}")

                # Save to database history
                save_email_history(sender_email, subject, body, category, reply, "sent")
                mark_as_replied(email_id_str)

                time.sleep(2)

            except Exception as e:
                logging.error(f"Failed to process email: {e}")
                continue

        mail.logout()

    except Exception as e:
        logging.error(f"Gmail connection error: {e}")

# ── Step 9: Main loop ──────────────────────────────────────────────────────────

def main():
    logging.info("=" * 50)
    logging.info("Email Agent Started")
    logging.info(f"Checking every {CHECK_INTERVAL} seconds")
    logging.info("Press Ctrl+C to stop")
    logging.info("=" * 50)

    # Set up database tables on startup
    if DATABASE_URL:
        setup_database()
    else:
        logging.warning("No DATABASE_URL found — running without database")

    while True:
        try:
            logging.info("Checking inbox...")
            check_and_reply()
            logging.info(f"Sleeping {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logging.info("Agent stopped. Goodbye!")
            break

        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()