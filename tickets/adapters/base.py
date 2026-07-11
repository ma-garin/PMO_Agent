from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, TypedDict

# ステータス名から完了/未完了を判定するための一般的なヒント集合。
# 個別チケットのis_done判定(各アダプタのfetch_tickets)とは別に、
# ステータス遷移履歴(TicketStatusTransition)の再オープン判定でのみ使う。
DONE_STATUS_NAME_HINTS = frozenset(
    {
        "done",
        "closed",
        "resolved",
        "rejected",
        "complete",
        "completed",
        "完了",
        "却下",
        "終了",
        "クローズ",
        "解決",
        "対応済み",
        "対応完了",
    }
)


def is_done_status_name(name: str) -> bool:
    return name.strip().lower() in DONE_STATUS_NAME_HINTS


class StatusTransitionEntry(TypedDict):
    from_status: str
    to_status: str
    occurred_at: datetime


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

    @abstractmethod
    def fetch_status_history(self, source, ticket) -> list[StatusTransitionEntry]:
        """指定チケットのステータス遷移履歴を取得する(読み取り専用)。"""
        raise NotImplementedError


class TicketSourceConnectionError(Exception):
    pass
