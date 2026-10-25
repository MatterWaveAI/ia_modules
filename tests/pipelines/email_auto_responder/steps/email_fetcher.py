"""Email Fetcher Step - Fetches emails from various sources"""

from typing import Dict, Any, Optional, List
from ia_modules.pipeline.core import PipelineStep
import json


class EmailFetcherStep(PipelineStep):
    """
    Fetches emails from various sources:
    - IMAP/Gmail
    - Microsoft Graph API (Outlook/Office 365)
    - Mock data for testing
    - JSON file import
    - Direct input
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.source_type = config.get("source_type", "mock")  # mock, imap, graph, file, direct
        self.max_emails = config.get("max_emails", 10)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch emails based on source type"""

        source_type = data.get("source_type", self.source_type)

        if source_type == "mock":
            emails = self._fetch_mock_emails(data)
        elif source_type == "imap":
            emails = await self._fetch_imap_emails(data)
        elif source_type == "graph":
            emails = await self._fetch_graph_emails(data)
        elif source_type == "file":
            emails = self._fetch_from_file(data)
        elif source_type == "direct":
            # User provided emails directly in input
            emails = data.get("emails", [])
        else:
            raise ValueError(f"Unknown source type: {source_type}")

        # Limit number of emails
        emails = emails[:self.max_emails]

        return {
            **data,
            "emails": emails,
            "email_count": len(emails),
            "source": source_type,
            "fetched": True
        }

    def _fetch_mock_emails(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate realistic mock emails for testing"""

        mock_scenarios = data.get("mock_scenarios", "all")  # all, urgent, normal, spam

        all_mock_emails = [
            {
                "from": "urgent.customer@techcorp.com",
                "subject": "URGENT: Production Server Down - Critical Issue",
                "body": """Our production server has been down for the past 30 minutes. This is a critical emergency affecting all our users. We need immediate assistance!

Error logs show database connection failures. This is costing us thousands per minute.

Please escalate this ASAP!""",
                "attachments": ["error_logs.txt"],
                "received_at": "2025-10-27T09:00:00Z"
            },
            {
                "from": "inquiry@startup.com",
                "subject": "Question about Enterprise Pricing",
                "body": """Hi there,

We're a growing startup and interested in your enterprise plan. A few questions:

1. Do you offer volume discounts for 50+ users?
2. What's included in the enterprise support package?
3. Can we get a custom demo?

Looking forward to hearing from you!

Best regards,
Sarah""",
                "attachments": [],
                "received_at": "2025-10-27T08:45:00Z"
            },
            {
                "from": "happy.client@company.com",
                "subject": "Thank you for excellent service!",
                "body": """I just wanted to send a quick note to thank your team for the outstanding support last week.

Your response time was incredible and the solution worked perfectly. This is why we love working with you!

Keep up the great work!

Cheers,
Michael""",
                "attachments": [],
                "received_at": "2025-10-27T08:30:00Z"
            },
            {
                "from": "lottery-winner@prize-claim.biz",
                "subject": "🎉 Congratulations! You've Won $1,000,000!",
                "body": """CONGRATULATIONS!!!

You have been selected as the WINNER of our international lottery!

To claim your prize of ONE MILLION DOLLARS, simply:
1. Click here immediately
2. Provide your bank details
3. Pay a small processing fee of $500

ACT NOW! This offer expires in 24 hours!

This is 100% legitimate and not a scam!""",
                "attachments": [],
                "received_at": "2025-10-27T08:15:00Z"
            },
            {
                "from": "noreply@notifications.service.com",
                "subject": "Your weekly report is ready",
                "body": """This is an automated notification.

Your weekly analytics report has been generated and is ready for download.

Visit your dashboard to view the report.

This is an automated message, please do not reply to this email.""",
                "attachments": [],
                "received_at": "2025-10-27T08:00:00Z"
            },
            {
                "from": "frustrated.user@example.com",
                "subject": "Very disappointed with recent update",
                "body": """I've been a loyal customer for 3 years, but I'm seriously considering canceling my subscription.

The recent update has broken several features I rely on daily. I've reported these issues multiple times with no response.

This is extremely frustrating and unprofessional. I need answers NOW.

If this isn't resolved immediately, I'm taking my business elsewhere.""",
                "attachments": [],
                "received_at": "2025-10-27T07:45:00Z"
            },
            {
                "from": "partner@bigcorp.com",
                "subject": "Partnership opportunity",
                "body": """Hi,

We've been following your company's growth and are impressed with your product.

We'd like to explore a potential partnership that could benefit both organizations. Are you available for a call next week to discuss?

Best regards,
Alex Chen
Business Development
BigCorp Industries""",
                "attachments": [],
                "received_at": "2025-10-27T07:30:00Z"
            },
            {
                "from": "support-request@client.com",
                "subject": "Feature request for mobile app",
                "body": """Hello,

We're using your software and love it! One feature that would be really helpful is offline mode for the mobile app.

Many of our field workers don't always have reliable internet access. Being able to sync data when they reconnect would be a game changer.

Is this something you're considering for future releases?

Thanks!
Emma""",
                "attachments": [],
                "received_at": "2025-10-27T07:00:00Z"
            }
        ]

        # Filter by scenario if specified
        if mock_scenarios == "urgent":
            return [e for e in all_mock_emails if "urgent" in e["subject"].lower() or "critical" in e["subject"].lower()]
        elif mock_scenarios == "normal":
            return [e for e in all_mock_emails if "question" in e["subject"].lower() or "request" in e["subject"].lower()]
        elif mock_scenarios == "spam":
            return [e for e in all_mock_emails if "congratulations" in e["subject"].lower() or "winner" in e["subject"].lower()]
        else:
            return all_mock_emails

    async def _fetch_imap_emails(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch emails from IMAP server (Gmail, etc.)"""

        # Configuration
        imap_config = data.get("imap_config", {})
        server = imap_config.get("server", "imap.gmail.com")
        port = imap_config.get("port", 993)
        username = imap_config.get("username")
        password = imap_config.get("password")
        folder = imap_config.get("folder", "INBOX")
        only_unread = imap_config.get("only_unread", True)

        if not username or not password:
            raise ValueError("IMAP requires username and password")

        try:
            import imaplib
            import email as email_lib
            from email.header import decode_header

            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(server, port)
            mail.login(username, password)
            mail.select(folder)

            # Search for emails
            search_criteria = 'UNSEEN' if only_unread else 'ALL'
            _, message_numbers = mail.search(None, search_criteria)

            emails = []
            for num in message_numbers[0].split()[:self.max_emails]:
                _, msg_data = mail.fetch(num, '(RFC822)')
                email_message = email_lib.message_from_bytes(msg_data[0][1])

                # Decode subject
                subject = decode_header(email_message["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()

                # Get email body
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = email_message.get_payload(decode=True).decode()

                # Get attachments
                attachments = []
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_disposition() == "attachment":
                            attachments.append(part.get_filename())

                emails.append({
                    "from": email_message.get("From"),
                    "subject": subject,
                    "body": body,
                    "attachments": attachments,
                    "received_at": email_message.get("Date")
                })

            mail.close()
            mail.logout()

            return emails

        except ImportError:
            raise ValueError("IMAP support requires 'imaplib' and 'email' packages")
        except Exception as e:
            raise ValueError(f"Failed to fetch IMAP emails: {str(e)}")

    async def _fetch_graph_emails(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch emails from Microsoft Graph API (Outlook/Office 365)"""

        graph_config = data.get("graph_config", {})
        access_token = graph_config.get("access_token")
        user_email = graph_config.get("user_email", "me")
        folder = graph_config.get("folder", "inbox")
        only_unread = graph_config.get("only_unread", True)

        if not access_token:
            raise ValueError("Graph API requires access_token")

        try:
            import aiohttp

            # Build Graph API URL
            url = f"https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/{folder}/messages"

            # Query parameters
            params = {
                "$top": self.max_emails,
                "$select": "from,subject,body,receivedDateTime,hasAttachments"
            }

            if only_unread:
                params["$filter"] = "isRead eq false"

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        raise ValueError(f"Graph API error: {response.status}")

                    result = await response.json()
                    emails = []

                    for msg in result.get("value", []):
                        emails.append({
                            "from": msg.get("from", {}).get("emailAddress", {}).get("address"),
                            "subject": msg.get("subject"),
                            "body": msg.get("body", {}).get("content"),
                            "attachments": [] if not msg.get("hasAttachments") else ["attachment"],
                            "received_at": msg.get("receivedDateTime")
                        })

                    return emails

        except ImportError:
            raise ValueError("Graph API support requires 'aiohttp' package")
        except Exception as e:
            raise ValueError(f"Failed to fetch Graph emails: {str(e)}")

    def _fetch_from_file(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Load emails from a JSON file"""

        file_path = data.get("file_path")
        if not file_path:
            raise ValueError("file source requires file_path")

        try:
            with open(file_path, 'r') as f:
                emails_data = json.load(f)

            if isinstance(emails_data, dict):
                emails = emails_data.get("emails", [])
            elif isinstance(emails_data, list):
                emails = emails_data
            else:
                raise ValueError("Invalid JSON format")

            return emails

        except Exception as e:
            raise ValueError(f"Failed to load emails from file: {str(e)}")
