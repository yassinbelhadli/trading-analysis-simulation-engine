"""Notification message templates — AR / EN / FR / ES.

Kept intentionally small for the 6.0 skeleton: one key per routed event type.
`get_message` mirrors the bot's `get_msg` fallback pattern (EN is the default).
"""
from __future__ import annotations

from typing import Any, Dict

MESSAGES: Dict[str, Dict[str, str]] = {
    "EN": {
        "trade_opened": "{icon} <b>{direction} {symbol}</b> opened at {price}",
        "trade_closed": "{icon} <b>{symbol}</b> closed \u2014 PnL <b>{pnl}</b>",
        "tp_hit": "\U0001f3af <b>TP hit \u2014 {symbol}</b> @ {price}",
        "sl_hit": "\U0001f6ab <b>SL hit \u2014 {symbol}</b> @ {price}",
        "news_countdown": "\u23f3 <b>{event}</b> in {minutes} min",
        "news_event": "\u26a0\ufe0f <b>{event}</b> upcoming ({impact})",
        "license_activated": "\u2705 <b>License activated</b> \u2014 your bot is ready",
        "license_expired": "\u26d4 <b>License expired</b> \u2014 trading has been paused",
        "system_info": "\u2139\ufe0f {message}",
        "error": "\u274c {message}",
        "health_warning": "\u26a0\ufe0f {message}",
        # Economic calendar
        "calendar_t60": "\u23f0 <b>\u26a0 {event}</b> in {minutes} min \u2014 T-60 protection active",
        "calendar_t30": "\u23f0 <b>\u26a0 {event}</b> in {minutes} min \u2014 prepare for volatility",
        "calendar_t5": "\U0001f534 <b>{event}</b> in {minutes} min \u2014 HIGH IMPACT",
        "calendar_released": "\U0001f4e5 <b>{event}</b> released: Actual={actual} | Forecast={forecast} | Previous={previous}{surprise_line}",
        "calendar_weekly": "\U0001f4c5 <b>Weekly Economic Calendar</b>\n{summary}",
        "calendar_data_unavailable": "\u26a0\ufe0f Calendar data unavailable \u2014 news protection may be degraded",
        # News-driven trade
        "news_driven_trade": "\U0001f6a8 <b>NEWS-DRIVEN TRADE</b>\n\n\U0001f1fa\U0001f1f8 <b>{event}</b>\nActual: {actual}\nForecast: {forecast}\nSurprise: {surprise}\n\n{icon} <b>{direction} {symbol}</b>\nNews context \u2713\n{setup_details}\n\nScore: {score}\n\nEntry: {entry}\nSL: {sl}\nTP1: {tp1}\nTP2: {tp2}",
    },
    "AR": {
        "trade_opened": "{icon} <b>{direction} {symbol}</b> \u0641\u062a\u062d \u0639\u0646\u062f {price}",
        "trade_closed": "{icon} <b>{symbol}</b> \u0623\u063a\u064a\u0644\u0642 \u2014 \u0627\u0644\u0631\u0628\u062d/\u0627\u0644\u062e\u0633\u0627\u0631\u0629 <b>{pnl}</b>",
        "tp_hit": "\U0001f3af <b>\u062a\u062d\u0642\u0642 \u0647\u062f\u0641 \u0627\u0644\u0631\u0628\u062d \u2014 {symbol}</b> \u0639\u0646\u062f {price}",
        "sl_hit": "\U0001f6ab <b>\u062a\u062d\u0642\u0642 \u0625\u064a\u0642\u0627\u0641 \u0627\u0644\u062e\u0633\u0627\u0631\u0629 \u2014 {symbol}</b> \u0639\u0646\u062f {price}",
        "news_countdown": "\u23f3 <b>{event}</b> \u0628\u0639\u062f {minutes} \u062f\u0642\u064a\u0642\u0629",
        "news_event": "\u26a0\ufe0f <b>{event}</b> \u0642\u0627\u062f\u0645 ({impact})",
        "license_activated": "\u2705 <b>\u062a\u0645 \u062a\u0641\u0639\u064a\u0644 \u0627\u0644\u062a\u0631\u062e\u064a\u0635</b> \u2014 \u0627\u0644\u0628\u0648\u062a \u062c\u0627\u0647\u0632",
        "license_expired": "\u26d4 <b>\u0627\u0646\u062a\u0647\u0649 \u0627\u0644\u062a\u0631\u062e\u064a\u0635</b> \u2014 \u062a\u0645 \u0625\u064a\u0642\u0627\u0641 \u0627\u0644\u062a\u062f\u0627\u0648\u0644",
        "system_info": "\u2139\ufe0f {message}",
        "error": "\u274c {message}",
        "health_warning": "\u26a0\ufe0f {message}",
        # Calendar
        "calendar_t60": "\u23f0 <b>\u26a0 {event}</b> \u0628\u0639\u062f {minutes} \u062f\u0642\u064a\u0642\u0629 \u2014 \u062d\u0645\u0627\u064a\u0629 T-60 \u0646\u0634\u0637\u0629",
        "calendar_t30": "\u23f0 <b>\u26a0 {event}</b> \u0628\u0639\u062f {minutes} \u062f\u0642\u064a\u0642\u0629 \u2014 \u0627\u0633\u062a\u0639\u062f \u0644\u0644\u062a\u0642\u0644\u0628\u0627\u062a",
        "calendar_t5": "\U0001f534 <b>{event}</b> \u0628\u0639\u062f {minutes} \u062f\u0642\u064a\u0642\u0629 \u2014 \u062a\u0623\u062b\u064a\u0631 \u0639\u0627\u0644\u064a",
        "calendar_released": "\U0001f4e5 <b>{event}</b> \u0635\u062f\u0631: \u0627\u0644\u0641\u0639\u0644\u064a={actual} | \u0627\u0644\u062a\u0648\u0642\u0639={forecast} | \u0627\u0644\u0633\u0627\u0628\u0642={previous}{surprise_line}",
        "calendar_weekly": "\U0001f4c5 <b>\u0627\u0644\u062a\u0642\u0648\u064a\u0645 \u0627\u0644\u0627\u0642\u062a\u0635\u0627\u062f\u064a \u0627\u0644\u0623\u0633\u0628\u0648\u0639\u064a</b>\n{summary}",
        "calendar_data_unavailable": "\u26a0\ufe0f \u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u062a\u0642\u0648\u064a\u0645 \u063a\u064a\u0631 \u0645\u062a\u0627\u062d\u0629 \u2014 \u062d\u0645\u0627\u064a\u0629 \u0627\u0644\u0623\u062e\u0628\u0627\u0631 \u0642\u062f \u062a\u062a\u0636\u0631\u0631",
    },
    "FR": {
        "trade_opened": "{icon} <b>{direction} {symbol}</b> ouvert \u00e0 {price}",
        "trade_closed": "{icon} <b>{symbol}</b> cl\u00f4tur\u00e9 \u2014 PnL <b>{pnl}</b>",
        "tp_hit": "\U0001f3af <b>TP atteint \u2014 {symbol}</b> @ {price}",
        "sl_hit": "\U0001f6ab <b>SL atteint \u2014 {symbol}</b> @ {price}",
        "news_countdown": "\u23f3 <b>{event}</b> dans {minutes} min",
        "news_event": "\u26a0\ufe0f <b>{event}</b> \u00e0 venir ({impact})",
        "license_activated": "\u2705 <b>Licence activ\u00e9e</b> \u2014 votre bot est pr\u00eat",
        "license_expired": "\u26d4 <b>Licence expir\u00e9e</b> \u2014 trading mis en pause",
        "system_info": "\u2139\ufe0f {message}",
        "error": "\u274c {message}",
        "health_warning": "\u26a0\ufe0f {message}",
        # Calendar
        "calendar_t60": "\u23f0 <b>\u26a0 {event}</b> dans {minutes} min \u2014 protection T-60 active",
        "calendar_t30": "\u23f0 <b>\u26a0 {event}</b> dans {minutes} min \u2014 pr\u00e9parez-vous \u00e0 la volatilit\u00e9",
        "calendar_t5": "\U0001f534 <b>{event}</b> dans {minutes} min \u2014 IMPACT \u00c9LEV\u00c9",
        "calendar_released": "\U0001f4e5 <b>{event}</b> publi\u00e9: Actuel={actual} | Pr\u00e9vu={forecast} | Pr\u00e9c\u00e9dent={previous}{surprise_line}",
        "calendar_weekly": "\U0001f4c5 <b>Calendrier \u00e9conomique hebdomadaire</b>\n{summary}",
        "calendar_data_unavailable": "\u26a0\ufe0f Donn\u00e9es du calendrier indisponibles \u2014 protection actualit\u00e9s d\u00e9grad\u00e9e",
    },
    "ES": {
        "trade_opened": "{icon} <b>{direction} {symbol}</b> abierto en {price}",
        "trade_closed": "{icon} <b>{symbol}</b> cerrado \u2014 PnL <b>{pnl}</b>",
        "tp_hit": "\U0001f3af <b>TP alcanzado \u2014 {symbol}</b> @ {price}",
        "sl_hit": "\U0001f6ab <b>SL alcanzado \u2014 {symbol}</b> @ {price}",
        "news_countdown": "\u23f3 <b>{event}</b> en {minutes} min",
        "news_event": "\u26a0\ufe0f <b>{event}</b> pr\u00f3ximo ({impact})",
        "license_activated": "\u2705 <b>Licencia activada</b> \u2014 tu bot est\u00e1 listo",
        "license_expired": "\u26d4 <b>Licencia expirada</b> \u2014 trading en pausa",
        "system_info": "\u2139\ufe0f {message}",
        "error": "\u274c {message}",
        "health_warning": "\u26a0\ufe0f {message}",
        # Calendar
        "calendar_t60": "\u23f0 <b>\u26a0 {event}</b> en {minutes} min \u2014 protecci\u00f3n T-60 activa",
        "calendar_t30": "\u23f0 <b>\u26a0 {event}</b> en {minutes} min \u2014 prep\u00e1rate para la volatilidad",
        "calendar_t5": "\U0001f534 <b>{event}</b> en {minutes} min \u2014 IMPACTO ALTO",
        "calendar_released": "\U0001f4e5 <b>{event}</b> publicado: Actual={actual} | Pron\u00f3stico={forecast} | Anterior={previous}{surprise_line}",
        "calendar_weekly": "\U0001f4c5 <b>Calendario Econ\u00f3mico Semanal</b>\n{summary}",
        "calendar_data_unavailable": "\u26a0\ufe0f Datos del calendario no disponibles \u2014 protecci\u00f3n de noticias puede estar degradada",
    },
}

