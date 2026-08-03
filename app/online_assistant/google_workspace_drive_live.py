from __future__ import annotations

from typing import Any

from app.online_assistant.common import OnlineAssistantError, safe_error


class DriveLiveProviderMixin:
    """Bounded, read-only listing of recently modified Google Drive files."""

    def list_recent_drive_files(
        self, *, max_results: int = 10
    ) -> list[dict[str, Any]]:
        try:
            result = self._service("drive", "v3").files().list(
                q="trashed = false",
                pageSize=max(1, min(int(max_results), 25)),
                fields=(
                    "files(id,name,mimeType,modifiedTime,size,webViewLink,parents)"
                ),
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
                "Nie udało się odczytać ostatnich dokumentów z Dysku Google: "
                + safe_error(error)
            ) from None


__all__ = ["DriveLiveProviderMixin"]
