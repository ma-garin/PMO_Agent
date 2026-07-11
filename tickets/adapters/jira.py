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


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


class JiraAdapter(TicketAdapter):
    def fetch_tickets(self, source) -> list[NormalizedTicket]:
        url = f"{source.base_url.rstrip('/')}/rest/api/3/search"
        params = {
            "jql": f"project = {source.project_key} ORDER BY updated DESC",
            "maxResults": PAGE_SIZE,
            "fields": "summary,status,priority,assignee,reporter,duedate,"
            "created,updated,resolutiondate,issuetype,description",
        }
        try:
            response = requests.get(
                url,
                params=params,
                auth=(source.username, source.api_token),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TicketSourceConnectionError(str(exc)) from exc

        payload = response.json()
        return [self._normalize(issue, source) for issue in payload.get("issues", [])]

    def fetch_status_history(self, source, ticket) -> list[StatusTransitionEntry]:
        url = f"{source.base_url.rstrip('/')}/rest/api/3/issue/{ticket.external_id}/changelog"
        start_at = 0
        entries: list[StatusTransitionEntry] = []

        while True:
            try:
                response = requests.get(
                    url,
                    params={"startAt": start_at, "maxResults": PAGE_SIZE},
                    auth=(source.username, source.api_token),
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                raise TicketSourceConnectionError(str(exc)) from exc

            payload = response.json()
            values = payload.get("values", [])
            for entry in values:
                occurred_at = _parse_datetime(entry.get("created"))
                if occurred_at is None:
                    continue
                for item in entry.get("items", []):
                    if item.get("field") != "status":
                        continue
                    entries.append(
                        StatusTransitionEntry(
                            from_status=item.get("fromString") or "",
                            to_status=item.get("toString") or "",
                            occurred_at=occurred_at,
                        )
                    )

            start_at += len(values)
            if payload.get("isLast", True) or not values:
                break

        return entries

    def _normalize(self, issue: dict, source) -> NormalizedTicket:
        fields = issue.get("fields", {})
        status = fields.get("status") or {}
        priority = fields.get("priority") or {}
        assignee = fields.get("assignee") or {}
        reporter = fields.get("reporter") or {}
        issuetype = fields.get("issuetype") or {}
        status_category = (status.get("statusCategory") or {}).get("key", "")
        description = fields.get("description")
        # JIRA API v3はdescriptionをADF(構造化JSON)で返すため、プレーンテキストの場合のみ格納する
        description_text = description if isinstance(description, str) else ""

        return NormalizedTicket(
            external_id=issue["key"],
            external_url=f"{source.base_url.rstrip('/')}/browse/{issue['key']}",
            summary=fields.get("summary", ""),
            description=description_text,
            status=status.get("name", ""),
            is_done=status_category == "done",
            priority=priority.get("name", ""),
            ticket_type=issuetype.get("name", ""),
            assignee_name=assignee.get("displayName", ""),
            reporter_name=reporter.get("displayName", ""),
            due_date=_parse_date(fields.get("duedate")),
            source_created_at=_parse_datetime(fields.get("created")),
            source_updated_at=_parse_datetime(fields.get("updated")),
            closed_at=_parse_datetime(fields.get("resolutiondate")),
            raw_payload=issue,
        )
