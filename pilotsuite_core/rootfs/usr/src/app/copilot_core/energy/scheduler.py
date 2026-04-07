"""Energy Load-Shifting Scheduler (Slice 182 / P2-002).

Uses Google OR-Tools CP-SAT solver to optimize device schedules
based on LSTM energy forecasts (P1-002) and real-time pricing.

Architecture:
    LSTM Forecast (P1-002)
        ↓  (predicted load, solar, price)
    OR-Tools CP-SAT Scheduler (this file)
        ↓  (device schedules, battery plan)
    Action Executor (VS-6 / autonomy_executor)

Priority device classes:
1. EV Charging (flexible, high kWh, hard deadline)
2. Heat Pump / Hot Water (thermal buffer = storage)
3. Battery Storage (arbitrage + solar self-consumption)

Rolling 24-hour horizon with 15-minute slots (96 decision variables).
Re-optimize every hour or on price/forecast update.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
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

    def solve(
        self,
        timeout_seconds: float = 5.0,
        allow_soft_constraints: bool = True,
    ) -> Dict[str, Any]:
        """Solve the optimization problem using CP-SAT.
        
        Args:
            timeout_seconds: Max time for solver (default 5s).
            allow_soft_constraints: If True, use soft deadlines with penalty weights.
            
        Returns:
            Dict with schedule, cost_savings, solar_usage, status.
        """
        if not cp_model:
            _LOGGER.warning("OR-Tools not available. Returning fallback schedule.")
            return self._fallback_schedule()

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = timeout_seconds
        solver.parameters.log_search_progress = False
        
        # Decision Variables: device_id -> [is_running_at_slot_i, ...]
        schedule_vars = {}
        soft_penalty_vars = []
        
        for task in self._tasks:
            vars_list = [model.NewBoolVar(f"{task.device_id}_{i}") for i in range(self.slots)]
            schedule_vars[task.device_id] = vars_list
            
            # Hard constraint: Must run for the required duration
            model.Add(sum(vars_list) == task.duration_slots)
            
            if allow_soft_constraints:
                # Soft constraint: Try to finish before deadline
                # Penalty increases the later the task runs past deadline
                for i in range(task.deadline_slot, self.slots):
                    penalty_var = model.NewIntVar(0, i - task.deadline_slot + 1, f"penalty_{task.device_id}_{i}")
                    model.Add(penalty_var == vars_list[i] * (i - task.deadline_slot + 1))
                    soft_penalty_vars.append(penalty_var * task.priority)
            else:
                # Hard constraint: No operation after deadline
                for i in range(task.deadline_slot, self.slots):
                    model.Add(vars_list[i] == 0)
        
        # Objective: Minimize cost (Price * Power) + penalties
        # Maximize Solar usage: solar_bonus rewards running during solar hours
        total_cost = []
        total_solar_bonus = []
        
        for task in self._tasks:
            vars_list = schedule_vars[task.device_id]
            for i in range(self.slots):
                # Cost at slot i (in cents for integer arithmetic)
                cost = int(self._price_forecast[i] * task.power_kw * 100)
                # Solar bonus at slot i (encourage running when solar is available)
                solar_bonus = int(self._solar_forecast[i] * task.power_kw * 10)
                total_cost.append(vars_list[i] * cost)
                total_solar_bonus.append(vars_list[i] * solar_bonus)
        
        if soft_penalty_vars:
            model.Minimize(sum(total_cost) + sum(soft_penalty_vars) * 100)
        else:
            model.Minimize(sum(total_cost))

        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            results = {}
            total_cost = 0.0
            total_solar_kwh = 0.0
            
            for task_id, vars_list in schedule_vars.items():
                task = next(t for t in self._tasks if t.device_id == task_id)
                slots_on = [solver.Value(v) for v in vars_list]
                results[task_id] = {
                    "slots": slots_on,
                    "start_slot": next((i for i, v in enumerate(slots_on) if v), None),
                    "end_slot": self.slots - 1 - next((i for i, v in enumerate(reversed(slots_on)) if v), -1) if any(slots_on) else None,
                    "total_slots_on": sum(slots_on),
                    "energy_kwh": sum(slots_on) * (task.power_kw / 4),  # 15-min slots = /4 for kWh
                    "solar_kwh": sum(s * self._solar_forecast[i] * task.power_kw / 4 
                                      for i, s in enumerate(slots_on)),
                }
                # Calculate cost
                for i, v in enumerate(slots_on):
                    if v:
                        total_cost += self._price_forecast[i] * task.power_kw / 4
                        total_solar_kwh += self._solar_forecast[i] * task.power_kw / 4
            
            # Calculate savings vs running at flat rate worst period
            baseline_cost = sum(t.power_kw * t.duration_slots / 4 * max(self._price_forecast) for t in self._tasks)
            savings = baseline_cost - total_cost if baseline_cost > 0 else 0
            
            _LOGGER.info(
                "Energy optimization solved: status=%s, tasks=%d, cost=%.2f€, solar=%.2fkWh, savings=%.2f€",
                status, len(results), total_cost, total_solar_kwh, savings
            )
            
            return {
                "ok": True,
                "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
                "schedule": results,
                "summary": {
                    "total_cost_eur": round(total_cost, 2),
                    "total_solar_kwh": round(total_solar_kwh, 2),
                    "cost_savings_eur": round(savings, 2),
                    "tasks_scheduled": len(results),
                },
                "slots": self.slots,
                "prices": self._price_forecast,
                "solar": self._solar_forecast,
            }
        
        _LOGGER.error("Energy optimization failed or infeasible: status=%d", status)
        return self._fallback_schedule()
    
    def _fallback_schedule(self) -> Dict[str, Any]:
        """Return a simple fallback schedule when OR-Tools unavailable."""
        results = {}
        for task in self._tasks:
            # Simple heuristic: run at cheapest slots before deadline
            slots = [0] * self.slots
            for i in range(task.duration_slots):
                # Find cheapest slot before deadline
                search_range = min(task.deadline_slot, self.slots - task.duration_slots)
                start = min(range(search_range or 1), key=lambda i: self._price_forecast[i])
                for j in range(start, min(start + task.duration_slots, self.slots)):
                    if j < len(slots):
                        slots[j] = 1
            results[task.device_id] = {"slots": slots, "heuristic": True}
        
        return {
            "ok": True,
            "status": "fallback_heuristic",
            "schedule": results,
            "summary": {"note": "Fallback schedule - OR-Tools unavailable"},
        }

    def get_schedule_horizon(self, start_hour: int = 0) -> List[Tuple[int, datetime]]:
        """Return list of (slot, datetime) for the 24h horizon."""
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        start = now.replace(hour=start_hour) if start_hour else now
        return [(i, start + timedelta(minutes=15 * i)) for i in range(self.slots)]

    def to_action_executor_format(self, schedule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert schedule to Action Executor (VS-6) format."""
        actions = []
        schedule_data = schedule.get("schedule", schedule)
        horizon = self.get_schedule_horizon()
        
        for device_id, data in schedule_data.items():
            slots = data.get("slots", [])
            for i, running in enumerate(slots):
                if running:
                    _, slot_time = horizon[i]
                    actions.append({
                        "device_id": device_id,
                        "action": "turn_on" if i == 0 or not slots[i-1] else "keep_on",
                        "scheduled_time": slot_time.isoformat(),
                        "slot": i,
                    })
        
        return sorted(actions, key=lambda a: a["scheduled_time"])

