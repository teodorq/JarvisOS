from __future__ import annotations

import os
import re
import threading
import time
import uuid
from typing import Any, Protocol

COMMAND_TTL_SECONDS = 86_400
CLAIM_LEASE_SECONDS = 120
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "expired"})
ALLOWED_EVENT_STATUSES = frozenset({"waiting_local_confirmation", "completed", "failed", "cancelled"})
_DEVICE_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_COMMAND_ID = re.compile(r"^[a-f0-9]{32}$")

class RemoteStoreError(RuntimeError):
    """Raised when the durable command relay cannot be used safely."""

class RemoteCommandStore(Protocol):
    def create(self, device_id: str, command: str) -> dict[str, Any]: ...
    def claim_next(self, device_id: str) -> dict[str, Any] | None: ...
    def get(self, device_id: str, command_id: str) -> dict[str, Any] | None: ...
    def set_status(self, device_id: str, command_id: str, status: str, message: str) -> dict[str, Any] | None: ...

def normalize_device_id(value: object) -> str:
    device_id = str(value or "").strip().lower()
    if not _DEVICE_ID.fullmatch(device_id):
        raise ValueError("invalid device id")
    return device_id

def normalize_command_id(value: object) -> str:
    command_id = str(value or "").strip().lower()
    if not _COMMAND_ID.fullmatch(command_id):
        raise ValueError("invalid command id")
    return command_id

def normalize_event_status(value: object) -> str:
    status = str(value or "").strip().lower()
    if status not in ALLOWED_EVENT_STATUSES:
        raise ValueError("invalid command status")
    return status

class MemoryRemoteCommandStore:
    def __init__(self, clock=time.time) -> None:
        self.clock = clock
        self._lock = threading.Lock()
        self._records: dict[tuple[str, str], dict[str, Any]] = {}

    def create(self, device_id: str, command: str) -> dict[str, Any]:
        device_id = normalize_device_id(device_id)
        now = int(self.clock())
        record = {"id": uuid.uuid4().hex, "device_id": device_id, "command": str(command), "status": "queued", "message": "Polecenie czeka na komputer.", "created_at": now, "updated_at": now, "expires_at": now + COMMAND_TTL_SECONDS, "lease_until": 0}
        with self._lock:
            self._cleanup(now)
            self._records[(device_id, record["id"])] = record
            return dict(record)

    def claim_next(self, device_id: str) -> dict[str, Any] | None:
        device_id = normalize_device_id(device_id)
        now = int(self.clock())
        with self._lock:
            self._cleanup(now)
            candidates = [record for (owner, _), record in self._records.items() if owner == device_id and (record["status"] == "queued" or (record["status"] == "claimed" and int(record.get("lease_until", 0)) <= now))]
            if not candidates:
                return None
            record = min(candidates, key=lambda item: int(item["created_at"]))
            record.update(status="claimed", message="Komputer odebra\u0142 polecenie.", updated_at=now, lease_until=now + CLAIM_LEASE_SECONDS)
            return dict(record)

    def get(self, device_id: str, command_id: str) -> dict[str, Any] | None:
        key = (normalize_device_id(device_id), normalize_command_id(command_id))
        with self._lock:
            self._cleanup(int(self.clock()))
            record = self._records.get(key)
            return dict(record) if record is not None else None

    def set_status(self, device_id: str, command_id: str, status: str, message: str) -> dict[str, Any] | None:
        key = (normalize_device_id(device_id), normalize_command_id(command_id))
        status = normalize_event_status(status)
        now = int(self.clock())
        with self._lock:
            self._cleanup(now)
            record = self._records.get(key)
            if record is None or record["status"] in TERMINAL_STATUSES:
                return dict(record) if record is not None else None
            record.update(status=status, message=str(message)[:2_000], updated_at=now, lease_until=0 if status in TERMINAL_STATUSES else now + CLAIM_LEASE_SECONDS)
            return dict(record)

    def _cleanup(self, now: int) -> None:
        for key in [key for key, record in self._records.items() if int(record.get("expires_at", 0)) <= now]:
            self._records.pop(key, None)

