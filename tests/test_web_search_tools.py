from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.tools.web_search_tools import SearchResult, TavilyWebSearchTool


def _make_context():
    plugin_context = MagicMock()
    plugin_context.get_config.return_value = {
        "provider_settings": {
            "websearch_tavily_key": ["test-key"],
        }
    }
    event = SimpleNamespace(unified_msg_origin="test-umo")
    agent_context = SimpleNamespace(event=event, context=plugin_context)
    return SimpleNamespace(context=agent_context)


@pytest.mark.asyncio
async def test_tavily_search_rejects_days_with_time_range(monkeypatch):
    tool = TavilyWebSearchTool()
    search_mock = AsyncMock()
    monkeypatch.setattr("astrbot.core.tools.web_search_tools._tavily_search", search_mock)

    with pytest.raises(ValueError, match="mutually exclusive"):
        await tool.call(
            _make_context(),
            query="latest S&P 500",
            topic="news",
            days=3,
            time_range="week",
        )

    search_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_tavily_search_rejects_days_with_explicit_dates(monkeypatch):
    tool = TavilyWebSearchTool()
    search_mock = AsyncMock()
    monkeypatch.setattr("astrbot.core.tools.web_search_tools._tavily_search", search_mock)

    with pytest.raises(ValueError, match="mutually exclusive"):
        await tool.call(
            _make_context(),
            query="latest S&P 500",
            topic="news",
            days=3,
            start_date="2026-03-01",
            end_date="2026-03-27",
        )

    search_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_tavily_search_rejects_time_range_with_explicit_dates(monkeypatch):
    tool = TavilyWebSearchTool()
    search_mock = AsyncMock()
    monkeypatch.setattr("astrbot.core.tools.web_search_tools._tavily_search", search_mock)

    with pytest.raises(ValueError, match="mutually exclusive"):
        await tool.call(
            _make_context(),
            query="latest S&P 500",
            topic="general",
            time_range="month",
            start_date="2026-03-01",
            end_date="2026-03-27",
        )

    search_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_tavily_search_news_time_range_does_not_send_implicit_days(monkeypatch):
    tool = TavilyWebSearchTool()
    search_mock = AsyncMock(
        return_value=[
            SearchResult(
                title="S&P 500",
                url="https://example.com/sp500",
                snippet="Latest market update",
            )
        ]
    )
    monkeypatch.setattr("astrbot.core.tools.web_search_tools._tavily_search", search_mock)

    await tool.call(
        _make_context(),
        query="latest S&P 500",
        topic="news",
        time_range="week",
    )

    search_mock.assert_awaited_once()
    payload = search_mock.await_args.args[1]
    assert payload["topic"] == "news"
    assert payload["time_range"] == "week"
    assert "days" not in payload
