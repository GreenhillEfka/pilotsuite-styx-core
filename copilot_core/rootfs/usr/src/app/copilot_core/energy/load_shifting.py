"""Load Shifting Empfehlungen — Intelligente Verbrauchsoptimierung (v12.6.0).

Erstellt Empfehlungen zur Lastverlagerung basierend auf:
- PV-Ertragsprognose
- Strompreisen (dynamische Tarife)
- Verbrauchsprognose
- Geräteeigenschaften und Flexibilität
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ShiftableDevice:
    """Verschiebbares Gerät."""
    
    device_id: str
    device_type: str  # washer/dryer/dishwasher/ev_charger/heat_pump/battery
    name: str
    power_kw: float  # Nennleistung
    energy_kwh: float  # Benötigte Energie pro Zyklus
    duration_hours: float  # Dauer
    flexibility_hours: float  # Wie lange kann Start verzögert werden
    priority: int  # 1-5 (1=höchste Priorität)
    min_start_hour: int  # Frühester Start (0-23)
    max_start_hour: int  # Spätester Start (0-23)
    must_complete_by: Optional[str]  # ISO timestamp, wann fertig sein muss
    current_state: str  # idle/running/scheduled
    cost_per_kwh: float  # Aktuelle Stromkosten


@dataclass
class LoadShiftRecommendation:
    """Empfehlung zur Lastverlagerung."""
    
    recommendation_id: str
    timestamp: str  # ISO
    device_id: str
    device_name: str
    device_type: str
    action: str  # start_now/delay/advance/schedule
    recommended_start: str  # ISO timestamp
    original_start: Optional[str]
    duration_hours: float
    energy_kwh: float
    cost_original: float  # Kosten bei ursprünglichem Start
    cost_optimized: float  # Kosten bei optimiertem Start
    savings_eur: float
    savings_pct: float
    co2_savings_g: float  # CO2-Einsparung
    reason: str  # Warum diese Empfehlung
    confidence: float  # 0-1
    pv_utilization_pct: float  # Wie viel PV-Strom genutzt wird
    grid_price_ct_kwh: float  # Strompreis zur empfohlenen Zeit


@dataclass
class OptimizationWindow:
    """Optimales Zeitfenster."""
    
    start: str  # ISO
    end: str  # ISO
    duration_hours: float
    avg_price_ct_kwh: float
    avg_pv_power_kw: float
    total_energy_kwh: float
    cost_eur: float
    co2_intensity_g_kwh: float
    recommendation: str  # Kurzbeschreibung


@dataclass
class LoadShiftSummary:
    """Zusammenfassung der Optimierung."""
    
    total_devices: int
    shiftable_devices: int
    recommendations_count: int
    total_potential_savings_eur: float
    total_potential_savings_pct: float
    total_co2_savings_kg: float
    pv_self_consumption_increase_pct: float
    grid_relief_kwh: float
    best_action_device: str
    best_action_savings_eur: float


class LoadShiftingEngine:
    """Engine für Load Shifting Empfehlungen.
    
    Analysiert Verbrauch, PV-Ertrag und Preise um optimale
    Startzeiten für flexible Geräte zu empfehlen.
    """
    
    def __init__(
        self,
        pv_forecast: Optional[list[dict]] = None,
        price_forecast: Optional[list[dict]] = None,
        consumption_forecast: Optional[list[dict]] = None,
        grid_co2_intensity: float = 400.0,  # g CO2/kWh (deutscher Mix)
    ):
        self._pv_forecast = pv_forecast or []
        self._price_forecast = price_forecast or []
        self._consumption_forecast = consumption_forecast or []
        self._grid_co2 = grid_co2_intensity
        self._devices: list[ShiftableDevice] = []
        
        # Standard-Geräteprofile
        self._device_profiles = {
            "washer": {
                "power_kw": 2.0,
                "energy_kwh": 1.5,
                "duration_hours": 1.5,
                "flexibility_hours": 8,
                "priority": 3,
            },
            "dryer": {
                "power_kw": 2.5,
                "energy_kwh": 3.0,
                "duration_hours": 1.5,
                "flexibility_hours": 12,
                "priority": 3,
            },
            "dishwasher": {
                "power_kw": 1.5,
                "energy_kwh": 1.0,
                "duration_hours": 2.5,
                "flexibility_hours": 10,
                "priority": 2,
            },
            "ev_charger": {
                "power_kw": 11.0,
                "energy_kwh": 40.0,
                "duration_hours": 4.0,
                "flexibility_hours": 24,
                "priority": 4,
            },
            "heat_pump": {
                "power_kw": 5.0,
                "energy_kwh": 10.0,
                "duration_hours": 3.0,
                "flexibility_hours": 6,
                "priority": 5,
            },
            "battery": {
                "power_kw": 5.0,
                "energy_kwh": 10.0,
                "duration_hours": 2.0,
                "flexibility_hours": 24,
                "priority": 5,
            },
        }
    
    def set_pv_forecast(self, forecast: list[dict]) -> None:
        """Setze PV-Prognose."""
        self._pv_forecast = forecast
    
    def set_price_forecast(self, forecast: list[dict]) -> None:
        """Setze Preisprognose (ct/kWh)."""
        self._price_forecast = forecast
    
    def set_consumption_forecast(self, forecast: list[dict]) -> None:
        """Setze Verbrauchsprognose."""
        self._consumption_forecast = forecast
    
    def set_co2_intensity(self, intensity_g_kwh: float) -> None:
        """Setze CO2-Intensität des Stromnetzes."""
        self._grid_co2 = intensity_g_kwh
    
    def add_device(self, device: ShiftableDevice) -> None:
        """Füge Gerät hinzu."""
        self._devices.append(device)
    
    def add_device_from_profile(
        self,
        device_id: str,
        device_type: str,
        name: str,
        **kwargs,
    ) -> None:
        """Füge Gerät aus Profil hinzu."""
        profile = self._device_profiles.get(device_type, {})
        
        device = ShiftableDevice(
            device_id=device_id,
            device_type=device_type,
            name=name,
            power_kw=kwargs.get("power_kw", profile.get("power_kw", 1.0)),
            energy_kwh=kwargs.get("energy_kwh", profile.get("energy_kwh", 1.0)),
            duration_hours=kwargs.get("duration_hours", profile.get("duration_hours", 1.0)),
            flexibility_hours=kwargs.get("flexibility_hours", profile.get("flexibility_hours", 4)),
            priority=kwargs.get("priority", profile.get("priority", 3)),
            min_start_hour=kwargs.get("min_start_hour", 0),
            max_start_hour=kwargs.get("max_start_hour", 23),
            must_complete_by=kwargs.get("must_complete_by"),
            current_state=kwargs.get("current_state", "idle"),
            cost_per_kwh=kwargs.get("cost_per_kwh", 30.0),
        )
        self._devices.append(device)
    
    def _get_price_at(self, hour_offset: int) -> float:
        """Hole Preis für Stunde."""
        if hour_offset < len(self._price_forecast):
            return self._price_forecast[hour_offset].get("price_ct_kwh", 30.0)
        return 30.0  # Default
    
    def _get_pv_at(self, hour_offset: int) -> float:
        """Hole PV-Leistung für Stunde (kW)."""
        if hour_offset < len(self._pv_forecast):
            return self._pv_forecast[hour_offset].get("pv_power_kw", 0.0)
        return 0.0
    
    def _get_consumption_at(self, hour_offset: int) -> float:
        """Hole Verbrauch für Stunde (kW)."""
        if hour_offset < len(self._consumption_forecast):
            return self._consumption_forecast[hour_offset].get("predicted_consumption_kw", 0.5)
        return 0.5
    
    def _calculate_pv_utilization(
        self,
        start_hour: int,
        duration_hours: float,
        device_power_kw: float,
    ) -> float:
        """Berechne PV-Ausnutzungsgrad für Zeitraum."""
        if not self._pv_forecast:
            return 0.0
        
        total_pv = 0.0
        total_consumption = 0.0
        
        for h in range(int(duration_hours) + 1):
            hour_idx = start_hour + h
            if hour_idx < len(self._pv_forecast):
                pv = self._pv_forecast[hour_idx].get("pv_power_kw", 0.0)
                total_pv += pv
                total_consumption += device_power_kw
        
        if total_consumption == 0:
            return 0.0
        
        return min(1.0, total_pv / total_consumption)
    
    def _calculate_score(
        self,
        start_hour: int,
        device: ShiftableDevice,
    ) -> tuple[float, dict]:
        """Berechne Score für Startzeit (höher = besser)."""
        duration = device.duration_hours
        price_score = 0.0
        pv_score = 0.0
        grid_relief_score = 0.0
        
        # Preis-Score
        total_cost = 0.0
        for h in range(int(duration) + 1):
            price = self._get_price_at(start_hour + h)
            total_cost += price * (device.energy_kwh / duration)
        
        avg_price = total_cost / duration if duration > 0 else 0
        price_score = (50 - avg_price) / 50  # Normalisiert
        
        # PV-Score
        pv_util = self._calculate_pv_utilization(start_hour, duration, device.power_kw)
        pv_score = pv_util
        
        # Netz-Entlastung (Verbrauch wenn wenig andere Last)
        base_consumption = self._get_consumption_at(start_hour)
        grid_relief_score = (1.0 - base_consumption / 2.0)  # Normalisiert
        
        # Gewichteter Gesamtscore
        total_score = (
            price_score * 0.4 +
            pv_score * 0.4 +
            grid_relief_score * 0.2
        )
        
        details = {
            "price_score": round(price_score, 3),
            "pv_score": round(pv_score, 3),
            "grid_relief_score": round(grid_relief_score, 3),
            "avg_price_ct": round(avg_price, 2),
            "pv_utilization": round(pv_util, 3),
        }
        
        return max(0, min(1, total_score)), details
    
    def _find_optimal_window(
        self,
        device: ShiftableDevice,
    ) -> tuple[int, float, dict]:
        """Finde optimales Startfenster für Gerät."""
        now = datetime.now()
        best_hour = 0
        best_score = -1
        best_details = {}
        
        # Prüfe alle möglichen Startzeiten
        for h in range(device.flexibility_hours):
            hour_of_day = (now.hour + h) % 24
            
            # Prüfe Zeitfenster-Beschränkungen
            if hour_of_day < device.min_start_hour or hour_of_day > device.max_start_hour:
                continue
            
            score, details = self._calculate_score(now.hour + h, device)
            
            if score > best_score:
                best_score = score
                best_hour = h
                best_details = details
        
        return best_hour, best_score, best_details
    
    def generate_recommendations(self) -> list[LoadShiftRecommendation]:
        """Generiere Load Shifting Empfehlungen."""
        recommendations = []
        now = datetime.now()
        
        for device in self._devices:
            # Nur idle Geräte
            if device.current_state != "idle":
                continue
            
            # Finde optimales Fenster
            delay_hours, score, details = self._find_optimal_window(device)
            
            # Berechne Kosten
            original_price = self._get_price_at(0)
            optimized_price = details.get("avg_price_ct", original_price)
            
            cost_original = device.energy_kwh * original_price / 100
            cost_optimized = device.energy_kwh * optimized_price / 100
            savings_eur = cost_original - cost_optimized
            
            # PV-basierte Einsparung
            pv_util = details.get("pv_utilization", 0)
            pv_savings = device.energy_kwh * pv_util * original_price / 100
            savings_eur += pv_savings
            
            savings_pct = (savings_eur / cost_original * 100) if cost_original > 0 else 0
            
            # CO2-Einsparung durch PV-Nutzung
            co2_savings = device.energy_kwh * pv_util * (self._grid_co2 - 50) / 1000  # kg
            
            # Empfehlungstext
            if pv_util > 0.5:
                reason = f"Maximale PV-Nutzung ({pv_util*100:.0f}%) während der Laufzeit"
            elif optimized_price < 25:
                reason = f"Günstiger Strompreis ({optimized_price:.1f} ct/kWh)"
            elif score > 0.7:
                reason = "Optimale Kombination aus PV und Preis"
            else:
                reason = "Verbrauch in günstigerem Zeitfenster"
            
            recommended_start = now + timedelta(hours=delay_hours)
            
            rec = LoadShiftRecommendation(
                recommendation_id=f"rec_{device.device_id}_{int(now.timestamp())}",
                timestamp=now.isoformat(),
                device_id=device.device_id,
                device_name=device.name,
                device_type=device.device_type,
                action="schedule" if delay_hours > 0 else "start_now",
                recommended_start=recommended_start.isoformat(),
                original_start=now.isoformat(),
                duration_hours=device.duration_hours,
                energy_kwh=device.energy_kwh,
                cost_original=round(cost_original, 3),
                cost_optimized=round(cost_optimized, 3),
                savings_eur=round(savings_eur, 3),
                savings_pct=round(savings_pct, 1),
                co2_savings_g=round(co2_savings * 1000, 1),
                reason=reason,
                confidence=round(score, 2),
                pv_utilization_pct=round(pv_util * 100, 1),
                grid_price_ct_kwh=round(optimized_price, 2),
            )
            recommendations.append(rec)
        
        # Sortiere nach Einsparung
        recommendations.sort(key=lambda r: -r.savings_eur)
        
        return recommendations
    
    def generate_optimization_windows(
        self,
        hours_ahead: int = 24,
    ) -> list[OptimizationWindow]:
        """Generiere optimale Zeitfenster für Verbrauch."""
        windows = []
        now = datetime.now()
        
        # Finde 3-4 beste Fenster
        window_size = 2  # Stunden
        
        for start_h in range(0, hours_ahead - window_size, 2):
            # Durchschnittspreis
            avg_price = sum(
                self._get_price_at(start_h + h) for h in range(window_size)
            ) / window_size
            
            # Durchschnitt PV
            avg_pv = sum(
                self._get_pv_at(start_h + h) for h in range(window_size)
            ) / window_size
            
            # Gesamtkosten für typischen Verbrauch (2 kWh)
            cost = 2.0 * avg_price / 100
            
            # Score
            score = (50 - avg_price) / 50 * 0.5 + avg_pv / 5.0 * 0.5
            
            if score > 0.5:  # Nur gute Fenster
                start = now + timedelta(hours=start_h)
                end = start + timedelta(hours=window_size)
                
                rec = ""
                if avg_pv > 2.0:
                    rec = f"PV-Spitze: {avg_pv:.1f} kW verfügbar"
                elif avg_price < 25:
                    rec = f"Niedriger Preis: {avg_price:.1f} ct/kWh"
                else:
                    rec = "Gute Bedingungen"
                
                window = OptimizationWindow(
                    start=start.isoformat(),
                    end=end.isoformat(),
                    duration_hours=window_size,
                    avg_price_ct_kwh=round(avg_price, 2),
                    avg_pv_power_kw=round(avg_pv, 2),
                    total_energy_kwh=2.0,
                    cost_eur=round(cost, 3),
                    co2_intensity_g_kwh=round(self._grid_co2 * (1 - avg_pv/5), 0),
                    recommendation=rec,
                )
                windows.append(window)
        
        # Sortiere nach Score, nimm top 4
        windows.sort(key=lambda w: -w.avg_pv_power_kw / max(1, w.avg_price_ct_kwh))
        return windows[:4]
    
    def generate_summary(
        self,
        recommendations: Optional[list[LoadShiftRecommendation]] = None,
    ) -> LoadShiftSummary:
        """Generiere Zusammenfassung."""
        if recommendations is None:
            recommendations = self.generate_recommendations()
        
        total_savings = sum(r.savings_eur for r in recommendations)
        total_co2 = sum(r.co2_savings_g for r in recommendations) / 1000  # kg
        avg_pv_util = sum(r.pv_utilization_pct for r in recommendations) / len(recommendations) if recommendations else 0
        
        shiftable = len([d for d in self._devices if d.current_state == "idle"])
        
        best_rec = recommendations[0] if recommendations else None
        
        return LoadShiftSummary(
            total_devices=len(self._devices),
            shiftable_devices=shiftable,
            recommendations_count=len(recommendations),
            total_potential_savings_eur=round(total_savings, 2),
            total_potential_savings_pct=round(total_savings / max(0.01, sum(r.cost_original for r in recommendations)) * 100, 1),
            total_co2_savings_kg=round(total_co2, 2),
            pv_self_consumption_increase_pct=round(avg_pv_util, 1),
            grid_relief_kwh=round(sum(r.energy_kwh * r.pv_utilization_pct / 100 for r in recommendations), 2),
            best_action_device=best_rec.device_name if best_rec else "",
            best_action_savings_eur=round(best_rec.savings_eur, 2) if best_rec else 0,
        )
    
    def get_recommendations_as_dict(self) -> dict:
        """Generiere komplettes Ergebnis als Dictionary."""
        recommendations = self.generate_recommendations()
        windows = self.generate_optimization_windows()
        summary = self.generate_summary(recommendations)
        
        return {
            "generated_at": datetime.now().isoformat(),
            "summary": asdict(summary),
            "recommendations": [asdict(r) for r in recommendations],
            "optimization_windows": [asdict(w) for w in windows],
            "devices": [asdict(d) for d in self._devices],
        }
    
    def get_simple_recommendation_text(self) -> str:
        """Generiere einfache Text-Empfehlung für UI."""
        recommendations = self.generate_recommendations()
        
        if not recommendations:
            return "Keine Load-Shifting Empfehlungen verfügbar."
        
        best = recommendations[0]
        
        text = f"💡 {best.device_name} um {best.recommended_start[11:16]} starten — "
        
        if best.pv_utilization_pct > 50:
            text += f"PV-Spitze nutzen ({best.pv_utilization_pct:.0f}%)!"
        elif best.grid_price_ct_kwh < 25:
            text += f"günstiger Strom ({best.grid_price_ct_kwh:.1f} ct/kWh)!"
        else:
            text += f"{best.savings_eur:.2f}€ sparen!"
        
        return text


# Slice 70: OR-Tools-inspired Scheduling Optimizer (P2-002)
# Simple greedy heuristic — OR-Tools constraint solver pattern
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SchedulingWindow:
    """Time window for scheduling a device."""
    start_hour: float
    end_hour: float
    cost_per_kwh: float


def greedy_schedule_optimize(
    devices: List[ShiftableDevice],
    windows: List[SchedulingWindow],
    energy_kwh_target: float,
    battery_charge_kwh: float = 0.0,
) -> List[Tuple[str, Optional[float]]]:
    """Greedy scheduling: assigns cheapest windows to highest-priority devices.
    
    Args:
        devices: List of shiftable devices, sorted by priority (1=highest)
        windows: Available time windows with cost info
        energy_kwh_target: Target energy budget
        battery_charge_kwh: Battery buffer in kWh
    
    Returns:
        List of (device_id, optimal_start_hour) — None if unschedulable
    """
    if not devices or not windows:
        return []
    
    # Sort windows by cost ascending (cheapest first)
    sorted_windows = sorted(windows, key=lambda w: w.cost_per_kwh)
    
    assignments = []
    remaining_budget = energy_kwh_target + battery_charge_kwh
    
    for dev in sorted(devices, key=lambda d: d.priority):
        if remaining_budget < dev.energy_kwh:
            assignments.append((dev.device_id, None))  # Cannot fit
            continue
        
        # Find cheapest window that fits this device
        best_start: Optional[float] = None
        best_cost = float("inf")
        
        for win in sorted_windows:
            available_hours = win.end_hour - win.start_hour
            if available_hours < dev.duration_hours:
                continue
            if dev.min_start_hour > win.start_hour:
                continue
            if dev.max_start_hour < win.end_hour:
                continue
            
            if win.cost_per_kwh < best_cost:
                best_cost = win.cost_per_kwh
                # Schedule at the cheapest feasible point
                best_start = max(win.start_hour, dev.min_start_hour)
        
        if best_start is not None:
            remaining_budget -= dev.energy_kwh
        
        assignments.append((dev.device_id, best_start))
    
    return assignments
