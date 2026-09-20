from __future__ import annotations

import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock


def _install_dependency_stubs() -> None:
    config_validation = MagicMock()
    config_validation.empty_config_schema = MagicMock(return_value=MagicMock(spec_set=dict))

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = ["homeassistant.helpers"]
    helpers.config_validation = config_validation

    ha = types.ModuleType("homeassistant")
    ha.helpers = helpers
    for name, stub in {
        "homeassistant": ha,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.config_validation": config_validation,
        "homeassistant.const": MagicMock(),
        "homeassistant.core": MagicMock(),
        "homeassistant.components": MagicMock(),
        "homeassistant.loader": MagicMock(),
    }.items():
        sys.modules.setdefault(name, stub)

    dateutil = types.ModuleType("dateutil")
    dateutil.__path__ = ["dateutil"]
    parser = types.ModuleType("dateutil.parser")
    parser.parse = lambda _value, **_kwargs: datetime.now(UTC)
    sys.modules.setdefault("dateutil", dateutil)
    sys.modules.setdefault("dateutil.parser", parser)


_install_dependency_stubs()
CUSTOM_COMPONENTS = Path(__file__).parents[1] / "custom_components"
sys.path.insert(0, str(CUSTOM_COMPONENTS))

from nspanel_haui.haui.abstract.haui_event import HAUIEvent  # noqa: E402
from nspanel_haui.haui.device import HAUIDevice  # noqa: E402
from nspanel_haui.haui.mapping.const import ESPEvent  # noqa: E402
from nspanel_haui.haui.page.blank import BlankPage  # noqa: E402


class DummyPanel:
    def get(self, key: str, default=None):
        return "sys_blank" if key == "key" else default


class DummyNavigation:
    def __init__(self) -> None:
        self.panel = DummyPanel()
        self._sleep_panel_active = True
        self.exit_calls: list[dict] = []

    def exit_sleep_to_prev_or_home(self, config: dict) -> None:
        self.exit_calls.append(config)


class DummyApp:
    def __init__(self) -> None:
        self.controller = {"navigation": DummyNavigation()}

    def log(self, *_args, **_kwargs) -> None:
        pass


def _sleeping_device() -> tuple[HAUIDevice, DummyNavigation]:
    app = DummyApp()
    device = HAUIDevice(
        app,
        {
            "name": "panel",
            "home_panel": "home",
            "sleep_panel": "sys_blank",
            "wakeup_panel": "",
        },
    )
    return device, app.controller["navigation"]


def test_blank_component_then_first_touch_exits_sleep_without_action() -> None:
    device, navigation = _sleeping_device()
    device.woke_up = True

    class BlankPageSpy:
        def __init__(self) -> None:
            self.logs: list[str] = []

        def log(self, message: str) -> None:
            self.logs.append(message)

    blank = BlankPageSpy()
    component_event = HAUIEvent(ESPEvent.COMPONENT, "1,1,1")

    BlankPage.callback_blank(blank, component_event, (), 1)
    device.process_event(component_event)
    assert navigation.exit_calls == []
    assert blank.logs == ["Blank callback"]

    device.process_event(HAUIEvent(ESPEvent.TOUCH_START, "1"))

    assert navigation.exit_calls == [device.config]
    assert device.woke_up is False


def test_touch_outside_sleep_or_wakeup_state_does_not_navigate() -> None:
    device, navigation = _sleeping_device()
    navigation._sleep_panel_active = False
    device.woke_up = True

    device.process_event(HAUIEvent(ESPEvent.TOUCH_START, "1"))

    assert navigation.exit_calls == []
    assert device.woke_up is True
