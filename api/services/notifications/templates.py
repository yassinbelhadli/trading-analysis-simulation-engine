"""Template rendering — turns an event payload into per-channel text (i18n)."""
from __future__ import annotations

from typing import Any

from api.services.notifications.messages import EVENT_KEYS, get_message, pnl_value


def _fmt(value: Any, ndigits: int = 2) -> str:
    try:
        return f"{float(value):.{ndigits}f}"
    except (TypeError, ValueError):
        return str(value or "")


def _direction_icon(payload: dict) -> str:
    direction = str(payload.get("direction", "")).upper()
    if direction == "SELL":
        return "\U0001f534"
    if direction == "BUY":
        return "\U0001f7e2"
    return "\U0001f539"


def _win_loss_icon(payload: dict) -> str:
    pnl = payload.get("realized_pnl", payload.get("pnl"))
    try:
        if float(pnl or 0) >= 0:
            return "\u2705"
    except (TypeError, ValueError):
        pass
    return "\U0001f6ab"


def render_telegram(event_type: str, payload: dict, fallback: str = "", lang: str = "EN") -> str:
    """Single text message for Telegram (HTML). Falls back to the raw message
    for events that have no dedicated template yet."""
    key = EVENT_KEYS.get(event_type)
    if key is None:
        return fallback or event_type
    if event_type == "TRADE_OPENED" or event_type == "PAPER_TRADE_FILLED":
        return get_message(lang, key, icon=_direction_icon(payload),
                           direction=str(payload.get("direction", "BUY")),
                           symbol=str(payload.get("symbol", "")),
                           price=_fmt(payload.get("price") or payload.get("entry") or 0))
    if event_type == "TRADE_CLOSED" or event_type == "PARTIAL_CLOSE":
        return get_message(lang, key, icon=_win_loss_icon(payload),
                           symbol=str(payload.get("symbol", "")),
                           pnl=pnl_value(payload.get("realized_pnl", payload.get("pnl"))))
    if event_type in ("TP_HIT", "PAPER_TRADE_TP_HIT", "SL_HIT", "PAPER_TRADE_SL_HIT"):
        return get_message(lang, key, symbol=str(payload.get("symbol", "")),
                           price=_fmt(payload.get("price") or payload.get("exit_price") or 0))
    if event_type == "NEWS_COUNTDOWN":
        return get_message(lang, key, event=str(payload.get("event", "Event")),
                           minutes=str(payload.get("minutes_remaining", 0)))
    if event_type == "NEWS_UPDATED":
        return get_message(lang, key, event=str(payload.get("event", payload.get("name", "Event"))),
                           impact=str(payload.get("impact", "MEDIUM")).upper())
    if event_type in ("LICENSE_ACTIVATED", "LICENSE_EXPIRED"):
        return get_message(lang, key)
    # Calendar events with rich formatting
    if event_type in ("CALENDAR_T60_ALERT", "CALENDAR_T30_ALERT", "CALENDAR_T5_ALERT"):
        return _render_calendar_alert(event_type, payload, lang)
    if event_type == "ECONOMIC_EVENT_RELEASED":
        return _render_calendar_released(payload, lang)
    if event_type == "CALENDAR_WEEKLY_SUMMARY":
        return _render_calendar_weekly(payload, lang)
    if event_type == "NEWS_DRIVEN_TRADE":
        return _render_news_driven_trade(payload, lang)
    return get_message(lang, key, message=fallback or "System notification")


