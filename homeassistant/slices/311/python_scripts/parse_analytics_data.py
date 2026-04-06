"""Parse PilotSuite Analytics Data and Create Home Assistant Sensors.

This script is called by the analytics sensors blueprint to:
1. Fetch data from the PilotSuite Advanced Analytics API
2. Parse the response and extract metrics
3. Create/update Home Assistant sensors for dashboard use

Requires: Home Assistant Python Scripts integration enabled
"""

from datetime import datetime, timezone


def extract_module_health(module_cards, module_id):
    """Extract health data for a specific module."""
    for card in module_cards:
        if card.get("module_id") == module_id:
            return {
                "state": str(card.get("health_score", 0)),
                "attributes": {
                    "status": card.get("status", "unknown"),
                    "total_events": card.get("total_events", 0),
                    "trend_7d": card.get("trend_7d", 0),
                    "trend_30d": card.get("trend_30d", 0),
                    "key_metrics": card.get("key_metrics", {}),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }
            }
    return None


def main():
    """Main entry point for the script."""
    # Get response data from the blueprint call
    response_data = data.get("response_data", {})
    
    if not response_data or not response_data.get("ok"):
        logger.error("Invalid analytics response data")
        return
    
    analytics_data = response_data.get("data", {})
    
    # Extract overall system health
    system_health = analytics_data.get("overall_health_score", 0)
    system_status = analytics_data.get("overall_status", "unknown")
    
    # Create system health sensor
    service_data = {
        "entity_id": "sensor.pilotsuite_system_health",
        "state": str(system_health),
        "attributes": {
            "status": system_status,
            "zones_active": analytics_data.get("zones_active", 0),
            "zones_total": analytics_data.get("zones_total", 0),
            "time_range_days": analytics_data.get("time_range_days", 30),
            "refresh_interval_seconds": analytics_data.get("refresh_interval_seconds", 60),
            "generated_at": analytics_data.get("generated_at", ""),
            "unit_of_measurement": "score",
            "device_class": "measurement",
        }
    }
    service.call("python_script", "set_state", service_data)
    
    # Extract total events KPI
    kpis = analytics_data.get("kpis", [])
    total_events = 0
    acceptance_rate = 0
    
    for kpi in kpis:
        if kpi.get("kpi_id") == "total_events":
            total_events = int(kpi.get("current_value", 0))
        elif kpi.get("kpi_id") == "acceptance_rate":
            acceptance_rate = kpi.get("current_value", 0)
    
    # Create total events sensor
    service_data = {
        "entity_id": "sensor.pilotsuite_total_events",
        "state": str(total_events),
        "attributes": {
            "unit_of_measurement": "events",
            "device_class": "measurement",
        }
    }
    service.call("python_script", "set_state", service_data)
    
    # Create acceptance rate sensor
    service_data = {
        "entity_id": "sensor.pilotsuite_acceptance_rate",
        "state": str(acceptance_rate),
        "attributes": {
            "unit_of_measurement": "rate",
            "device_class": "measurement",
        }
    }
    service.call("python_script", "set_state", service_data)
    
    # Extract module health cards
    module_cards = analytics_data.get("module_cards", [])
    
    # Create sensors for each module
    modules = [
        "zone_truth",
        "proposal_lifecycle",
        "action_closure",
        "brain_neuron",
        "chat_rag",
    ]
    
    for module_id in modules:
        module_data = extract_module_health(module_cards, module_id)
        if module_data:
            service_data = {
                "entity_id": f"sensor.pilotsuite_{module_id}_health",
                "state": module_data["state"],
                "attributes": module_data["attributes"]
            }
            service.call("python_script", "set_state", service_data)
    
    # Create attention count sensor
    attention_items = analytics_data.get("attention_required", [])
    service_data = {
        "entity_id": "sensor.pilotsuite_attention_count",
        "state": str(len(attention_items)),
        "attributes": {
            "items": attention_items,
            "unit_of_measurement": "items",
        }
    }
    service.call("python_script", "set_state", service_data)
    
    logger.info(f"Updated PilotSuite analytics sensors: health={system_health:.2f}, events={total_events}")
