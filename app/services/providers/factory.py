from __future__ import annotations

from app.config import Settings
from app.services.providers.interfaces import MacroCalendarProvider
from app.services.providers.static_macro_calendar import StaticMacroCalendarProvider


class ProviderConfigurationError(RuntimeError):
    pass


def build_macro_calendar_provider(settings: Settings) -> MacroCalendarProvider:
    if settings.macro_calendar_path is None or not settings.macro_calendar_path.strip():
        raise ProviderConfigurationError("MACRO_CALENDAR_PATH is required for static macro calendar provider")

    return StaticMacroCalendarProvider(settings.macro_calendar_path)
