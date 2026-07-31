"""万家乐开关平台。"""
from __future__ import annotations

from typing import Any, List

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ._entity import WanjialeEntity
from .api import (
    WanjialeApi,
    WanjialeBoiler,
    WanjialeDevice,
    WanjialeDisinfect,
    WanjialeStove,
    WanjialeWaterHeater,
)
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    api: WanjialeApi = entry_data["api"]
    coordinator = entry_data["coordinator"]

    devices: List[Any] = [
        WanjialeSwitchEntity(dev, coordinator)
        for dev in api.devices
        if isinstance(dev, (WanjialeStove, WanjialeDisinfect))
    ]
    # 热水器待机开关 + 增压开关
    for dev in api.devices:
        if isinstance(dev, WanjialeWaterHeater):
            devices.append(WanjialePowerSwitch(dev, coordinator))
            devices.append(WanjialeBoostSwitch(dev, coordinator))
    # 壁挂炉开关：主电源 / 即热 / 抑菌（供暖开关由 climate 实体控制）
    for dev in api.devices:
        if isinstance(dev, WanjialeBoiler):
            devices.append(WanjialeBoilerSwitch(
                dev, coordinator, "is_power_on", "set_power", "电源", "mdi:power",
            ))
            devices.append(WanjialeBoilerSwitch(
                dev, coordinator, "is_instant_heat", "set_instant_heat", "即热", "mdi:flash",
            ))
            devices.append(WanjialeBoilerSwitch(
                dev, coordinator, "is_antibacterial", "set_antibacterial", "抑菌", "mdi:bacteria",
            ))
    async_add_entities(devices, True)


class WanjialeSwitchEntity(WanjialeEntity, SwitchEntity):
    """通用开关实体（灶具/消毒柜）。"""

    def __init__(self, device: WanjialeDevice, coordinator) -> None:
        super().__init__(device, coordinator)
        self._attr_name = f"{device.name} 开关"

    @property
    def unique_id(self) -> str:
        return f"{self._device.unique_id()}-switch"

    @property
    def is_on(self) -> bool:
        return bool(getattr(self._device, "is_power_on", False))

    def turn_on(self, **kwargs: Any) -> None:
        self._device.turn_on()

    def turn_off(self, **kwargs: Any) -> None:
        self._device.turn_off()


class WanjialePowerSwitch(WanjialeEntity, SwitchEntity):
    """热水器待机开关。

    对应 Java PostMessage dvid="4" + opt 消息。
    dwtype=2 开关型：0=关机, 1=开机。
    """

    _wh: WanjialeWaterHeater
    _attr_icon = "mdi:power"

    def __init__(self, device: WanjialeWaterHeater, coordinator) -> None:
        super().__init__(device, coordinator)
        self._wh = device

    @property
    def name(self) -> str:
        # return f"{self._device.name} 电源"
        return f"电源"

    @property
    def unique_id(self) -> str:
        return f"{self._device.unique_id()}-power"

    @property
    def is_on(self) -> bool:
        return bool(self._wh.is_power_on)

    def turn_on(self, **kwargs: Any) -> None:
        self._wh.turn_on()
        self.schedule_update_ha_state()
        self._request_refresh_soon()

    def turn_off(self, **kwargs: Any) -> None:
        self._wh.turn_off()
        self.schedule_update_ha_state()
        self._request_refresh_soon()


class WanjialeBoostSwitch(WanjialeEntity, SwitchEntity):
    """热水器增压开关。

    对应 Java PostMessage dvid="1"=7 (OP_BOOST) + 编码值。
    dwtype=2 开关型：0=关, 1=开。
    状态读取 DVID "20" bit0-1。
    """

    _wh: WanjialeWaterHeater
    _attr_icon = "mdi:water-pump"

    def __init__(self, device: WanjialeWaterHeater, coordinator) -> None:
        super().__init__(device, coordinator)
        self._wh = device

    @property
    def name(self) -> str:
        return "增压"

    @property
    def unique_id(self) -> str:
        return f"{self._device.unique_id()}-boost"

    @property
    def is_on(self) -> bool:
        return bool(self._wh.is_boost)

    def turn_on(self, **kwargs: Any) -> None:
        self._wh.set_boost(True)
        self.schedule_update_ha_state()
        self._request_refresh_soon()

    def turn_off(self, **kwargs: Any) -> None:
        self._wh.set_boost(False)
        self.schedule_update_ha_state()
        self._request_refresh_soon()


class WanjialeBoilerSwitch(WanjialeEntity, SwitchEntity):
    """壁挂炉通用开关实体。

    通过属性名 + setter 方法名参数化，复用于电源/即热/抑菌开关。
      - state_attr: 读取状态的设备属性名（如 "is_power_on"）
      - setter:     控制开关的设备方法名（如 "set_power"）
    """

    def __init__(
        self,
        device: WanjialeBoiler,
        coordinator,
        state_attr: str,
        setter: str,
        label: str,
        icon: str,
    ) -> None:
        super().__init__(device, coordinator)
        self._boiler = device
        self._state_attr = state_attr
        self._setter = setter
        self._label = label
        self._attr_icon = icon

    @property
    def name(self) -> str:
        return self._label

    @property
    def unique_id(self) -> str:
        return f"{self._device.unique_id()}-{self._label}"

    @property
    def is_on(self) -> bool:
        return bool(getattr(self._boiler, self._state_attr, False))

    def turn_on(self, **kwargs: Any) -> None:
        getattr(self._boiler, self._setter)(True)
        self.schedule_update_ha_state()
        self._request_refresh_soon()

    def turn_off(self, **kwargs: Any) -> None:
        getattr(self._boiler, self._setter)(False)
        self.schedule_update_ha_state()
        self._request_refresh_soon()
