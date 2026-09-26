from unittest.mock import AsyncMock, MagicMock

import pytest

from nspanel_haui import async_reload_entry


@pytest.mark.asyncio
async def test_reload_uses_config_entry_manager_lifecycle():
    hass = MagicMock()
    hass.config_entries.async_reload = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "hub-entry"

    await async_reload_entry(hass, entry)

    hass.config_entries.async_reload.assert_awaited_once_with("hub-entry")
