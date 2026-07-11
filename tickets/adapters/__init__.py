from ..models import TicketSource
from .base import NormalizedTicket, TicketAdapter, TicketSourceConnectionError
from .jira import JiraAdapter
from .redmine import RedmineAdapter

_ADAPTERS: dict[str, type[TicketAdapter]] = {
    TicketSource.Kind.JIRA: JiraAdapter,
    TicketSource.Kind.REDMINE: RedmineAdapter,
}


def get_adapter(kind: str) -> TicketAdapter:
    try:
        adapter_class = _ADAPTERS[kind]
    except KeyError as exc:
        raise ValueError(f"未対応のチケットソース種別です: {kind}") from exc
    return adapter_class()


__all__ = [
    "NormalizedTicket",
    "TicketAdapter",
    "TicketSourceConnectionError",
    "JiraAdapter",
    "RedmineAdapter",
    "get_adapter",
]
