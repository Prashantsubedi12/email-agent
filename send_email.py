# send_email.py
# Goal: Read unread emails, get Claude's reply, and actually send it
# Uses smtplib to send emails — built into Python, no installation needed

# ── Step 1: Import libraries ───────────────────────────────────────────────────

import imaplib
import smtplib        # handles sending emails via SMTP
import email
import email.mime.text
import email.mime.multipart
import os
import time           # we use this to avoid sending emails too fast
from dotenv import load_dotenv
import anthropic

# ── Step 2: Load credentials ───────────────────────────────────────────────────

load_dotenv()

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")

if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, ANTHROPIC_API_KEY]):
    print("ERROR: Missing values in .env file")
    exit()

# ── Step 3: System prompt (same as Phase 3) ───────────────────────────────────

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

# ── Step 4: File that tracks which emails we already replied to ────────────────

# This is the path to our tracking file
# Each email has a unique ID — we save those IDs here so we never reply twice
REPLIED_IDS_FILE = "replied_ids.txt"

def load_replied_ids():
    """Read the list of email IDs we have already replied to."""
    # If the file doesn't exist yet, return an empty set
    if not os.path.exists(REPLIED_IDS_FILE):
        return set()
    # Open the file and read each line as an ID
    with open(REPLIED_IDS_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_replied_id(email_id):
    """Add a new email ID to our tracking file."""
    # "a" means append — we add to the end without deleting existing content
    with open(REPLIED_IDS_FILE, "a") as f:
        f.write(email_id + "\n")

# ── Step 5: Function to get Claude's reply ────────────────────────────────────

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def get_claude_reply(sender, subject, body):
    """Send email content to Claude and return its classification and reply."""
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

# ── Step 6: Function to parse Claude's response ───────────────────────────────

def parse_claude_response(claude_text):
    """
    Claude returns text like:
        CATEGORY: INQUIRY
        REPLY:
        Thank you for reaching out...

    This function splits that into two separate values we can use.
    """
    category = "OTHER"
    reply    = ""

    lines = claude_text.strip().split("\n")

    for i, line in enumerate(lines):
        # Find the category line
        if line.startswith("CATEGORY:"):
            category = line.replace("CATEGORY:", "").strip()

        # Find the REPLY: marker, then grab everything after it
        if line.startswith("REPLY:"):
            # Join all lines after "REPLY:" into the reply text
            reply = "\n".join(lines[i+1:]).strip()
            break

    return category, reply

# ── Step 7: Function to send an email ─────────────────────────────────────────

def send_reply(to_address, original_subject, reply_body):
    """
    Sends an email reply using Gmail SMTP.
    to_address       = who we are replying to
    original_subject = the subject of the email we received
    reply_body       = the text Claude wrote
    """

    # Build the email message
    # MIMEMultipart lets us create a proper email with headers
    msg = email.mime.multipart.MIMEMultipart()
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = to_address
    # Add "Re: " to the subject so it looks like a real reply
    msg["Subject"] = f"Re: {original_subject}"

    # Attach the reply body as plain text
    msg.attach(email.mime.text.MIMEText(reply_body, "plain"))

    # Connect to Gmail's SMTP server and send
    # Port 587 is the standard port for sending email securely
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()       # introduce ourselves to the server
        server.starttls()   # upgrade connection to encrypted (TLS)
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)

    print(f"Reply sent to {to_address}")

# ── Step 8: Main logic — read, analyze, reply ─────────────────────────────────

print("=" * 60)
print("Email Agent Starting...")
print("=" * 60)

# Load the list of emails we already replied to
replied_ids = load_replied_ids()

# Connect to Gmail
print("Connecting to Gmail...")
mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

# We use readonly=False here because later we may want to mark emails as read
mail.select("INBOX", readonly=False)

# Search for unread emails
status, messages = mail.search(None, "UNSEEN")
email_ids = messages[0].split()

print(f"Found {len(email_ids)} unread email(s)")
print("-" * 60)

if not email_ids:
    print("No unread emails. Nothing to do.")
    mail.logout()
    exit()

# Process each unread email
for email_id in reversed(email_ids[-5:]):

    # Convert email_id from bytes to string for storage
    email_id_str = email_id.decode("utf-8")

    # ── Safety check 1: Have we already replied to this email? ────────────────
    if email_id_str in replied_ids:
        print(f"Skipping email {email_id_str} — already replied")
        continue

    # Fetch the email
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    sender  = msg.get("From", "")
    subject = msg.get("Subject", "No subject")

    # Extract just the email address from sender
    # sender might look like: "John Smith <john@example.com>"
    # We want just: "john@example.com"
    if "<" in sender:
        sender_email = sender.split("<")[1].replace(">", "").strip()
    else:
        sender_email = sender.strip()

    # ── Safety check 2: Never reply to our own emails ─────────────────────────
    if sender_email.lower() == GMAIL_ADDRESS.lower():
        print(f"Skipping email from myself ({sender_email})")
        save_replied_id(email_id_str)  # mark it so we don't check it again
        continue

    # Get the body
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                break
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

    body = body[:2000]

    print(f"Processing email from: {sender_email}")
    print(f"Subject: {subject}")

    # Send to Claude
    print("Asking Claude for a reply...")
    claude_text = get_claude_reply(sender_email, subject, body)

    # Parse Claude's response into category and reply
    category, reply = parse_claude_response(claude_text)

    print(f"Category: {category}")
    print(f"Reply preview: {reply[:100]}...")

    # ── Safety check 3: Don't send replies to spam ────────────────────────────
    if category == "SPAM" or reply == "No reply needed.":
        print("Skipping — email classified as SPAM")
        save_replied_id(email_id_str)
        print("-" * 60)
        continue

    # Send the reply
    print("Sending reply...")
    send_reply(sender_email, subject, reply)

    # Mark this email