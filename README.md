# 📧 AI Email Auto-Reply Agent

A Python-based AI agent that monitors a Gmail inbox and automatically replies to incoming emails using the Anthropic Claude API.

Built as a portfolio project to demonstrate backend development, API integration, and AI agent design.

---

## 🎯 What It Does

1. **Monitors** a Gmail inbox every 60 seconds using IMAP
2. **Reads** each new unread email (sender, subject, body)
3. **Analyzes** the email using Claude AI to classify it and write a reply
4. **Sends** the reply automatically via Gmail SMTP
5. **Logs** all activity to a file for review

---

## 🤖 How the AI Works

Each email is sent to Claude (Anthropic's AI) with a system prompt that defines:
- The persona (freelance photographer based in Osaka, Japan)
- Classification categories: INQUIRY, COMPLAINT, SPAM, PERSONAL, OTHER
- Reply tone and format rules

Claude returns a category and a professionally written reply. The system sends the reply — or skips it if the email is spam.

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.10+ | Core language |
| Anthropic Claude API (Haiku) | Email classification and reply generation |
| `imaplib` (built-in) | Reading emails from Gmail |
| `smtplib` (built-in) | Sending emails via Gmail |
| `python-dotenv` | Secure credential management |
| Gmail App Password | Secure Gmail authentication |

No frameworks. No databases. Pure Python.

---

## 📁 Project Structure

email-agent/
├── main.py            # Main agent loop — runs continuously
├── test_claude.py     # Phase 1: Tests Claude API connection
├── read_email.py      # Phase 2: Reads emails from Gmail
├── claude_reply.py    # Phase 3: Connects Claude to emails
├── send_email.py      # Phase 4: Sends Claude's replies
├── replied_ids.txt    # Tracks which emails have been replied to
├── agent.log          # Persistent log of all agent activity
├── .env               # Secret credentials (not on GitHub)
├── .gitignore         # Prevents .env from being committed
└── README.md          # This file

---

## ⚙️ Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/email-agent.git
cd email-agent
```

### 2. Create a virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install anthropic python-dotenv
```

### 4. Configure credentials

Create a `.env` file in the root folder:

ANTHROPIC_API_KEY=your_claude_api_key_here
GMAIL_ADDRESS=your_gmail@gmail.com
GMAIL_APP_PASSWORD=your_16_character_app_password


To get these:
- **Claude API key** → [console.anthropic.com](https://console.anthropic.com)
- **Gmail App Password** → Google Account → Security → 2-Step Verification → App Passwords

### 5. Run the agent
```bash
python main.py
```

Press `Ctrl+C` to stop.

---

## 🔒 Safety Features

- **Never replies to itself** — skips emails sent from the same address
- **Never replies twice** — tracks replied email IDs in `replied_ids.txt`
- **Never replies to spam** — Claude classifies and skips spam automatically
- **Credentials protected** — `.env` file is excluded from Git via `.gitignore`
- **Error handling** — agent logs errors and keeps running if something fails

---

## 📊 Sample Log Output

2026-07-17 15:15:13 [INFO] Email Agent Started
2026-07-17 15:15:13 [INFO] Checking inbox every 60 seconds
2026-07-17 15:16:15 [INFO] No new emails found
2026-07-17 15:17:17 [INFO] Found 2 unread email(s)
2026-07-17 15:17:19 [INFO] Processing email from client@example.com — Subject: Photography Inquiry
2026-07-17 15:17:21 [INFO] Claude classified as: INQUIRY
2026-07-17 15:17:23 [INFO] Reply sent to client@example.com

---

## 💡 What I Learned

- How to call an external AI API from Python
- How IMAP and SMTP protocols work for reading and sending email
- How to write effective system prompts for AI agents
- How to manage secrets safely with environment variables
- How to build a continuously running backend agent with error handling
- How to structure a Python project with multiple files

---

## 🚀 Possible Future Improvements

- Web dashboard to view logs and replies in a browser
- Support for multiple email accounts
- Calendar integration to check availability before replying
- Confidence threshold — only auto-send if Claude is highly confident
- Database storage instead of text file for replied IDs

---

## 👤 Author

**Prashant Subedi**  
IT Student — 産業技術短期大学, Hyogo, Japan  
Freelance Photographer  
GitHub: [@Prash](https://github.com/Prash-2604)

---

## ⚠️ Disclaimer

This project is built for learning and portfolio purposes.
Always test auto-reply systems carefully before using them on a real inbox.