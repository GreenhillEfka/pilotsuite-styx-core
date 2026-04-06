"""Energy Load-Shifting Scheduler (Slice 182).

Uses Google OR-Tools CP-SAT solver to optimize device schedules 
based on LSTM energy forecasts (P1-002) and real-time pricing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
try:
    from ortools.sat.python import cp_model
except ImportError:
    _LOGGER = logging.getLogger(__name__)
    _LOGGER.warning("OR-Tools not found. Please install: pip install ortools")
    cp_model = None

_LOGGER = logging.getLogger(__name__)

@dataclass
class ScheduleTask:
    """Represents a controllable energy load."""
    device_id: str
    power_kw: float
    duration_slots: int
    deadline_slot: int # Must be finished by this slot (0-95)
    priority: int = 1 # 1=High, 3=Low

class EnergyLoadScheduler:
    """Optimizes device schedules for cost and self-consumption."""
    
    def __init__(self, slots_per_day: int = 96):
        self.slots = slots_per_day # 15-minute slots for 24h
        self._tasks: List[ScheduleTask] = []
        self._price_forecast: List[float] = [0.20] * slots_per_day
        self._solar_forecast: List[float] = [0.0] * slots_per_day

    def add_task(self, task: ScheduleTask):
        self._tasks.append(task)

    def update_forecasts(self, prices: List[float], solar: List[float]):
        self._price_forecast = prices[:self.slots]
        self._solar_forecast = solar[:self.slots]

    def solve(self) -> Dict[str, List[int]]:
        """Solves the optimization problem using CP-SAT."""
        if not cp_model:
            return {}

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        
        # Decision Variables: device_id -> [is_running_at_slot_i, ...]
        schedule_vars = {}
        for task in self._tasks:
            vars_list = [model.NewBoolVar(f"{task.device_id}_{i}") for i in range(self.slots)]
            schedule_vars[task.device_id] = vars_list
            
            # Constraint: Must run for the required duration
            model.Add(sum(vars_list) == task.duration_slots)
            
            # Constraint: Must finish before deadline
            for i in range(task.deadline_slot, self.slots):
                model.Add(vars_list[i] == 0)

        # Objective: Minimize cost (Price * Power) - Maximize Solar usage (Solar * Power * 0.5 bonus)
        total_cost = []
        for task in self._tasks:
            vars_list = schedule_vars[task.device_id]
            for i in range(self.slots):
                # Cost at slot i
                cost = int(self._price_forecast[i] * task.power_kw * 100) # int for CP-SAT
                solar_bonus = int(self._solar_forecast[i] * task.power_kw * 50)
                total_cost.append(vars_list[i] * (cost - solar_bonus))

        model.Minimize(sum(total_cost))

        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            results = {}
            for task_id, vars_list in schedule_vars.items():
                results[task_id] = [solver.Value(v) for v in vars_list]
            _LOGGER.info("Energy optimization solved successfully.")
            return results
        
        _LOGGER.error("Energy optimization failed or was infeasible.")
        return {}

# API Integration for Slice 182
def init_scheduler_api(bp):
    @bp.route("/energy/scheduler/solve", methods=["POST"])
    def trigger_energy_optimization():
        scheduler = EnergyLoadScheduler()
        # Mocking 24h price/solar from LSTM forecast (P1-002)
        scheduler.update_forecasts([0.15]*48 + [0.35]*48, [0.0]*24 + [5.0]*48 + [0.0]*24)
        
        # Adding an EV task: 11kW, 4h (16 slots), must be ready by 7am (slot 28)
        scheduler.add_task(ScheduleTask("sensor.ev_charger", 11.0, 16, 28))
        
        result = scheduler.solve()
        return {"ok": True, "schedule": result, "count": len(result)}