class AzureTableRemoteCommandStore:
    def __init__(self, connection_string: str, table_name: str = "commands") -> None:
        try:
            from azure.core.exceptions import ResourceNotFoundError
            from azure.data.tables import TableServiceClient, UpdateMode
        except ImportError as error:
            raise RemoteStoreError("azure-data-tables is not installed") from error
        self._not_found = ResourceNotFoundError
        self._update_mode = UpdateMode.REPLACE
        self.table = TableServiceClient.from_connection_string(connection_string).create_table_if_not_exists(table_name)

    @staticmethod
    def _public(entity: dict[str, Any]) -> dict[str, Any]:
        return {"id": str(entity.get("RowKey", "")), "device_id": str(entity.get("PartitionKey", "")), "command": str(entity.get("Command", "")), "status": str(entity.get("Status", "")), "message": str(entity.get("Message", "")), "created_at": int(entity.get("CreatedAt", 0)), "updated_at": int(entity.get("UpdatedAt", 0)), "expires_at": int(entity.get("ExpiresAt", 0))}

    def create(self, device_id: str, command: str) -> dict[str, Any]:
        device_id = normalize_device_id(device_id)
        now = int(time.time())
        entity = {"PartitionKey": device_id, "RowKey": uuid.uuid4().hex, "Command": str(command), "Status": "queued", "Message": "Polecenie czeka na komputer.", "CreatedAt": now, "UpdatedAt": now, "ExpiresAt": now + COMMAND_TTL_SECONDS, "LeaseUntil": 0}
        self._cleanup(device_id, now)
        self.table.create_entity(entity)
        return self._public(entity)

    def claim_next(self, device_id: str) -> dict[str, Any] | None:
        device_id = normalize_device_id(device_id)
        now = int(time.time())
        self._cleanup(device_id, now)
        records = list(self.table.query_entities(query_filter=f"PartitionKey eq '{device_id}'"))
        candidates = [record for record in records if record.get("Status") == "queued" or (record.get("Status") == "claimed" and int(record.get("LeaseUntil", 0)) <= now)]
        if not candidates:
            return None
        entity = min(candidates, key=lambda item: int(item.get("CreatedAt", 0)))
        entity.update(Status="claimed", Message="Komputer odebra\u0142 polecenie.", UpdatedAt=now, LeaseUntil=now + CLAIM_LEASE_SECONDS)
        self.table.update_entity(entity, mode=self._update_mode)
        return self._public(entity)

    def get(self, device_id: str, command_id: str) -> dict[str, Any] | None:
        device_id, command_id = normalize_device_id(device_id), normalize_command_id(command_id)
        try:
            entity = self.table.get_entity(device_id, command_id)
        except self._not_found:
            return None
        if int(entity.get("ExpiresAt", 0)) <= int(time.time()):
            self.table.delete_entity(device_id, command_id)
            return None
        return self._public(entity)

    def set_status(self, device_id: str, command_id: str, status: str, message: str) -> dict[str, Any] | None:
        device_id, command_id = normalize_device_id(device_id), normalize_command_id(command_id)
        status = normalize_event_status(status)
        try:
            entity = self.table.get_entity(device_id, command_id)
        except self._not_found:
            return None
        if str(entity.get("Status")) in TERMINAL_STATUSES:
            return self._public(entity)
        now = int(time.time())
        entity.update(Status=status, Message=str(message)[:2_000], UpdatedAt=now, LeaseUntil=0 if status in TERMINAL_STATUSES else now + CLAIM_LEASE_SECONDS)
        self.table.update_entity(entity, mode=self._update_mode)
        return self._public(entity)

    def _cleanup(self, device_id: str, now: int) -> None:
        expired = self.table.query_entities(
            query_filter=f"PartitionKey eq '{device_id}'",
        )
        for index, entity in enumerate(expired):
            if index >= 50:
                break
            if int(entity.get("ExpiresAt", 0)) <= now:
                self.table.delete_entity(entity["PartitionKey"], entity["RowKey"])

def remote_store_from_environment() -> RemoteCommandStore | None:
    connection = os.getenv("JARVIS_OS_REMOTE_STORAGE_CONNECTION", "").strip()
    if not connection:
        return None
    table_name = os.getenv("JARVIS_OS_REMOTE_TABLE", "commands").strip() or "commands"
    return AzureTableRemoteCommandStore(connection, table_name)
