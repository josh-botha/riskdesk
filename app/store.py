"""Incident storage: in memory for local runs and tests, DynamoDB on AWS."""

from decimal import Decimal
from typing import Protocol

from .models import Incident


class IncidentStore(Protocol):
    def put(self, incident: Incident) -> None: ...
    def get(self, incident_id: str) -> Incident | None: ...
    def list(self) -> list[Incident]: ...


class MemoryStore:
    def __init__(self) -> None:
        self._items: dict[str, Incident] = {}

    def put(self, incident: Incident) -> None:
        self._items[incident.id] = incident

    def get(self, incident_id: str) -> Incident | None:
        return self._items.get(incident_id)

    def list(self) -> list[Incident]:
        return sorted(self._items.values(), key=lambda i: i.created_at, reverse=True)


class DynamoStore:
    """One item per incident, keyed on id. DynamoDB has no float type, so the
    loss is stored as a Decimal string and converted back on read."""

    def __init__(self, table) -> None:
        self.table = table

    def put(self, incident: Incident) -> None:
        item = incident.model_dump(mode="json")
        item["gross_loss_aud"] = Decimal(str(incident.gross_loss_aud))
        self.table.put_item(Item=item)

    def get(self, incident_id: str) -> Incident | None:
        item = self.table.get_item(Key={"id": incident_id}).get("Item")
        return self._load(item) if item else None

    def list(self) -> list[Incident]:
        items, kwargs = [], {}
        while True:
            page = self.table.scan(**kwargs)
            items.extend(page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        incidents = [self._load(item) for item in items]
        return sorted(incidents, key=lambda i: i.created_at, reverse=True)

    @staticmethod
    def _load(item: dict) -> Incident:
        item = dict(item)
        item["gross_loss_aud"] = float(item["gross_loss_aud"])
        return Incident.model_validate(item)