def _render_calendar_alert(event_type: str, payload: dict, lang: str = "EN") -> str:
    """Render T-60 / T-30 / T-5 calendar alert with rich formatting."""
    title = payload.get("event_title", "Event")
    impact = payload.get("impact", "MEDIUM").upper()
    minutes = int(payload.get("minutes_until", 0))
    symbols = payload.get("relevant_symbols", [])
    forecast = payload.get("forecast")
    previous = payload.get("previous")

    # Impact icon
    impact_icon = "\U0001f534" if impact == "HIGH" else "\U0001f7e1" if impact == "MEDIUM" else "\U0001f7e2"

    # Schedule time (ET)
    scheduled = payload.get("scheduled_at_utc", "")
    time_str = ""
    if scheduled:
        try:
            from datetime import datetime as dt
            utc_dt = dt.fromisoformat(scheduled.replace("Z", "+00:00"))
            from zoneinfo import ZoneInfo
            et_dt = utc_dt.astimezone(ZoneInfo("America/New_York"))
            time_str = et_dt.strftime("%H:%M")
        except Exception:
            time_str = scheduled[:16]

    # Symbols line
    symbols_line = " \u2022 ".join(symbols) if symbols else "N/A"

    # Forecast/Previous
    forecast_str = _fmt(forecast) if forecast is not None else "\u2014"
    previous_str = _fmt(previous) if previous is not None else "\u2014"

    if event_type == "CALENDAR_T60_ALERT":
        header = "\u23f0 <b>\u26a0 US NEWS IN %d MIN</b>" % minutes
        sub = "T-60 protection active"
    elif event_type == "CALENDAR_T30_ALERT":
        header = "\u23f0 <b>\u26a0 US NEWS IN %d MIN</b>" % minutes
        sub = "Prepare for volatility"
    else:  # T-5
        header = "\U0001f534 <b>US NEWS IN %d MIN</b>" % minutes
        sub = "News release imminent"

    lines = [
        header,
        "",
        "\U0001f1fa\U0001f1f8 <b>%s</b>" % title,
        "%s %s IMPACT" % (impact_icon, impact),
        "",
        "Time: %s ET" % time_str if time_str else "",
        "Forecast: %s" % forecast_str,
        "Previous: %s" % previous_str,
        "",
        "Markets: %s" % symbols_line,
        "",
        "\u26a0\ufe0f New entries restricted.",
    ]
    return "\n".join(line for line in lines if line is not None)


def _render_calendar_released(payload: dict, lang: str = "EN") -> str:
    """Render ECONOMIC_EVENT_RELEASED with actual/forecast/surprise."""
    title = payload.get("event_title", "Event")
    actual = payload.get("actual")
    forecast = payload.get("forecast")
    previous = payload.get("previous")
    surprise = payload.get("surprise")

    actual_str = _fmt(actual) if actual is not None else "\u2014"
    forecast_str = _fmt(forecast) if forecast is not None else "\u2014"
    previous_str = _fmt(previous) if previous is not None else "\u2014"

    surprise_line = ""
    if surprise is not None:
        sign = "+" if surprise >= 0 else ""
        surprise_line = "\nSurprise: %s%s" % (sign, _fmt(surprise))

    lines = [
        "\U0001f4e5 <b>USD NEWS RELEASED</b>",
        "",
        "\U0001f1fa\U0001f1f8 <b>%s</b>" % title,
        "",
        "Actual: %s" % actual_str,
        "Forecast: %s" % forecast_str,
        "Previous: %s" % previous_str,
    ]
    if surprise_line:
        lines.append(surprise_line)
    return "\n".join(lines)


def _render_calendar_weekly(payload: dict, lang: str = "EN") -> str:
    """Render CALENDAR_WEEKLY_SUMMARY grouped by day."""
    from datetime import datetime as dt

    events = payload.get("events", [])
    week_start = payload.get("week_start", "")
    week_end = payload.get("week_end", "")

    lines = [
        "\U0001f1fa\U0001f1f8 <b>US ECONOMIC CALENDAR</b>",
    ]
    if week_start and week_end:
        lines.append("Week: %s \u2192 %s" % (week_start[:10], week_end[:10]))
    lines.append("")

    # Group by day
    days = {}
    for ev in events:
        scheduled = ev.get("scheduled_at_utc", "")
        try:
            utc_dt = dt.fromisoformat(scheduled.replace("Z", "+00:00"))
            from zoneinfo import ZoneInfo
            et_dt = utc_dt.astimezone(ZoneInfo("America/New_York"))
            day_name = et_dt.strftime("%A").upper()
            time_str = et_dt.strftime("%H:%M")
        except Exception:
            day_name = "OTHER"
            time_str = scheduled[:5] if scheduled else "??"

        if day_name not in days:
            days[day_name] = []
        impact = ev.get("impact", "LOW").upper()
        title = ev.get("title", "")
        impact_icon = "\U0001f534" if impact == "HIGH" else "\U0001f7e1" if impact == "MEDIUM" else ""
        days[day_name].append("\u2022 %s \u2014 %s %s" % (time_str, title, impact_icon))

    for day in ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]:
        if day in days:
            lines.append("<b>%s</b>" % day)
            lines.extend(days[day])
            lines.append("")

    return "\n".join(lines)


