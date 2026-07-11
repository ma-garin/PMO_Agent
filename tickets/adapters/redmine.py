from __future__ import annotations

from datetime import date, datetime

import requests

from .base import NormalizedTicket, TicketAdapter, TicketSourceConnectionError

REQUEST_TIMEOUT_SECONDS = 15
PAGE_SIZE = 100

CLOSED_STATUS_NAMES = {"closed", "resolved", "rejected", "完了", "却下", "終了"}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _is_done(status_name: str, done_ratio: int) -> bool:
    if done_ratio == 100:
        return True
    return status_name.strip().lower() in CLOSED_STATUS_NAMES


class RedmineAdapter(TicketAdapter):
    def fetch_tickets(self, source) -> list[NormalizedTicket]:
        url = f"{source.base_url.rstrip('/')}/issues.json"
        params = {
            "project_id": source.project_key,
            "status_id": "*",
            "limit": PAGE_SIZE,
            "sort": "updated_on:desc",
        }
        headers = {"X-Redmine-API-Key": source.api_token}
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TicketSourceConnectionError(str(exc)) from exc

        payload = response.json()
        return [self._normalize(issue, source) for issue in payload.get("issues", [])]

    def _normalize(self, issue: dict, source) -> NormalizedTicket:
        status = issue.get("status") or {}
        priority = issue.get("priority") or {}
        assigned_to = issue.get("assigned_to") or {}
        author = issue.get("author") or {}
        tracker = issue.get("tracker") or {}
        status_name = status.get("name", "")

        return NormalizedTicket(
            external_id=str(issue["id"]),
            external_url=f"{source.base_url.rstrip('/')}/issues/{issue['id']}",
            summary=issue.get("subject", ""),
            description=issue.get("description") or "",
            status=status_name,
            is_done=_is_done(status_name, issue.get("done_ratio", 0)),
            priority=priority.get("name", ""),
            ticket_type=tracker.get("name", ""),
            assignee_name=assigned_to.get("name", ""),
            reporter_name=author.get("name", ""),
            due_date=_parse_date(issue.get("due_date")),
            source_created_at=_parse_datetime(issue.get("created_on")),
            source_updated_at=_parse_datetime(issue.get("updated_on")),
            closed_at=_parse_datetime(issue.get("closed_on")),
            raw_payload=issue,
        )
