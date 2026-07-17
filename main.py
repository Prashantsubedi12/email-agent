# main.py
# Final version — real portfolio context + SMS notifications + SQLite database

# ── Imports ────────────────────────────────────────────────────────────────────

import imaplib
import smtplib
import email
import email.mime.text
import email.mime.multipart
import os
import time
import logging
import sqlite3
from dotenv import load_dotenv
import anthropic


# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("agent.log"),
        logging.StreamHandler()
    ]
)

# ── Credentials ────────────────────────────────────────────────────────────────

load_dotenv()

GMAIL_ADDRESS        = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD   = os.getenv("GMAIL_APP_PASSWORD")
ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY")
TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER   = os.getenv("TWILIO_FROM_NUMBER")
MY_PHONE_NUMBER      = os.getenv("MY_PHONE_NUMBER")

if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, ANTHROPIC_API_KEY]):
    logging.error("Missing values in .env file")
    exit()

CHECK_INTERVAL = 60
DATABASE_FILE  = "email_agent.db"

# ── System Prompt — Real Portfolio Context ─────────────────────────────────────

SYSTEM_PROMPT = """
You are the email assistant for Prashant Subedi, a bilingual freelance photographer 
and web developer based in Osaka, Japan.

== ABOUT PRASHANT ==
- Full name: Prashant Subedi
- Brand name: Prashant Captures
- Age: 20 years old
- Based in: Osaka, Japan
- Languages: English, Japanese, Nepali, Hindi (fully fluent in all four)
- Camera: Sony a6400 with Tamron 17-70mm f/2.8
- Instagram/TikTok: @prashantsub12
- Portfolio: https://photography-site-bay-three.vercel.app
- Email: prashant.captures.photo@gmail.com

== PHOTOGRAPHY SERVICES & PRICING ==
1. Portrait Session — ¥8,000〜¥15,000
   - 1-on-1 outdoor portraits at Osaka locations
   - 1-2 hours shooting
   - 20+ edited photos delivered within 5 days

2. Tourist Photo Session — ¥12,000〜¥20,000 (MOST POPULAR)
   - Walk Osaka together, shoot at iconic spots
   - 2-3 hours walking and shooting
   - 30+ edited photos
   - Perfect for foreign visitors — bilingual (EN/JP)

3. Couple Session — ¥12,000〜¥25,000
   - Outdoor romantic sessions
   - Osaka Castle, riverside walks, neon-lit streets at night
   - 1-2 hours, 25+ edited photos

4. Event Coverage — ¥10,000〜¥30,000 per event
   - Concerts, live events, sports, festivals, birthday parties
   - Full event coverage, 50+ edited photos, quick turnaround

Additional notes on pricing:
- All prices are starting points — final price depends on duration and location
- Bilingual sessions (English + Japanese) at no extra charge
- Photos delivered via Google Drive within 5 days

== WEB DEVELOPMENT SERVICES ==
Prashant is also a web developer. He builds:
- Small business websites (restaurants, shops, local SMEs)
- Bilingual websites (English + Japanese)
- Portfolio sites for photographers and creatives
- AI automation tools (like this email agent)
Tech stack: HTML, CSS, JavaScript, SvelteKit, Python, FastAPI
Portfolio: https://photography-site-bay-three.vercel.app/it-portfolio/

== PRASHANT'S PERSONALITY & TONE ==
- Warm, friendly, and genuine — never stiff or corporate
- Bilingual — reply in the same language the client used
- If email is in Japanese → reply in Japanese
- If email is in English → reply in English
- If email mixes both → reply in English with Japanese phrases where natural
- Always honest about availability and pricing
- Mentions specific Osaka locations when relevant
- Signs off as "Prashant" not "Prashant Captures"

== YOUR JOB ==
When you receive an email, do TWO things:

1. CLASSIFY into exactly one category:
   - INQUIRY: Questions about photography services, pricing, booking, availability, web dev services
   - BOOKING: Someone ready to book a specific session with date/time
   - COMPLAINT: Dissatisfaction or problem with a past session
   - SPAM: Promotional emails, scams, irrelevant messages
   - PERSONAL: Messages from friends or family
   - OTHER: Anything else

2. WRITE A REPLY that:
   - Sounds like Prashant himself wrote it — warm and genuine
   - Answers the specific question asked
   - Mentions relevant pricing if they asked about services
   - Suggests a specific next step (check portfolio, book via contact form, etc.)
   - Is 3-5 sentences maximum
   - Is in the same language as the original email

Format your response EXACTLY like this:
CATEGORY: [category]
REPLY:
[reply text here]

For SPAM only:
CATEGORY: SPAM
REPLY:
No reply needed.
"""

# ── Database ───────────────────────────────────────────────────────────────────

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS replied_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT UNIQUE NOT NULL,
            replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            subject TEXT,
            body TEXT,
            category TEXT,
            reply_sent TEXT,
            status TEXT DEFAULT 'sent',
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logging.info("Database ready — email_agent.db")

def has_replied(email_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM replied_emails WHERE email_id = ?", (email_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_as_replied(email_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO replied_emails (email_id) VALUES (?)", (email_id,))
    conn.commit()
    conn.close()

def save_email_history(sender, subject, body, category, reply, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO email_history
        (sender, subject, body, category, reply_sent, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (sender, subject, body[:2000], category, reply, status))
    conn.commit()
    conn.close()

# ── SMS Notification ───────────────────────────────────────────────────────────

def send_sms_notification(sender, subject, category):
    """
    Send an email notification to Prashant's personal Gmail
    when an important inquiry arrives.
    Gmail app on phone will notify instantly.
    """
    try:
        msg = email.mime.multipart.MIMEMultipart()
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = "prashantsubedi718@gmail.com"
        msg["Subject"] = f"📸 New {category} from {sender}"

        body = f"""
New {category} received!

From: {sender}
Subject: {subject}

Auto-reply has been sent.
Check prashant.captures.photo@gmail.com for details.
        """

        msg.attach(email.mime.text.MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        logging.info(f"Email notification sent to prashantsubedi718@gmail.com")

    except Exception as e:
        logging.error(f"Notification failed: {e}")

# ── Claude ─────────────────────────────────────────────────────────────────────

claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def get_claude_reply(sender, subject, body):
    user_message = f"""
Please analyze this email and write a reply.

FROM: {sender}
SUBJECT: {subject}
BODY:
{body}
"""
    response = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text

def parse_claude_response(claude_text):
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

# ── Send Email ─────────────────────────────────────────────────────────────────

def send_reply(to_address, original_subject, reply_body):
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

# ── Main Check ─────────────────────────────────────────────────────────────────

def check_and_reply():
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
                logging.info("Skipping own email")
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

                save_email_history(sender_email, subject, body, category, reply, "sent")
                mark_as_replied(email_id_str)

                # Send SMS only for inquiries and bookings
                if category in ["INQUIRY", "BOOKING"]:
                    send_sms_notification(sender_email, subject, category)

                time.sleep(2)

            except Exception as e:
                logging.error(f"Failed to process email: {e}")
                continue

        mail.logout()

    except Exception as e:
        logging.error(f"Gmail connection error: {e}")

# ── Main Loop ──────────────────────────────────────────────────────────────────

def main():
    logging.info("=" * 50)
    logging.info("Prashant Captures — Email Agent Started")
    logging.info(f"Monitoring: {GMAIL_ADDRESS}")
    logging.info(f"Checking every {CHECK_INTERVAL} seconds")
    logging.info("Press Ctrl+C to stop")
    logging.info("=" * 50)

    setup_database()

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