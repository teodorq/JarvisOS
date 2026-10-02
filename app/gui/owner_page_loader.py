from __future__ import annotations

from typing import Any


COMMAND_PAGES = frozenset({
    "operations", "release", "commercial", "assistant", "intelligence",
    "productivity", "stability", "assistant_v12", "online",
})


def ensure_owner_page(window: Any, page_name: str) -> Any:
    name = str(page_name or "console")
    loaded = getattr(window, "_loaded_owner_pages", set())
    if name in loaded or name not in getattr(window, "pages", {}):
        return window.pages.get(name)
    page = _build_page(window, name)
    if page is None:
        return window.pages.get(name)
    placeholder = window.pages[name]
    index = window.stack.indexOf(placeholder)
    window.stack.removeWidget(placeholder)
    placeholder.deleteLater()
    window.stack.insertWidget(max(0, index), page)
    attribute = "assistant_v12_page" if name == "assistant_v12" else f"{name}_page"
    setattr(window, attribute, page)
    window.pages[name] = page
    loaded.add(name)
    window._loaded_owner_pages = loaded
    if name in COMMAND_PAGES:
        page.command_requested.connect(
            lambda command: (
                window.console_page.prepare_command(command),
                window._show_page("console"),
            )
        )
    elif name == "platform":
        page.configuration_changed.connect(
            lambda: (
                setattr(window, "business_config", window.config_store.ensure()),
                window._apply_runtime_config(),
            )
        )
    return page


def _build_page(window: Any, name: str) -> Any:
    if name == "platform":
        from app.gui.business_platform_page import BusinessPlatformPage
        return BusinessPlatformPage(window.business_service)
    if name == "operations":
        from app.gui.business_operations_page import BusinessOperationsPage
        return BusinessOperationsPage(window.business_service)
    if name == "release":
        from app.gui.business_release_page import BusinessReleasePage
        return BusinessReleasePage(window.business_service)
    if name == "commercial":
        from app.gui.business_commercial_page import BusinessCommercialPage
        return BusinessCommercialPage(window.business_service)
    if name == "assistant":
        from app.gui.assistant_productivity_page import AssistantProductivityPage
        return AssistantProductivityPage(window.assistant)
    if name == "intelligence":
        from app.gui.intelligence_center_page import IntelligenceCenterPage
        return IntelligenceCenterPage(window.assistant.intelligence)
    if name == "productivity":
        from app.gui.productivity_center_page import ProductivityCenterPage
        return ProductivityCenterPage(window.assistant.productivity)
    if name == "stability":
        from app.gui.stability_beta_page import StabilityBetaPage
        return StabilityBetaPage(window.assistant.stability)
    if name == "forex":
        from app.gui.forex_paper_page import ForexPaperPage
        return ForexPaperPage(
            window.assistant.trading.forex_dashboard,
            activity=window.assistant.trading.forex_activity,
        )
    if name == "assistant_v12":
        from app.gui.assistant_v12_page import AssistantV12Page
        return AssistantV12Page(window.assistant.assistant_v12)
    if name == "online":
        from app.gui.online_assistant_page import OnlineAssistantPage
        return OnlineAssistantPage(window.assistant.online)
    return None
