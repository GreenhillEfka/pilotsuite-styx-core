"""Device Profiles — Pre-configured constraints for common device types."""
from __future__ import annotations

from typing import List, Optional
from .or_tools_scheduler import DeviceConstraint, DeviceClass, ConstraintType


class DeviceProfileLibrary:
    """Pre-configured device profiles based on research recommendations."""

    @staticmethod
    def ev_charging(
        device_id: str,
        max_power_kw: float = 11.0,
        deadline_slot: int = 28,  # 7:00 AM
        min_charge_kwh: float = 40.0,
        constraint_type: ConstraintType = ConstraintType.HARD,
    ) -> DeviceConstraint:
        """EV charging: flexible, high kWh, hard deadline."""
        return DeviceConstraint(
            device_id=device_id,
            device_class=DeviceClass.EV_CHARGING,
            constraint_type=constraint_type,
            description=f"EV: {min_charge_kwh}kWh by slot {deadline_slot}",
            min_power_kw=0.0,
            max_power_kw=max_power_kw,
            deadline_slot=deadline_slot,
            min_state=min_charge_kwh,
            penalty_weight=10.0,
        )

    @staticmethod
    def heat_pump(
        device_id: str,
        max_power_kw: float = 8.0,
        comfort_temp_min: float = 20.0,
        comfort_temp_max: float = 22.0,
        constraint_type: ConstraintType = ConstraintType.SOFT,
    ) -> DeviceConstraint:
        """Heat pump with thermal buffer."""
        return DeviceConstraint(
            device_id=device_id,
            device_class=DeviceClass.HEAT_PUMP,
            constraint_type=constraint_type,
            description=f"Heat pump: {comfort_temp_min}-{comfort_temp_max}°C",
            min_power_kw=0.0,
            max_power_kw=max_power_kw,
            comfort_temp_min=comfort_temp_min,
            comfort_temp_max=comfort_temp_max,
            penalty_weight=5.0,
        )

    @staticmethod
    def battery_storage(
        device_id: str,
        capacity_kwh: float = 10.0,
        max_charge_kw: float = 5.0,
        max_discharge_kw: float = 5.0,
        min_soc: float = 0.1,
        max_soc: float = 0.9,
        constraint_type: ConstraintType = ConstraintType.HARD,
    ) -> DeviceConstraint:
        """Battery for arbitrage + solar self-consumption."""
        return DeviceConstraint(
            device_id=device_id,
            device_class=DeviceClass.BATTERY,
            constraint_type=constraint_type,
            description=f"Battery: {capacity_kwh}kWh",
            min_power_kw=-max_discharge_kw,
            max_power_kw=max_charge_kw,
            min_state=min_soc * capacity_kwh,
            max_state=max_soc * capacity_kwh,
            penalty_weight=10.0,
        )

    @classmethod
    def get_typical_home_setup(cls) -> List[DeviceConstraint]:
        """Typical home: EV + Heat Pump + Battery."""
        return [
            cls.ev_charging("wallbox.ev_charger", deadline_slot=28, min_charge_kwh=40.0),
            cls.heat_pump("climate.heat_pump"),
            cls.battery_storage("battery.home", capacity_kwh=10.0),
        ]


ev_charging = DeviceProfileLibrary.ev_charging
heat_pump = DeviceProfileLibrary.heat_pump
battery_storage = DeviceProfileLibrary.battery_storage
get_typical_home_setup = DeviceProfileLibrary.get_typical_home_setup
