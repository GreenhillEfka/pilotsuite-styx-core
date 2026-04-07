"""Scheduler Integration — Forecast → Optimization → Action Executor."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
import time

logger = logging.getLogger(__name__)


@dataclass
class ForecastData:
    """Forecast data from LSTM model."""
    load_kwh: List[float]
    solar_kwh: List[float]
    price_ct_kwh: List[float]
    carbon_g_kwh: Optional[List[float]] = None
    confidence: float = 0.85
    horizon_slots: int = 96


@dataclass
class ScheduleProposal:
    """Schedule proposal for user confirmation."""
    schedule_id: str
    created_at: float
    valid_from_slot: int
    valid_until_slot: int
    total_cost_ct: float
    total_solar_kwh: float
    total_grid_kwh: float
    device_actions: Dict[str, List[Dict]]
    requires_confirmation: bool
    confirmed: bool = False


class SchedulerIntegration:
    """Integrates LSTM Forecast → OR-Tools → Action Executor."""

    def __init__(self):
        self._forecast_provider: Optional[Callable] = None
        self._scheduler: Optional[Any] = None
        self._action_executor: Optional[Callable] = None
        self._pending_proposals: Dict[str, ScheduleProposal] = {}
        self._active_schedule: Optional[ScheduleProposal] = None

    def register_forecast_provider(self, provider: Callable):
        self._forecast_provider = provider

    def register_scheduler(self, scheduler: Any):
        self._scheduler = scheduler

    def register_action_executor(self, executor: Callable):
        self._action_executor = executor

    async def run_optimization_cycle(
        self,
        devices: List[Any],
        require_confirmation: bool = False,
    ) -> Optional[ScheduleProposal]:
        """Run complete optimization cycle."""
        if not all([self._forecast_provider, self._scheduler, self._action_executor]):
            logger.error("Missing components")
            return None
        
        # Get forecast
        forecast = await self._get_forecast()
        if not forecast:
            return None
        
        # Optimize
        result = self._scheduler.optimize(
            devices=devices,
            forecast={'load': forecast.load_kwh, 'solar': forecast.solar_kwh, 'price': forecast.price_ct_kwh},
            prices=forecast.price_ct_kwh,
            carbon_intensity=forecast.carbon_g_kwh,
        )
        
        if not result.success:
            return None
        
        # Create proposal
        proposal = ScheduleProposal(
            schedule_id=f"sched_{int(time.time())}",
            created_at=time.time(),
            valid_from_slot=0,
            valid_until_slot=96,
            total_cost_ct=result.total_cost,
            total_solar_kwh=result.total_solar_used_kwh,
            total_grid_kwh=result.total_grid_consumption_kwh,
            device_actions=result.device_schedules,
            requires_confirmation=require_confirmation,
        )
        
        if require_confirmation:
            self._pending_proposals[proposal.schedule_id] = proposal
        else:
            await self._execute_schedule(proposal)
            self._active_schedule = proposal
        
        return proposal

    async def _get_forecast(self) -> Optional[ForecastData]:
        if not self._forecast_provider:
            return None
        try:
            data = await self._forecast_provider()
            return ForecastData(
                load_kwh=data.get('load', []),
                solar_kwh=data.get('solar', []),
                price_ct_kwh=data.get('price', []),
                carbon_g_kwh=data.get('carbon'),
            )
        except Exception as e:
            logger.error(f"Forecast error: {e}")
            return None

    async def _execute_schedule(self, proposal: ScheduleProposal):
        if not self._action_executor:
            return
        for device_id, actions in proposal.device_actions.items():
            if actions:
                await self._action_executor(device_id, actions[0])

    async def confirm_schedule(self, schedule_id: str) -> bool:
        if schedule_id not in self._pending_proposals:
            return False
        proposal = self._pending_proposals[schedule_id]
        proposal.confirmed = True
        await self._execute_schedule(proposal)
        self._active_schedule = proposal
        del self._pending_proposals[schedule_id]
        return True

    def get_stats(self) -> Dict[str, Any]:
        return {
            "components": sum([1 if x else 0 for x in [self._forecast_provider, self._scheduler, self._action_executor]]),
            "pending": len(self._pending_proposals),
            "active": self._active_schedule.schedule_id if self._active_schedule else None,
        }


default_scheduler_integration: Optional[SchedulerIntegration] = None


def init_scheduler_integration() -> SchedulerIntegration:
    global default_scheduler_integration
    default_scheduler_integration = SchedulerIntegration()
    return default_scheduler_integration
