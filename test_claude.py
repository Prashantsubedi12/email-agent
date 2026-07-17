# test_claude.py
# Goal: Send a message to Claude and print the reply
# This tests that our API key works and our setup is correct

# ── Step 1: Import the libraries we need ──────────────────────────────────────

import os                        # os lets us read environment variables
from dotenv import load_dotenv   # load_dotenv reads our .env file
import anthropic                 # anthropic is the official Claude library

# ── Step 2: Load the API key from .env ────────────────────────────────────────

load_dotenv()  # This reads .env and loads everything inside it into memory

api_key = os.getenv("ANTHROPIC_API_KEY")  # This fetches the key by name

# Safety check — if the key is missing, stop immediately with a clear message
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY not found in .env file")
    print("Make sure your .env file exists and has your key in it")
    exit()

# ── Step 3: Create the Claude client ──────────────────────────────────────────

# Think of 'client' like opening a phone call with Claude
# We pass our API key so Claude knows who we are
client = anthropic.Anthropic(api_key=api_key)

# ── Step 4: Send a message and get a reply ────────────────────────────────────

print("Sending message to Claude...")
print("-" * 40)  # Just prints a line of dashes for readability

# This is the actual API call
# model     = which version of Claude to use
# max_tokens = maximum length of Claude's reply (1024 tokens ≈ 750 words)
# messages  = the conversation — a list of messages with "role" and "content"
#   role "user"      = the message WE are sending
#   role "assistant" = what Claude replies (Claude fills this in automatically)

message = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Hello Claude! Please introduce yourself in 2-3 sentences. Then tell me what day it is today."
        }
    ]
)

# ── Step 5: Print the reply ───────────────────────────────────────────────────

# message.content is a list — we want the first item's text
reply = message.content[0].text

print("Claude says:")
print(reply)
print("-" * 40)
print("SUCCESS: Claude API is working correctly!")

