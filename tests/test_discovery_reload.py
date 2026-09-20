from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# Import custom integration without installing Home Assistant in this host test env.
helpers = types.ModuleType("homeassistant.helpers")
config_validation = types.ModuleType("homeassistant.helpers.config_validation")
config_validation.empty_config_schema = lambda _domain: {}
helpers.config_validation = config_validation
homeassistant = types.ModuleType("homeassistant")
homeassistant.helpers = helpers
sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault("homeassistant.helpers.config_validation", config_validation)

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components"))
import nspanel_haui as haui  # noqa: E402


@pytest.fixture(autouse=True)
def clear_discovery_tasks():
    tasks = getattr(haui, "_DISCOVERY_TASKS", {})
    tasks.clear()
    yield
    for task in tasks.values():
        task.cancel()
    tasks.clear()


class FakeHass:
    def __init__(self) -> None:
        self.created_tasks: list[asyncio.Task] = []

    def async_create_task(self, coro, **_kwargs):
        task = asyncio.create_task(coro)
        self.created_tasks.append(task)
        return task


def test_discovery_registry_burst_runs_one_scan_per_hub(monkeypatch):
    hass = FakeHass()
    entry = SimpleNamespace(entry_id="hub-1")
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def scan(_hass, _entry):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()

    monkeypatch.setattr(haui, "_auto_add_unconfigured_devices", scan)

    async def scenario():
        first = haui._schedule_auto_add_unconfigured_devices(hass, entry)
        await started.wait()
        second = haui._schedule_auto_add_unconfigured_devices(hass, entry)

        assert first is second
        assert calls == 1

        release.set()
        await first

    asyncio.run(scenario())


def test_async_reload_uses_home_assistant_manager(monkeypatch):
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_reload=AsyncMock()),
    )
    entry = SimpleNamespace(entry_id="hub-1")
    unload = AsyncMock()
    setup = AsyncMock()
    monkeypatch.setattr(haui, "async_unload_entry", unload)
    monkeypatch.setattr(haui, "async_setup_entry", setup)

    asyncio.run(haui.async_reload_entry(hass, entry))

    hass.config_entries.async_reload.assert_awaited_once_with("hub-1")
    unload.assert_not_awaited()
    setup.assert_not_awaited()


def test_auto_add_combines_device_changes_into_one_update(monkeypatch):
    entry = SimpleNamespace(
        entry_id="hub-1",
        title="hub",
        data={"devices": [{"name": "existing", "enabled": False}]},
    )
    update_entry = MagicMock()
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_update_entry=update_entry),
    )
    discovered = types.ModuleType("nspanel_haui.esphome_helpers")
    discovered.discover_esphome_devices = AsyncMock(
        return_value=[
            {"name": "existing", "esphome_device_id": "device-1"},
            {"name": "new", "esphome_device_id": "device-2"},
        ]
    )
    monkeypatch.setitem(sys.modules, "nspanel_haui.esphome_helpers", discovered)

    asyncio.run(haui._auto_add_unconfigured_devices(hass, entry))

    update_entry.assert_called_once()
    devices = update_entry.call_args.kwargs["data"]["devices"]
    assert [(device["name"], device["enabled"]) for device in devices] == [
        ("existing", True),
        ("new", True),
    ]


def test_unload_cancels_discovery_before_platform_unload():
    entry = SimpleNamespace(entry_id="hub-1")

    async def scenario():
        discovery_task = asyncio.create_task(asyncio.sleep(3600))
        haui._DISCOVERY_TASKS[entry.entry_id] = discovery_task
        unload_platforms = AsyncMock()

        async def assert_cancelled(_entry, _platforms):
            assert entry.entry_id not in haui._DISCOVERY_TASKS
            assert discovery_task.cancelling() == 1

        unload_platforms.side_effect = assert_cancelled
        hass = SimpleNamespace(
            config_entries=SimpleNamespace(
                async_unload_platforms=unload_platforms,
            ),
            data={haui.DOMAIN: {entry.entry_id: {}}},
        )

        await haui.async_unload_entry(hass, entry)
        await asyncio.sleep(0)
        assert discovery_task.cancelled()

    asyncio.run(scenario())


def test_auto_add_does_not_directly_reload_entry(monkeypatch):
    entry = SimpleNamespace(
        entry_id="hub-1",
        title="hub",
        data={"devices": []},
    )
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_update_entry=MagicMock()),
    )
    discovered = types.ModuleType("nspanel_haui.esphome_helpers")
    discovered.discover_esphome_devices = AsyncMock(
        return_value=[{"name": "panel-1", "esphome_device_id": "device-1"}]
    )
    monkeypatch.setitem(sys.modules, "nspanel_haui.esphome_helpers", discovered)
    reload_entry = AsyncMock()
    monkeypatch.setattr(haui, "async_reload_entry", reload_entry)

    asyncio.run(haui._auto_add_unconfigured_devices(hass, entry))

    hass.config_entries.async_update_entry.assert_called_once()
    reload_entry.assert_not_awaited()
