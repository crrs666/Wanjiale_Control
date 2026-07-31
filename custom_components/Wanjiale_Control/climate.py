"""万家乐壁挂炉采暖实体平台。"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ._entity import WanjialeEntity
from .api import WanjialeApi, WanjialeBoiler
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    api: WanjialeApi = entry_data["api"]
    coordinator = entry_data["coordinator"]

    devices: List[Any] = [
        WanjialeBoilerClimateEntity(dev, coordinator)
        for dev in api.devices
        if isinstance(dev, WanjialeBoiler)
    ]
    _LOGGER.info("创建 %d 个壁挂炉采暖实体: %s", len(devices), [d.name for d in devices])
    async_add_entities(devices, True)


class WanjialeBoilerClimateEntity(WanjialeEntity, ClimateEntity):
    """壁挂炉采暖实体。

    控制采暖系统：
      - 当前温度 = dvid 107（当前供暖水温）
      - 目标温度 = dvid 110（设定供暖水温）
      - HVAC 模式 = dvid 150（供暖开关）：HEAT=开, OFF=关

    控制方法使用同步签名，HA 自动包装到 executor 线程。
    """

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_target_temperature_step = 1
    _attr_icon = "mdi:radiator"

    def __init__(self, device, coordinator) -> None:
        super().__init__(device, coordinator)
        self._boiler: WanjialeBoiler = device

    @property
    def name(self) -> str:
        return "采暖"

    @property
    def unique_id(self) -> str:
        return f"{self._device.unique_id()}-heating"

    @property
    def min_temp(self) -> float:
        return float(self._boiler.MIN_HEATING_TEMP)

    @property
    def max_temp(self) -> float:
        return float(self._boiler.MAX_HEATING_TEMP)

    @property
    def current_temperature(self) -> Optional[float]:
        return self._boiler.heating_current_temp

    @property
    def target_temperature(self) -> Optional[float]:
        return self._boiler.heating_target_temp

    @property
    def hvac_mode(self) -> Optional[HVACMode]:
        if self._boiler.is_heating_on:
            return HVACMode.HEAT
        return HVACMode.OFF

    # --------------------------------------------------------------
    # 控制（同步方法 -> HA 自动包装到 executor）
    # --------------------------------------------------------------
    def set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get("temperature")
        if temp is None:
            return
        self._boiler.set_heating_temperature(int(float(temp)))
        self.schedule_update_ha_state()
        self._request_refresh_soon()

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.HEAT:
            self._boiler.set_heating_power(True)
        elif hvac_mode == HVACMode.OFF:
            self._boiler.set_heating_power(False)
        self.schedule_update_ha_state()
        self._request_refresh_soon()
