from __future__ import annotations

from datetime import date, datetime

import requests

from .base import (
    NormalizedTicket,
    StatusTransitionEntry,
    TicketAdapter,
    TicketSourceConnectionError,
)

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
    def __init__(self) -> None:
        self._status_map_cache: dict[str, str] | None = None

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

    def fetch_status_history(self, source, ticket) -> list[StatusTransitionEntry]:
        status_map = self._get_status_map(source)
        url = f"{source.base_url.rstrip('/')}/issues/{ticket.external_id}.json"
        headers = {"X-Redmine-API-Key": source.api_token}
        try:
            response = requests.get(
                url,
                params={"include": "journals"},
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TicketSourceConnectionError(str(exc)) from exc

        payload = response.json()
        journals = payload.get("issue", {}).get("journals", [])
        entries: list[StatusTransitionEntry] = []
        for journal in journals:
            occurred_at = _parse_datetime(journal.get("created_on"))
            if occurred_at is None:
                continue
            for detail in journal.get("details", []):
                if detail.get("name") != "status_id":
                    continue
                old_id = str(detail.get("old_value") or "")
                new_id = str(detail.get("new_value") or "")
                entries.append(
                    StatusTransitionEntry(
                        from_status=status_map.get(old_id, old_id),
                        to_status=status_map.get(new_id, new_id),
                        occurred_at=occurred_at,
                    )
                )
        return entries

    def _get_status_map(self, source) -> dict[str, str]:
        if self._status_map_cache is None:
            url = f"{source.base_url.rstrip('/')}/statuses.json"
            headers = {"X-Redmine-API-Key": source.api_token}
            try:
                response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise TicketSourceConnectionError(str(exc)) from exc
            self._status_map_cache = {
                str(s["id"]): s["name"] for s in response.json().get("issue_statuses", [])
            }
        return self._status_map_cache

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
