# claude_reply.py
# Goal: Read unread emails and use Claude to generate a reply for each one
# This combines Phase 1 (Claude API) and Phase 2 (Gmail IMAP)

# ── Step 1: Import libraries ───────────────────────────────────────────────────

import imaplib
import email
import os
from dotenv import load_dotenv
import anthropic

# ── Step 2: Load credentials ───────────────────────────────────────────────────

load_dotenv()

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")

# Safety check
if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, ANTHROPIC_API_KEY]):
    print("ERROR: Missing values in .env file")
    print("Make sure GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and ANTHROPIC_API_KEY are all set")
    exit()

# ── Step 3: Define the system prompt ──────────────────────────────────────────

# This is the "job description" we give Claude
# It tells Claude:
#   - What business this is
#   - How to classify emails
#   - How to write replies
# You can change the business description to anything you want later

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

# ── Step 4: Create the Claude client ──────────────────────────────────────────

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Step 5: Define a function to get Claude's reply ───────────────────────────

# A "function" is a reusable block of code
# We give it an email, it gives us back Claude's analysis and reply
# We'll call this function once for each unread email we find

def get_claude_reply(sender, subject, body):
    """
    Sends an email to Claude and returns its classification and suggested reply.
    sender  = who sent the email
    subject = email subject line
    body    = email body text
    """

    # Build the message we send to Claude
    # We format it clearly so Claude understands what each part is
    user_message = f"""
Please analyze this email and write a reply.

FROM: {sender}
SUBJECT: {subject}
BODY:
{body}
"""

    # Call the Claude API — same pattern as Phase 1
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,   # <-- this is new! The system prompt goes here
        messages=[
            {
                "role": "user",
                "content": user_message
            }
        ]
    )

    # Extract the text from Claude's response
    return response.content[0].text


# ── Step 6: Connect to Gmail and read unread emails ───────────────────────────

print("Connecting to Gmail...")
mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
mail.select("INBOX", readonly=True)

print("Searching for unread emails...")
status, messages = mail.search(None, "UNSEEN")
email_ids = messages[0].split()

print(f"Found {len(email_ids)} unread email(s)")
print("=" * 60)

if not email_ids:
    print("No unread emails found.")
    print("Tip: Send yourself a test email and run this again!")
    mail.logout()
    exit()

# ── Step 7: Process each email with Claude ────────────────────────────────────

# Take the 5 most recent unread emails, newest first
recent_ids = list(reversed(email_ids[-5:]))

for i, email_id in enumerate(recent_ids, start=1):

    # Fetch the raw email
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    # Get sender and subject
    sender  = msg.get("From", "Unknown sender")
    subject = msg.get("Subject", "No subject")

    # Get body text
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                break
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

    # Trim body to 2000 characters max
    # This prevents very long emails from using too many API tokens
    body = body[:2000]

    # Print the email details
    print(f"EMAIL {i}:")
    print(f"FROM:    {sender}")
    print(f"SUBJECT: {subject}")
    print(f"BODY:    {body[:200]}...")  # Only show first 200 chars in terminal
    print()

    # Send to Claude and get reply
    print("Sending to Claude for analysis...")
    claude_response = get_claude_reply(sender, subject, body)

    # Print Claude's response
    print("Claude's analysis:")
    print(claude_response)
    print("=" * 60)

# ── Step 8: Disconnect ─────────────────────────────────────────────────────────

mail.logout()
print("Done! Disconnected from Gmail.")