# event_type -> message key
EVENT_KEYS = {
    "TRADE_OPENED": "trade_opened",
    "PAPER_TRADE_FILLED": "trade_opened",
    "TRADE_CLOSED": "trade_closed",
    "PARTIAL_CLOSE": "trade_closed",
    "TP_HIT": "tp_hit",
    "PAPER_TRADE_TP_HIT": "tp_hit",
    "SL_HIT": "sl_hit",
    "PAPER_TRADE_SL_HIT": "sl_hit",
    "NEWS_COUNTDOWN": "news_countdown",
    "NEWS_UPDATED": "news_event",
    "LICENSE_ACTIVATED": "license_activated",
    "LICENSE_EXPIRED": "license_expired",
    "SYSTEM_INFO": "system_info",
    "ERROR": "error",
    "HEALTH_WARNING": "health_warning",
    # Economic calendar events
    "CALENDAR_T60_ALERT": "calendar_t60",
    "CALENDAR_T30_ALERT": "calendar_t30",
    "CALENDAR_T5_ALERT": "calendar_t5",
    "ECONOMIC_EVENT_RELEASED": "calendar_released",
    "CALENDAR_WEEKLY_SUMMARY": "calendar_weekly",
    "CALENDAR_DATA_UNAVAILABLE": "calendar_data_unavailable",
    "NEWS_DRIVEN_TRADE": "news_driven_trade",
}

_ICONS = {
    "BUY": "\U0001f7e2",
    "SELL": "\U0001f534",
    "win": "\u2705",
    "loss": "\U0001f6ab",
}


def get_message(lang: str, key: str, **kwargs: Any) -> str:
    """Render a message in `lang` (falls back to EN), applying `{placeholder}`."""
    lang = (lang or "EN").upper()
    table = MESSAGES.get(lang, MESSAGES["EN"])
    template = table.get(key, MESSAGES["EN"].get(key, key))
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return template
    return template


def pnl_value(pnl: Any) -> str:
    try:
        val = float(pnl)
        return f"{'+' if val >= 0 else ''}{val:.2f}"
    except (TypeError, ValueError):
        return str(pnl or "0")
