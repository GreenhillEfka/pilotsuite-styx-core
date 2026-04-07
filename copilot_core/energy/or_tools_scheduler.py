"""OR-Tools Scheduling Optimizer — Energy Load-Shifting with CP-SAT Solver."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import time

logger = logging.getLogger(__name__)

try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    logger.warning("OR-Tools not installed. Install with: pip install ortools")


class DeviceClass(Enum):
    """High-value device classes for scheduling."""
    EV_CHARGING = "ev_charging"
    HEAT_PUMP = "heat_pump"
    BATTERY = "battery_storage"
    HOT_WATER = "hot_water"
    DEFERRABLE = "deferrable_appliance"


class ConstraintType(Enum):
    """Constraint types."""
    HARD = "hard"
    SOFT = "soft"


@dataclass
class DeviceConstraint:
    """Constraint for a device."""
    device_id: str
    device_class: DeviceClass
    constraint_type: ConstraintType
    description: str
    min_power_kw: float = 0.0
    max_power_kw: float = 0.0
    deadline_slot: Optional[int] = None
    min_state: Optional[float] = None
    max_state: Optional[float] = None
    comfort_temp_min: Optional[float] = None
    comfort_temp_max: Optional[float] = None
    penalty_weight: float = 1.0


@dataclass
class ScheduleResult:
    """Optimization result."""
    success: bool
    status: str
    total_cost: float
    total_solar_used_kwh: float
    total_grid_consumption_kwh: float
    device_schedules: Dict[str, List[Dict]]
    solver_time_ms: float
    slots: int = 96
    infeasible_constraints: List[str] = field(default_factory=list)


class ORToolsScheduler:
    """
    OR-Tools CP-SAT Scheduler for residential energy optimization.
    Rolling 24-hour horizon with 15-minute slots (96 slots).
    """

    def __init__(self, slots: int = 96, solver_timeout_sec: float = 5.0):
        if not ORTOOLS_AVAILABLE:
            raise ImportError("OR-Tools not available. Install: pip install ortools")
        
        self._slots = slots
        self._solver_timeout = solver_timeout_sec
        self._last_schedule: Optional[ScheduleResult] = None
        self._optimization_history: List[ScheduleResult] = []

    def optimize(
        self,
        devices: List[DeviceConstraint],
        forecast: Dict[str, List[float]],
        prices: List[float],
        carbon_intensity: Optional[List[float]] = None,
    ) -> ScheduleResult:
        """Run optimization for 24-hour horizon."""
        start_time = time.perf_counter()
        model = cp_model.CpModel()
        
        # Decision variables
        device_vars = {}
        for device in devices:
            device_vars[device.device_id] = []
            for slot in range(self._slots):
                var = model.NewIntVar(
                    int(device.min_power_kw * 1000),
                    int(device.max_power_kw * 1000),
                    f"power_{device.device_id}_slot{slot}"
                )
                device_vars[device.device_id].append(var)
        
        # Power limit constraints
        for device in devices:
            for slot in range(self._slots):
                model.Add(device_vars[device.device_id][slot] >= int(device.min_power_kw * 1000))
                model.Add(device_vars[device.device_id][slot] <= int(device.max_power_kw * 1000))
        
        # Deadline constraints
        for device in devices:
            if device.deadline_slot is not None and device.min_state is not None:
                energy_until_deadline = sum(
                    device_vars[device.device_id][s] for s in range(device.deadline_slot + 1)
                )
                min_energy = int(device.min_state * 1000)
                model.Add(energy_until_deadline >= min_energy)
        
        # Objective: Minimize cost
        objective_terms = []
        for device in devices:
            for slot in range(self._slots):
                power_var = device_vars[device.device_id][slot]
                price = prices[slot] if slot < len(prices) else prices[-1]
                objective_terms.append(power_var * price)
        
        # Carbon weighting
        if carbon_intensity:
            for device in devices:
                for slot in range(self._slots):
                    power_var = device_vars[device.device_id][slot]
                    carbon = carbon_intensity[slot] if slot < len(carbon_intensity) else 500
                    objective_terms.append(power_var * carbon * 0.01)
        
        model.Minimize(sum(objective_terms))
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self._solver_timeout
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)
        
        solve_time_ms = (time.perf_counter() - start_time) * 1000
        
        # Extract results
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            device_schedules = {}
            total_cost = 0.0
            total_solar = 0.0
            total_grid = 0.0
            solar_forecast = forecast.get('solar', [0.0] * self._slots)
            
            for device in devices:
                schedule = []
                for slot in range(self._slots):
                    power_kw = solver.Value(device_vars[device.device_id][slot]) / 1000.0
                    price = prices[slot] if slot < len(prices) else prices[-1]
                    solar_avail = solar_forecast[slot] if slot < len(solar_forecast) else 0.0
                    
                    solar_used = min(power_kw / 4, solar_avail)
                    grid_used = (power_kw / 4) - solar_used
                    
                    total_cost += power_kw * price / 4
                    total_solar += solar_used
                    total_grid += max(0, grid_used)
                    
                    schedule.append({
                        "slot": slot,
                        "time": f"{slot // 4:02d}:{(slot % 4) * 15:02d}",
                        "power_kw": power_kw,
                        "solar_used_kw": solar_used * 4,
                        "grid_used_kw": max(0, grid_used) * 4,
                        "cost_ct": power_kw * price / 4,
                    })
                device_schedules[device.device_id] = schedule
            
            result = ScheduleResult(
                success=True,
                status=cp_model.Status.Name(status),
                total_cost=total_cost,
                total_solar_used_kwh=total_solar,
                total_grid_consumption_kwh=total_grid,
                device_schedules=device_schedules,
                solver_time_ms=solve_time_ms,
                slots=self._slots,
            )
        else:
            result = ScheduleResult(
                success=False,
                status=cp_model.Status.Name(status),
                total_cost=0.0,
                total_solar_used_kwh=0.0,
                total_grid_consumption_kwh=0.0,
                device_schedules={},
                solver_time_ms=solve_time_ms,
                slots=self._slots,
                infeasible_constraints=[d.device_id for d in devices],
            )
        
        self._last_schedule = result
        self._optimization_history.append(result)
        logger.info(f"Optimization: {result.status} in {solve_time_ms:.1f}ms, cost={result.total_cost:.2f}ct")
        
        return result

    def get_stats(self) -> Dict[str, Any]:
        if not self._optimization_history:
            return {"optimizations_run": 0, "slots": self._slots}
        successful = [r for r in self._optimization_history if r.success]
        return {
            "optimizations_run": len(self._optimization_history),
            "successful": len(successful),
            "avg_solver_time_ms": sum(r.solver_time_ms for r in successful) / len(successful),
            "slots": self._slots,
        }


default_or_scheduler: Optional[ORToolsScheduler] = None


def init_or_scheduler(slots: int = 96, timeout_sec: float = 5.0) -> ORToolsScheduler:
    global default_or_scheduler
    default_or_scheduler = ORToolsScheduler(slots=slots, solver_timeout_sec=timeout_sec)
    return default_or_scheduler
