# dashboard.py
# A simple web dashboard to view all processed emails
# Run this separately from main.py
# Visit http://localhost:8080 in your browser to see it

import sqlite3
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

DATABASE_FILE = "email_agent.db"

def get_email_history():
    """Read all processed emails from the database."""
    if not os.path.exists(DATABASE_FILE):
        return []
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sender, subject, category, reply_sent, status, processed_at
        FROM email_history
        ORDER BY processed_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_stats():
    """Get summary numbers for the top of the dashboard."""
    if not os.path.exists(DATABASE_FILE):
        return {"total": 0, "sent": 0, "spam": 0, "errors": 0}
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM email_history")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM email_history WHERE status = 'sent'")
    sent = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM email_history WHERE status = 'skipped_spam'")
    spam = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM email_history WHERE status = 'error'")
    errors = cursor.fetchone()[0]
    conn.close()
    return {"total": total, "sent": sent, "spam": spam, "errors": errors}

def build_html():
    """Build the full HTML page as a string."""
    rows  = get_email_history()
    stats = get_stats()

    # Build table rows
    table_rows = ""
    if not rows:
        table_rows = """
            <tr>
                <td colspan="6" style="text-align:center; color:#888; padding:40px;">
                    No emails processed yet. Run main.py and send a test email!
                </td>
            </tr>
        """
    else:
        for row in rows:
            # Color code the category badge
            category_colors = {
                "INQUIRY":   "#3b82f6",
                "COMPLAINT": "#ef4444",
                "SPAM":      "#6b7280",
                "PERSONAL":  "#8b5cf6",
                "OTHER":     "#f59e0b",
            }
            category = row["category"] or "OTHER"
            color    = category_colors.get(category, "#6b7280")

            # Color code the status badge
            status = row["status"] or "unknown"
            status_color = "#22c55e" if status == "sent" else "#6b7280"

            # Truncate long text for display
            sender  = (row["sender"]  or "")[:40]
            subject = (row["subject"] or "")[:50]
            reply   = (row["reply_sent"] or "No reply")[:100]
            time    = (row["processed_at"] or "")[:16]

            table_rows += f"""
                <tr>
                    <td>{time}</td>
                    <td>{sender}</td>
                    <td>{subject}</td>
                    <td>
                        <span style="
                            background:{color};
                            color:white;
                            padding:3px 10px;
                            border-radius:12px;
                            font-size:12px;
                            font-weight:bold;
                        ">{category}</span>
                    </td>
                    <td style="font-size:13px; color:#ccc;">{reply}...</td>
                    <td>
                        <span style="
                            background:{status_color};
                            color:white;
                            padding:3px 10px;
                            border-radius:12px;
                            font-size:12px;
                        ">{status}</span>
                    </td>
                </tr>
            """

    # Build the full HTML page
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Agent Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
            padding: 30px;
        }}

        .header {{
            margin-bottom: 30px;
        }}

        .header h1 {{
            font-size: 28px;
            font-weight: 700;
            color: #f8fafc;
        }}

        .header h1 span {{
            color: #3b82f6;
        }}

        .header p {{
            color: #94a3b8;
            margin-top: 5px;
            font-size: 14px;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
        }}

        .stat-card .number {{
            font-size: 36px;
            font-weight: 700;
            color: #f8fafc;
        }}

        .stat-card .label {{
            font-size: 13px;
            color: #94a3b8;
            margin-top: 4px;
        }}

        .stat-card.blue   .number {{ color: #3b82f6; }}
        .stat-card.green  .number {{ color: #22c55e; }}
        .stat-card.gray   .number {{ color: #6b7280; }}
        .stat-card.red    .number {{ color: #ef4444; }}

        .table-container {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            overflow: hidden;
        }}

        .table-header {{
            padding: 16px 20px;
            border-bottom: 1px solid #334155;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .table-header h2 {{
            font-size: 16px;
            font-weight: 600;
        }}

        .refresh-btn {{
            background: #3b82f6;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            cursor: pointer;
            text-decoration: none;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            text-align: left;
            padding: 12px 16px;
            font-size: 12px;
            font-weight: 600;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #334155;
            background: #162032;
        }}

        td {{
            padding: 14px 16px;
            font-size: 14px;
            border-bottom: 1px solid #1e293b;
            vertical-align: top;
        }}

        tr:hover td {{
            background: #162032;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        .footer {{
            margin-top: 20px;
            text-align: center;
            font-size: 12px;
            color: #475569;
        }}

        /* Auto-refresh every 30 seconds */
        /* Page reloads automatically so you always see latest data */
    </style>

    <!-- Auto refresh every 30 seconds -->
    <meta http-equiv="refresh" content="30">
</head>
<body>

    <div class="header">
        <h1>📧 Email Agent <span>Dashboard</span></h1>
        <p>AI-powered auto-reply system — powered by Claude API • Auto-refreshes every 30 seconds</p>
    </div>

    <div class="stats">
        <div class="stat-card blue">
            <div class="number">{stats["total"]}</div>
            <div class="label">Total Processed</div>
        </div>
        <div class="stat-card green">
            <div class="number">{stats["sent"]}</div>
            <div class="label">Replies Sent</div>
        </div>
        <div class="stat-card gray">
            <div class="number">{stats["spam"]}</div>
            <div class="label">Spam Skipped</div>
        </div>
        <div class="stat-card red">
            <div class="number">{stats["errors"]}</div>
            <div class="label">Errors</div>
        </div>
    </div>

    <div class="table-container">
        <div class="table-header">
            <h2>Email History</h2>
            <a href="/" class="refresh-btn">🔄 Refresh</a>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Sender</th>
                    <th>Subject</th>
                    <th>Category</th>
                    <th>Reply Preview</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>

    <div class="footer">
        Email Agent by Prashant Subedi • Osaka, Japan •
        Built with Python + Claude API
    </div>

</body>
</html>
"""
    return html

class DashboardHandler(BaseHTTPRequestHandler):
    """Handles incoming browser requests and serves the dashboard."""

    def do_GET(self):
        """Called every time someone visits the page in their browser."""
        html = build_html()

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress default server log spam in terminal."""
        pass

def main():
    port   = 8080
    server = HTTPServer(("localhost", port), DashboardHandler)
    print(f"Dashboard running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")

if __name__ == "__main__":
    main()