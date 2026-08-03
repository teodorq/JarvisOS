from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import importlib.util
import io
import json
import os
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root
from app.online_assistant.common import OnlineAssistantError, header_value, safe_error
from app.online_assistant.google_workspace_drive_live import DriveLiveProviderMixin
from app.online_assistant.google_workspace_gmail_writes import GmailWriteProviderMixin
from app.online_assistant.google_workspace_gmail_live import GmailLiveProviderMixin
from app.online_assistant.google_workspace_calendar_writes import CalendarWriteProviderMixin


class GoogleWorkspaceProvider(
    GmailWriteProviderMixin, CalendarWriteProviderMixin,
    GmailLiveProviderMixin, DriveLiveProviderMixin,
):
    """Optional Google Workspace adapter loaded lazily after explicit OAuth consent."""

    SCOPES = (
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
        "https://www.googleapis.com/auth/drive.file",
    )
    REQUIRED_MODULES = (
        "google.auth",
        "google.oauth2.credentials",
        "google_auth_oauthlib.flow",
        "googleapiclient.discovery",
        "googleapiclient.http",
    )

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        local_app_data = Path(
            os.getenv("LOCALAPPDATA", str(Path.home() / ".jarvis_os"))
        ).expanduser()
        self.secret_root = local_app_data / "JARVIS_OS" / "secrets"
        self.client_config_path = self.secret_root / "google_workspace_client_secret.json"
        self.token_path = self.secret_root / "google_workspace_token.json"
        self._services: dict[str, Any] = {}

    def dependency_status(self) -> dict[str, Any]:
        missing: list[str] = []
        for name in self.REQUIRED_MODULES:
            try:
                available = importlib.util.find_spec(name) is not None
            except (ImportError, ModuleNotFoundError, AttributeError):
                available = False
            if not available:
                missing.append(name)
        return {
            "ready": not missing,
            "missing": missing,
            "requirements_file": str(
                self.project_root / "requirements_google_workspace.txt"
            ),
        }

    def connection_status(self) -> dict[str, Any]:
        dependency = self.dependency_status()
        token_present = self.token_path.is_file()
        return {
            "status": "GOOGLE_WORKSPACE_CONNECTED" if dependency["ready"] and token_present else "GOOGLE_WORKSPACE_NOT_CONNECTED",
            "dependency_ready": dependency["ready"],
            "missing_dependencies": list(dependency["missing"]),
            "client_configured": self.client_config_path.is_file(),
            "token_present": token_present,
            "client_config_path": str(self.client_config_path),
            "token_path": str(self.token_path),
            "scopes": list(self.SCOPES),
            "automatic_sending": False,
            "automatic_sync": False,
        }

    def connect(self) -> dict[str, Any]:
        dependency = self.dependency_status()
        if not dependency["ready"]:
            raise OnlineAssistantError(
                "B126: brak bibliotek Google Workspace. Uruchom INSTALL_GOOGLE_WORKSPACE_SUPPORT.cmd."
            )
        if not self.client_config_path.is_file():
            raise OnlineAssistantError(
                "B126: brak pliku OAuth w LOCALAPPDATA\\JARVIS_OS\\secrets\\google_workspace_client_secret.json. "
                "Dodaj klienta typu Desktop app, a potem połącz ponownie."
            )
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow

            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.client_config_path), list(self.SCOPES)
            )
            credentials = flow.run_local_server(
                port=0,
                open_browser=True,
                authorization_prompt_message=(
                    "Otwieram bezpieczne okno Google OAuth w domyślnej przeglądarce."
                ),
                success_message=(
                    "JARVIS OS: autoryzacja zakończona. Możesz zamknąć tę kartę."
                ),
            )
            self._save_credentials(credentials)
            self._services.clear()
            probes = self.live_probe()
            return {
                "status": "GOOGLE_WORKSPACE_CONNECTED",
                "gmail": probes["gmail"],
                "calendar": probes["calendar"],
                "drive": probes["drive"],
            }
        except OnlineAssistantError:
            raise
        except Exception as error:
            raise OnlineAssistantError(
                f"B126: połączenie Google nie powiodło się: {safe_error(error)}"
            ) from None

    def disconnect(self) -> dict[str, Any]:
        self._services.clear()
        removed = False
        try:
            if self.token_path.exists():
                self.token_path.unlink()
                removed = True
        except OSError as error:
            raise OnlineAssistantError(
                f"B126: nie udało się usunąć lokalnego tokenu: {safe_error(error)}"
            ) from None
        return {"status": "GOOGLE_WORKSPACE_DISCONNECTED", "token_removed": removed}

    def live_probe(self) -> dict[str, bool]:
        results: dict[str, bool] = {"gmail": False, "calendar": False, "drive": False}
        errors: list[str] = []
        try:
            self._service("gmail", "v1").users().getProfile(userId="me").execute()
            results["gmail"] = True
        except Exception as error:
            errors.append("Gmail: " + safe_error(error))
        try:
            now = datetime.now(timezone.utc).isoformat()
            self._service("calendar", "v3").events().list(
                calendarId="primary",
                timeMin=now,
                maxResults=1,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            results["calendar"] = True
        except Exception as error:
            errors.append("Kalendarz: " + safe_error(error))
        try:
            self._service("drive", "v3").about().get(fields="user").execute()
            results["drive"] = True
        except Exception as error:
            errors.append("Dysk: " + safe_error(error))
        if errors and not any(results.values()):
            raise OnlineAssistantError(
                "B126–B128: test połączenia nie przeszedł. " + " | ".join(errors)
            )
        return results

    def list_gmail_messages(
        self,
        *,
        query: str = "in:inbox",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        try:
            service = self._service("gmail", "v1")
            listing = service.users().messages().list(
                userId="me",
                q=str(query)[:500],
                maxResults=max(1, min(int(max_results), 25)),
            ).execute()
            results: list[dict[str, Any]] = []
            for item in list(listing.get("messages", []) or []):
                message = service.users().messages().get(
                    userId="me",
                    id=item["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date", "To"],
                ).execute()
                payload = dict(message.get("payload", {}) or {})
                headers = list(payload.get("headers", []) or [])
                labels = list(message.get("labelIds", []) or [])
                results.append({
                    "id": str(message.get("id", "")),
                    "thread_id": str(message.get("threadId", "")),
                    "from": header_value(headers, "From"),
                    "to": header_value(headers, "To"),
                    "subject": header_value(headers, "Subject") or "(bez tematu)",
                    "date": header_value(headers, "Date"),
                    "snippet": str(message.get("snippet", ""))[:500],
                    "unread": "UNREAD" in labels,
                    "important": "IMPORTANT" in labels or "STARRED" in labels,
                    "labels": labels,
                })
            return results
        except Exception as error:
            raise OnlineAssistantError(
                f"B126: odczyt Gmail nie powiódł się: {safe_error(error)}"
            ) from None

    def create_gmail_draft(self, recipient: str, subject: str, body: str) -> dict[str, Any]:
        if "@" not in str(recipient):
            raise OnlineAssistantError("B126: podaj poprawny adres odbiorcy.")
        message = EmailMessage()
        message["To"] = str(recipient).strip()
        message["Subject"] = str(subject).strip()[:240] or "Wiadomość od JARVIS OS"
        message.set_content(str(body)[:100_000])
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        try:
            result = self._service("gmail", "v1").users().drafts().create(
                userId="me",
                body={"message": {"raw": raw}},
            ).execute()
            return {
                "status": "GMAIL_DRAFT_CREATED",
                "draft_id": str(result.get("id", "")),
                "message_id": str(dict(result.get("message", {}) or {}).get("id", "")),
                "recipient": str(recipient),
                "subject": str(subject),
            }
        except Exception as error:
            raise OnlineAssistantError(
                f"B126: utworzenie szkicu Gmail nie powiodło się: {safe_error(error)}"
            ) from None

    def send_gmail_draft(self, draft_id: str) -> dict[str, Any]:
        if not str(draft_id).strip():
            raise OnlineAssistantError("B126: podaj identyfikator szkicu Gmail.")
        try:
            result = self._service("gmail", "v1").users().drafts().send(
                userId="me",
                body={"id": str(draft_id).strip()},
            ).execute()
            return {
                "status": "GMAIL_DRAFT_SENT",
                "message_id": str(result.get("id", "")),
                "thread_id": str(result.get("threadId", "")),
            }
        except Exception as error:
            raise OnlineAssistantError(
                f"B126: wysłanie szkicu Gmail nie powiodło się: {safe_error(error)}"
            ) from None

    def list_calendar_events(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        max_results: int = 25,
    ) -> list[dict[str, Any]]:
        try:
            result = self._service("calendar", "v3").events().list(
                calendarId="primary",
                timeMin=start_at.astimezone(timezone.utc).isoformat(),
                timeMax=end_at.astimezone(timezone.utc).isoformat(),
                maxResults=max(1, min(int(max_results), 50)),
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            events: list[dict[str, Any]] = []
            for item in list(result.get("items", []) or []):
                start = dict(item.get("start", {}) or {})
                end = dict(item.get("end", {}) or {})
                events.append({
                    "id": str(item.get("id", "")),
                    "title": str(item.get("summary", "(bez nazwy)"))[:300],
                    "start_at": str(start.get("dateTime") or start.get("date") or ""),
                    "end_at": str(end.get("dateTime") or end.get("date") or ""),
                    "location": str(item.get("location", ""))[:300],
                    "status": str(item.get("status", "")),
                    "html_link": str(item.get("htmlLink", "")),
                })
            return events
        except Exception as error:
            raise OnlineAssistantError(
                f"B127: odczyt Kalendarza Google nie powiódł się: {safe_error(error)}"
            ) from None

    def create_calendar_event(
        self,
        *,
        title: str,
        start_at: datetime,
        duration_minutes: int = 30,
        description: str = "",
        reminder_minutes: int | None = None,
    ) -> dict[str, Any]:
        local_start = (
            start_at
            if start_at.utcoffset() is not None
            else start_at.astimezone()
        )
        local_end = local_start + timedelta(minutes=max(5, min(int(duration_minutes), 1440)))
        body = {
            "summary": str(title)[:300],
            "description": str(description)[:5000],
            # RFC3339 offsets are portable on Windows.  Do not send labels
            # such as ``UTC+02:00`` as Google Calendar timeZone values.
            "start": {"dateTime": local_start.isoformat()},
            "end": {"dateTime": local_end.isoformat()},
        }
        if reminder_minutes is not None:
            minutes = max(0, min(int(reminder_minutes), 40320))
            body["reminders"] = {"useDefault": False, "overrides": [{"method": "popup", "minutes": minutes}]}
        try:
            result = self._service("calendar", "v3").events().insert(
                calendarId="primary", body=body, sendUpdates="none"
            ).execute()
            return {
                "status": "GOOGLE_CALENDAR_EVENT_CREATED",
                "event_id": str(result.get("id", "")),
                "title": str(result.get("summary", title)),
                "start_at": str(dict(result.get("start", {}) or {}).get("dateTime", local_start.isoformat())),
                "html_link": str(result.get("htmlLink", "")),
                "reminder_minutes": reminder_minutes,
            }
        except Exception as error:
            raise OnlineAssistantError(
                f"B127: utworzenie wydarzenia nie powiodło się: {safe_error(error)}"
            ) from None

    def search_drive_files(self, query: str, *, max_results: int = 20) -> list[dict[str, Any]]:
        term = str(query).strip()
        if not term:
            raise OnlineAssistantError("B128: podaj tekst wyszukiwania na Dysku Google.")
        escaped = term.replace("'", "\\'")
        try:
            result = self._service("drive", "v3").files().list(
                q=f"trashed = false and name contains '{escaped}'",
                pageSize=max(1, min(int(max_results), 50)),
                fields="files(id,name,mimeType,modifiedTime,size,webViewLink,parents)",
                orderBy="modifiedTime desc",
            ).execute()
            return [
                {
                    "id": str(item.get("id", "")),
                    "name": str(item.get("name", ""))[:500],
                    "mime_type": str(item.get("mimeType", "")),
                    "modified_at": str(item.get("modifiedTime", "")),
                    "size": int(item.get("size", 0) or 0),
                    "web_view_link": str(item.get("webViewLink", "")),
                }
                for item in list(result.get("files", []) or [])
            ]
        except Exception as error:
            raise OnlineAssistantError(
                f"B128: wyszukiwanie na Dysku Google nie powiodło się: {safe_error(error)}"
            ) from None

    def read_drive_text(self, file_id: str, mime_type: str) -> str:
        try:
            service = self._service("drive", "v3")
            if str(mime_type).startswith("application/vnd.google-apps"):
                request = service.files().export_media(
                    fileId=str(file_id), mimeType="text/plain"
                )
            else:
                request = service.files().get_media(fileId=str(file_id))
            data = request.execute()
            if isinstance(data, bytes):
                return data[:250_000].decode("utf-8", errors="replace")
            return str(data)[:250_000]
        except Exception as error:
            raise OnlineAssistantError(
                f"B128: odczyt dokumentu z Dysku nie powiódł się: {safe_error(error)}"
            ) from None

    def create_drive_text_file(self, name: str, content: str) -> dict[str, Any]:
        try:
            from googleapiclient.http import MediaIoBaseUpload

            media = MediaIoBaseUpload(
                io.BytesIO(str(content).encode("utf-8")),
                mimetype="text/plain",
                resumable=False,
            )
            result = self._service("drive", "v3").files().create(
                body={"name": str(name)[:240], "mimeType": "text/plain"},
                media_body=media,
                fields="id,name,mimeType,webViewLink,modifiedTime",
            ).execute()
            return {
                "status": "GOOGLE_DRIVE_FILE_CREATED",
                "file_id": str(result.get("id", "")),
                "name": str(result.get("name", name)),
                "web_view_link": str(result.get("webViewLink", "")),
            }
        except Exception as error:
            raise OnlineAssistantError(
                f"B128: zapis raportu na Dysku Google nie powiódł się: {safe_error(error)}"
            ) from None

    def _service(self, name: str, version: str) -> Any:
        key = f"{name}:{version}"
        if key in self._services:
            return self._services[key]
        credentials = self._load_credentials()
        try:
            from googleapiclient.discovery import build

            service = build(name, version, credentials=credentials, cache_discovery=False)
            self._services[key] = service
            return service
        except Exception as error:
            raise OnlineAssistantError(
                f"B126–B128: nie udało się uruchomić API {name}: {safe_error(error)}"
            ) from None

    def _load_credentials(self) -> Any:
        dependency = self.dependency_status()
        if not dependency["ready"]:
            raise OnlineAssistantError(
                "B126: brak bibliotek Google Workspace. Uruchom INSTALL_GOOGLE_WORKSPACE_SUPPORT.cmd."
            )
        if not self.token_path.is_file():
            raise OnlineAssistantError(
                "B126: Google Workspace nie jest połączony. Użyj polecenia „Połącz Google Workspace”."
            )
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            credentials = Credentials.from_authorized_user_file(
                str(self.token_path), list(self.SCOPES)
            )
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self._save_credentials(credentials)
            if not credentials.valid:
                raise OnlineAssistantError(
                    "B126: lokalny token Google wygasł. Rozłącz i połącz konto ponownie."
                )
            return credentials
        except OnlineAssistantError:
            raise
        except Exception as error:
            raise OnlineAssistantError(
                f"B126: nie udało się odczytać lokalnego tokenu Google: {safe_error(error)}"
            ) from None

    def _save_credentials(self, credentials: Any) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.token_path.with_suffix(".tmp")
        temporary.write_text(credentials.to_json(), encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            raise RuntimeError("AutoDev: przechwycony wyjątek")
        os.replace(temporary, self.token_path)
        try:
            os.chmod(self.token_path, 0o600)
        except OSError:
            raise RuntimeError("AutoDev: przechwycony wyjątek")