def _render_news_driven_trade(payload: dict, lang: str = "EN") -> str:
    """Render NEWS_DRIVEN_TRADE with full news context + strategy confirmation."""
    event = payload.get("event_title", "Event")
    actual = payload.get("actual")
    forecast = payload.get("forecast")
    surprise = payload.get("surprise")
    direction = str(payload.get("direction", "BUY")).upper()
    symbol = payload.get("symbol", "")
    score = payload.get("score", 0)
    entry = payload.get("entry", "")
    sl = payload.get("sl", "")
    tp1 = payload.get("tp1", "")
    tp2 = payload.get("tp2", "")

    # Direction icon
    icon = "\U0001f534" if direction == "SELL" else "\U0001f7e2"

    # Format values
    actual_str = _fmt(actual) if actual is not None else "\u2014"
    forecast_str = _fmt(forecast) if forecast is not None else "\u2014"
    surprise_str = "\u2014"
    if surprise is not None:
        sign = "+" if surprise >= 0 else ""
        surprise_str = "%s%s" % (sign, _fmt(surprise))

    # Setup details from payload
    setup = payload.get("setup_details", {})
    details_lines = []
    if isinstance(setup, dict):
        for k, v in setup.items():
            if v is True:
                details_lines.append("%s \u2713" % k)
            elif v:
                details_lines.append("%s: %s" % (k, v))
    setup_details = "\n".join(details_lines) if details_lines else "News context \u2713"

    lines = [
        "\U0001f6a8 <b>NEWS-DRIVEN TRADE</b>",
        "",
        "\U0001f1fa\U0001f1f8 <b>%s</b>" % event,
        "Actual: %s" % actual_str,
        "Forecast: %s" % forecast_str,
        "Surprise: %s" % surprise_str,
        "",
        "%s <b>%s %s</b>" % (icon, direction, symbol),
        setup_details,
        "",
        "Score: %s" % score,
        "",
        "Entry: %s" % entry,
        "SL: %s" % sl,
        "TP1: %s" % tp1,
        "TP2: %s" % tp2,
    ]
    return "\n".join(lines)


def render_email_subject(event_type: str, lang: str = "EN") -> str:
    titles = {
        "LICENSE_ACTIVATED": "License Activated — ICT EA Pro",
        "LICENSE_EXPIRED": "License Expired — ICT EA Pro",
        "LICENSE_WARNING": "License Expiring — ICT EA Pro",
    }
    return titles.get(event_type, "Notification — ICT EA Pro")


def render_email_body(event_type: str, payload: dict, fallback: str = "", lang: str = "EN") -> str:
    if event_type in ("LICENSE_ACTIVATED", "LICENSE_EXPIRED", "LICENSE_WARNING"):
        lines = [
            f"<h2 style='color:#3b82f6;margin:0 0 12px'>{render_email_subject(event_type, lang)}</h2>",
            "<p>Hello,</p>",
            "<p>" + render_telegram(event_type, payload, fallback, lang) + "</p>",
            "<p style='color:#94a3b8;font-size:12px'>If you need any help, our support team is here for you.</p>",
        ]
        return "\n".join(lines)
    return f"<p>{render_telegram(event_type, payload, fallback, lang)}</p>"
