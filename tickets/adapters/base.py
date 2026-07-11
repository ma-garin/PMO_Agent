from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class NormalizedTicket:
    external_id: str
    summary: str
    external_url: str = ""
    description: str = ""
    status: str = ""
    is_done: bool = False
    priority: str = ""
    ticket_type: str = ""
    assignee_name: str = ""
    reporter_name: str = ""
    due_date: date | None = None
    source_created_at: datetime | None = None
    source_updated_at: datetime | None = None
    closed_at: datetime | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


class TicketAdapter(ABC):
    """チケット管理システムへの読み取り専用アクセスを抽象化するインターフェース。

    本システムはJIRA/Redmineへの書き込みを行わない（読み取り専用、ADR未満だが
    docs/DESIGN.md 3.1で確定した方針）。実装はfetch_ticketsのみを提供する。
    """

    @abstractmethod
    def fetch_tickets(self, source) -> list[NormalizedTicket]:
        raise NotImplementedError


class TicketSourceConnectionError(Exception):
    pass
