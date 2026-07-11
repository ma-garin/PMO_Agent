import calendar
from datetime import date

from tickets.models import Ticket


def month_grid(engagement, year: int, month: int) -> list[list[dict]]:
    """月曜始まりの週配列を返す。各日は date/当月フラグ/その日が期限のチケット一覧を持つ。"""
    cal = calendar.Calendar(firstweekday=0)
    month_dates = list(cal.itermonthdates(year, month))

    due_tickets = Ticket.objects.filter(
        source__engagement=engagement,
        due_date__year=year,
        due_date__month=month,
    ).exclude(is_done=True)
    tickets_by_date: dict[date, list[Ticket]] = {}
    for ticket in due_tickets:
        tickets_by_date.setdefault(ticket.due_date, []).append(ticket)

    # 前後月にはみ出す日にも期限チケットがある可能性があるため、月全体でも拾っておく
    spillover_tickets = Ticket.objects.filter(
        source__engagement=engagement, due_date__in=month_dates
    ).exclude(is_done=True)
    for ticket in spillover_tickets:
        if ticket.due_date not in tickets_by_date:
            tickets_by_date.setdefault(ticket.due_date, []).append(ticket)

    weeks: list[list[dict]] = []
    week: list[dict] = []
    for day in month_dates:
        week.append(
            {
                "date": day,
                "in_month": day.month == month,
                "tickets": tickets_by_date.get(day, []),
            }
        )
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        weeks.append(week)
    return weeks
