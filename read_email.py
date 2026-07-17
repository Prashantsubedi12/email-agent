# read_email.py
# Goal: Connect to Gmail and read the 5 most recent unread emails
# Uses imaplib — built into Python, no installation needed

# ── Step 1: Import libraries ───────────────────────────────────────────────────

import imaplib   # handles the IMAP connection to Gmail
import email     # helps us decode/parse raw email data into readable text
import os        # lets us read environment variables
from dotenv import load_dotenv  # reads our .env file

# ── Step 2: Load credentials from .env ────────────────────────────────────────

load_dotenv()

GMAIL_ADDRESS     = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Safety check
if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
    print("ERROR: GMAIL_ADDRESS or GMAIL_APP_PASSWORD not found in .env file")
    exit()

# ── Step 3: Connect to Gmail ───────────────────────────────────────────────────

print(f"Connecting to Gmail as {GMAIL_ADDRESS}...")

# imaplib.IMAP4_SSL means we connect securely (encrypted)
# "imap.gmail.com" is Gmail's IMAP server address — always this exact string
mail = imaplib.IMAP4_SSL("imap.gmail.com")

# Log in using email address and App Password (NOT your real Gmail password)
mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

print("Connected successfully!")

# ── Step 4: Select the inbox ───────────────────────────────────────────────────

# "INBOX" is the folder we want to read from
# readonly=True means we are ONLY reading — we won't change or delete anything
mail.select("INBOX", readonly=True)

# ── Step 5: Search for unread emails ──────────────────────────────────────────

# UNSEEN means "unread" in IMAP language
# search() returns a list of email ID numbers that match our filter
status, messages = mail.search(None, "UNSEEN")

# messages[0] is a bytes string like b"1 2 3 4 5"
# We split it into a list: [b"1", b"2", b"3", b"4", b"5"]
email_ids = messages[0].split()

print(f"Found {len(email_ids)} unread email(s)")
print("-" * 50)

# If no unread emails, stop here
if not email_ids:
    print("No unread emails found.")
    print("Tip: Send yourself a test email and run this again!")
    mail.logout()
    exit()

# ── Step 6: Read the 5 most recent emails ─────────────────────────────────────

# We take the LAST 5 IDs — these are the most recent ones
# If there are fewer than 5, we take all of them
recent_ids = email_ids[-5:]

# We reverse the list so newest email appears first
recent_ids = list(reversed(recent_ids))

for email_id in recent_ids:

    # Fetch the full email by its ID
    # "(RFC822)" means "give me the full raw email content"
    status, msg_data = mail.fetch(email_id, "(RFC822)")

    # msg_data[0][1] is the raw bytes of the email
    raw_email = msg_data[0][1]

    # Convert raw bytes into a proper email object we can read
    msg = email.message_from_bytes(raw_email)

    # ── Get sender and subject ─────────────────────────────────────────────────

    sender  = msg.get("From", "Unknown sender")
    subject = msg.get("Subject", "No subject")

    # ── Get the body text ─────────────────────────────────────────────────────

    body = ""

    # Emails can have multiple "parts" (plain text, HTML, attachments)
    # We walk through each part looking for plain text
    if msg.is_multipart():
        for part in msg.walk():
            # We only want plain text — not HTML, not attachments
            if part.get_content_type() == "text/plain":
                # Decode the bytes into a string
                # errors="ignore" means skip any characters we can't read
                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                break  # Stop after finding the first plain text part
    else:
        # Email has only one part — just read it directly
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

    # ── Print the email ────────────────────────────────────────────────────────

    print(f"FROM:    {sender}")
    print(f"SUBJECT: {subject}")
    print(f"BODY:")
    # Only print first 500 characters of body so terminal doesn't overflow
    print(body[:500])
    print("-" * 50)

# ── Step 7: Disconnect cleanly ─────────────────────────────────────────────────

mail.logout()
print("Disconnected from Gmail.")