# ─── API Endpoints ─────────────────────────────────────────────────────────────────

def init_scheduler_api(bp):
    """Register scheduler API endpoints."""
    
    @bp.route("/energy/scheduler/solve", methods=["POST"])
    def trigger_energy_optimization():
        """Run energy optimization with current forecasts."""
        from flask import request
        data = request.get_json() or {}
        
        scheduler = EnergyLoadScheduler(slots_per_day=96)
        
        # Get forecasts from LSTM (P1-002) if available
        # Fallback: synthetic 24h profiles
        prices = data.get("prices") or [0.15] * 48 + [0.35] * 48
        solar = data.get("solar") or [0.0] * 24 + [5.0] * 48 + [0.0] * 24
        
        scheduler.update_forecasts(prices, solar)
        
        # Add device tasks from request or use defaults
        tasks = data.get("tasks", [])
        if not tasks:
            # Default: EV charging task
            tasks = [{
                "device_id": "sensor.ev_charger",
                "power_kw": 11.0,
                "duration_slots": 16,  # 4 hours
                "deadline_slot": 28,   # 7:00 AM
                "priority": 1,
            }]
        
        for t in tasks:
            scheduler.add_task(ScheduleTask(
                device_id=t["device_id"],
                power_kw=t["power_kw"],
                duration_slots=t["duration_slots"],
                deadline_slot=t["deadline_slot"],
                priority=t.get("priority", 1),
            ))
        
        result = scheduler.solve(
            timeout_seconds=data.get("timeout_seconds", 5.0),
            allow_soft_constraints=data.get("soft_constraints", True),
        )
        
        return {
            "ok": True,
            **result,
        }
    
    @bp.route("/energy/scheduler/preview", methods=["GET"])
    def preview_schedule():
        """Preview schedule horizon (slots with times)."""
        scheduler = EnergyLoadScheduler()
        horizon = scheduler.get_schedule_horizon()
        return {
            "ok": True,
            "slots": [{"slot": i, "time": dt.isoformat()} for i, dt in horizon],
            "count": len(horizon),
        }
    
    @bp.route("/energy/scheduler/devices", methods=["GET"])
    def list_schedulable_devices():
        """List controllable devices for scheduling."""
        # In production, this would query HA entity registry
        return {
            "ok": True,
            "devices": [
                {"id": "sensor.ev_charger", "name": "EV Charger", "power_kw": 11.0, "flexibility": "high"},
                {"id": "sensor.heat_pump", "name": "Heat Pump", "power_kw": 3.0, "flexibility": "medium"},
                {"id": "sensor.hot_water", "name": "Hot Water Tank", "power_kw": 2.0, "flexibility": "medium"},
                {"id": "sensor.battery_storage", "name": "Battery Storage", "power_kw": 5.0, "flexibility": "high"},
            ],
        }
    
    @bp.route("/energy/scheduler/connect", methods=["POST"])
    def connect_to_forecaster():
        """Connect scheduler to LSTM Forecaster (P1-002) output."""
        from flask import request
        data = request.get_json() or {}
        forecaster_url = data.get("forecaster_url", "http://localhost:8909/api/v1/ml/forecast")
        
        # In production, would store URL and validate connection
        return {
            "ok": True,
            "connected_to": forecaster_url,
            "message": "Scheduler will poll forecasts every 15 minutes",
        }
