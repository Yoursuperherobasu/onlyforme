from datetime import datetime, timezone

from loguru import logger

from agentcore.custom.custom_node.node import Node
from agentcore.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    Output,
    SecretStrInput,
)
from agentcore.schema.data import Data
from agentcore.schema.dataframe import DataFrame
from agentcore.schema.message import Message
from agentcore.utils.constants import MESSAGE_SENDER_USER


class EmailTrigger(Node):
    display_name = "Email Trigger"
    description = "Triggers the flow when new emails arrive. Outputs email content and attachments."
    icon = "Mail"
    name = "EmailTrigger"

    inputs = [
        DropdownInput(
            name="protocol",
            display_name="Protocol",
            options=["IMAP", "Microsoft Graph"],
            value="IMAP",
            info="Email retrieval protocol.",
            real_time_refresh=True,
        ),
        # --- IMAP inputs ---
        MessageTextInput(
            name="imap_server",
            display_name="IMAP Server",
            info="IMAP server address (e.g., 'imap.gmail.com', 'outlook.office365.com').",
        ),
        IntInput(
            name="imap_port",
            display_name="Port",
            value=993,
            info="IMAP server port. Usually 993 for SSL.",
        ),
        # --- Microsoft Graph inputs ---
        SecretStrInput(
            name="graph_client_id",
            display_name="App Client ID",
            info="Azure AD App Registration client ID for Microsoft Graph.",
        ),
        SecretStrInput(
            name="graph_client_secret",
            display_name="App Client Secret",
            info="Azure AD App Registration client secret.",
        ),
        MessageTextInput(
            name="graph_tenant_id",
            display_name="Tenant ID",
            info="Azure AD tenant ID.",
        ),
        MessageTextInput(
            name="graph_user_email",
            display_name="User Email",
            info="Email address of the mailbox to monitor via Graph API.",
        ),
        # --- Common ---
        MessageTextInput(
            name="email_user",
            display_name="Email",
            info="Email address for IMAP login.",
        ),
        SecretStrInput(
            name="email_password",
            display_name="Password",
            info="Email password or app password for IMAP login.",
        ),
        MessageTextInput(
            name="folder",
            display_name="Mailbox Folder",
            value="INBOX",
            info="Mailbox folder to monitor (e.g., INBOX, Sent).",
        ),
        IntInput(
            name="poll_interval_seconds",
            display_name="Poll Interval (seconds)",
            value=60,
            info="How often to check for new emails (used when deployed).",
        ),
        BoolInput(
            name="mark_as_read",
            display_name="Mark As Read",
            value=True,
            info="Mark fetched emails as read after processing.",
        ),
        IntInput(
            name="batch_size",
            display_name="Max Emails Per Trigger",
            value=5,
            info="Maximum number of emails to process per trigger. 0 = unlimited.",
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID for this trigger. If empty, a new session is created per execution.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Emails",
            name="emails",
            method="emails_output",
        ),
        Output(
            display_name="Trigger Info",
            name="trigger_info",
            method="info_output",
        ),
    ]

    def update_build_config(self, build_config, field_value, field_name=None):
        """Show/hide inputs based on protocol selection."""
        from agentcore.utils.component_utils import set_current_fields, set_field_display

        mode_config = {
            "IMAP": [
                "imap_server",
                "imap_port",
                "email_user",
                "email_password",
            ],
            "Microsoft Graph": [
                "graph_client_id",
                "graph_client_secret",
                "graph_tenant_id",
                "graph_user_email",
            ],
        }
        default_keys = [
            "code",
            "_type",
            "protocol",
            "folder",
            "poll_interval_seconds",
            "mark_as_read",
            "batch_size",
            "session_id",
        ]
        return set_current_fields(
            build_config=build_config,
            action_fields=mode_config,
            selected_action=build_config["protocol"]["value"],
            default_fields=default_keys,
            func=set_field_display,
        )

    async def _fetch_imap_emails(self) -> list[Data]:
        """Fetch emails via IMAP."""
        import asyncio

        def _do_fetch():
            import email
            import imaplib

            server = self.imap_server
            port = self.imap_port
            user = self.email_user
            password = self.email_password
            mailbox = self.folder or "INBOX"
            mark_read = self.mark_as_read
            batch_size = self.batch_size

            mail = imaplib.IMAP4_SSL(server, port)
            try:
                mail.login(user, password)
                mail.select(mailbox)

                # Search for unseen emails
                status, data = mail.search(None, "UNSEEN")
                if status != "OK" or not data[0]:
                    return []

                email_ids = data[0].split()
                if batch_size and batch_size > 0:
                    email_ids = email_ids[:batch_size]

                results = []
                for eid in email_ids:
                    status, msg_data = mail.fetch(eid, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    subject = msg.get("Subject", "")
                    sender = msg.get("From", "")
                    date = msg.get("Date", "")
                    to = msg.get("To", "")

                    # Extract body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body = payload.decode("utf-8", errors="replace")
                                break
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")

                    # Extract attachment names
                    attachments = []
                    if msg.is_multipart():
                        for part in msg.walk():
                            filename = part.get_filename()
                            if filename:
                                attachments.append(filename)

                    results.append(
                        Data(
                            data={
                                "text": body,
                                "subject": subject,
                                "sender": sender,
                                "to": to,
                                "date": date,
                                "attachments": attachments,
                                "source": f"imap://{server}/{mailbox}",
                            }
                        )
                    )

                    if mark_read:
                        mail.store(eid, "+FLAGS", "\\Seen")

                return results
            finally:
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass

        return await asyncio.to_thread(_do_fetch)

    async def _fetch_graph_emails(self) -> list[Data]:
        """Fetch emails via Microsoft Graph API."""
        import asyncio

        def _do_fetch():
            import json
            from urllib.request import Request, urlopen

            client_id = self.graph_client_id
            client_secret = self.graph_client_secret
            tenant_id = self.graph_tenant_id
            user_email = self.graph_user_email
            mailbox = self.folder or "INBOX"
            mark_read = self.mark_as_read
            batch_size = self.batch_size or 5

            # Get access token
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            token_data = (
                f"client_id={client_id}"
                f"&client_secret={client_secret}"
                f"&scope=https://graph.microsoft.com/.default"
                f"&grant_type=client_credentials"
            ).encode()
            token_req = Request(token_url, data=token_data, method="POST")
            token_req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urlopen(token_req) as resp:
                token_info = json.loads(resp.read())
            access_token = token_info["access_token"]

            # Fetch unread emails
            headers = {"Authorization": f"Bearer {access_token}"}
            folder_filter = f"mailFolders/{mailbox}" if mailbox != "INBOX" else "mailFolders/inbox"
            messages_url = (
                f"https://graph.microsoft.com/v1.0/users/{user_email}/{folder_filter}/messages"
                f"?$filter=isRead eq false&$top={batch_size}&$orderby=receivedDateTime desc"
            )
            msg_req = Request(messages_url)
            for k, v in headers.items():
                msg_req.add_header(k, v)
            with urlopen(msg_req) as resp:
                messages_data = json.loads(resp.read())

            results = []
            for msg in messages_data.get("value", []):
                body_content = msg.get("body", {}).get("content", "")
                results.append(
                    Data(
                        data={
                            "text": body_content,
                            "subject": msg.get("subject", ""),
                            "sender": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                            "to": ", ".join(
                                r.get("emailAddress", {}).get("address", "")
                                for r in msg.get("toRecipients", [])
                            ),
                            "date": msg.get("receivedDateTime", ""),
                            "attachments": [],
                            "source": f"graph://{user_email}/{mailbox}",
                        }
                    )
                )

                # Mark as read
                if mark_read:
                    msg_id = msg.get("id")
                    patch_url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{msg_id}"
                    patch_data = json.dumps({"isRead": True}).encode()
                    patch_req = Request(patch_url, data=patch_data, method="PATCH")
                    for k, v in headers.items():
                        patch_req.add_header(k, v)
                    patch_req.add_header("Content-Type", "application/json")
                    try:
                        with urlopen(patch_req):
                            pass
                    except Exception as e:
                        logger.warning(f"Failed to mark email {msg_id} as read: {e}")

            return results

        return await asyncio.to_thread(_do_fetch)

    async def emails_output(self) -> DataFrame:
        """Fetch emails and return as DataFrame."""
        protocol = self.protocol

        if protocol == "IMAP":
            data_list = await self._fetch_imap_emails()
        elif protocol == "Microsoft Graph":
            data_list = await self._fetch_graph_emails()
        else:
            data_list = []

        self.status = data_list
        return DataFrame(data_list)

    async def info_output(self) -> Message:
        """Return trigger metadata as a Message."""
        now = datetime.now(timezone.utc)
        protocol = self.protocol

        metadata = {
            "trigger_type": "email",
            "protocol": protocol,
            "triggered_at": now.isoformat(),
            "folder": self.folder,
            "batch_size": self.batch_size,
        }

        if protocol == "IMAP":
            metadata["imap_server"] = self.imap_server
            metadata["email_user"] = self.email_user
        elif protocol == "Microsoft Graph":
            metadata["user_email"] = self.graph_user_email

        message = await Message.create(
            text=f"Email trigger fired ({protocol})",
            sender=MESSAGE_SENDER_USER,
            sender_name="EmailTrigger",
            session_id=self.session_id if hasattr(self, "session_id") and self.session_id else "",
            properties={"trigger_metadata": metadata},
        )

        self.status = message
        return message
