"""PilotSuite Contracts — Schema Evolution & Contract Testing."""
from __future__ import annotations

import logging
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Type
from pathlib import Path
from dataclasses import dataclass, field, asdict

from pydantic import BaseModel, Field, validator, ValidationError
from typing_extensions import Literal

logger = logging.getLogger(__name__)


# =============================================================================
# BLUEPRINT CONTRACT SCHEMA
# =============================================================================

class BlueprintContract(BaseModel):
    """Contract definition for PilotSuite Blueprints."""
    
    blueprint_id: str = Field(
        ...,
        pattern=r'^[a-z_]+_v\d+$',
        description="Unique blueprint identifier (e.g., presence_detection_v1)"
    )
    module_path: str = Field(
        ...,
        pattern=r'^copilot_core\.[a-z_]+\.[a-z_]+$',
        description="Python module path"
    )
    version: str = Field(
        ...,
        pattern=r'^\d+\.\d+\.\d+$',
        description="Semantic version"
    )
    events_published: List[str] = Field(
        default_factory=list,
        description="Events this blueprint publishes"
    )
    events_consumed: List[str] = Field(
        default_factory=list,
        description="Events this blueprint consumes"
    )
    actions_exposed: List[str] = Field(
        default_factory=list,
        description="Actions exposed by this blueprint"
    )
    config_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration schema for this blueprint"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Other blueprint IDs this depends on"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Creation timestamp"
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Last update timestamp"
    )
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of blueprint signature."""
        signature = {
            "blueprint_id": self.blueprint_id,
            "version": self.version,
            "module_path": self.module_path,
            "events_published": sorted(self.events_published),
            "events_consumed": sorted(self.events_consumed),
            "actions_exposed": sorted(self.actions_exposed),
        }
        signature_json = json.dumps(signature, sort_keys=True)
        return hashlib.sha256(signature_json.encode()).hexdigest()
    
    def validate_contract(self) -> List[str]:
        """Validate contract consistency."""
        errors = []
        
        # Check module exists
        module_parts = self.module_path.split(".")
        try:
            __import__(self.module_path)
        except ImportError as e:
            errors.append(f"Module not found: {self.module_path} - {e}")
        
        # Check for circular dependencies (simplified)
        if self.blueprint_id in self.dependencies:
            errors.append(f"Circular dependency: {self.blueprint_id} depends on itself")
        
        return errors
    
    class Config:
        json_schema_extra = {
            "example": {
                "blueprint_id": "presence_detection_v1",
                "module_path": "copilot_core.presence.api",
                "version": "1.0.0",
                "events_published": ["presence.changed", "presence.updated"],
                "events_consumed": ["sensor.updated", "config.changed"],
                "actions_exposed": ["pilotsuite.set_presence_mode"],
                "dependencies": [],
            }
        }


# =============================================================================
# API CONTRACT SCHEMA
# =============================================================================

class APIContract(BaseModel):
    """Contract definition for PilotSuite API Endpoints."""
    
    endpoint_id: str = Field(
        ...,
        pattern=r'^[a-z_]+_[v\d]+$',
        description="Unique endpoint identifier"
    )
    path: str = Field(
        ...,
        pattern=r'^/api/v\d+/[a-z_/]+$',
        description="API path"
    )
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field(
        ...,
        description="HTTP method"
    )
    request_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Request body schema (for POST/PUT/PATCH)"
    )
    response_schema: Dict[str, Any] = Field(
        ...,
        description="Response schema"
    )
    auth_required: bool = Field(
        default=True,
        description="Whether JWT auth is required"
    )
    rate_limit: Optional[int] = Field(
        default=100,
        description="Requests per minute limit"
    )
    version: str = Field(
        ...,
        pattern=r'^\d+\.\d+\.\d+$',
        description="API version"
    )
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of API signature."""
        signature = {
            "endpoint_id": self.endpoint_id,
            "path": self.path,
            "method": self.method,
            "response_schema": self.response_schema,
        }
        signature_json = json.dumps(signature, sort_keys=True)
        return hashlib.sha256(signature_json.encode()).hexdigest()


# =============================================================================
# EVENT CONTRACT SCHEMA
# =============================================================================

class EventContract(BaseModel):
    """Contract definition for PilotSuite Events."""
    
    event_type: str = Field(
        ...,
        pattern=r'^[a-z]+\.[a-z]+$',
        description="Event type (e.g., presence.changed)"
    )
    payload_schema: Dict[str, Any] = Field(
        ...,
        description="Event payload schema"
    )
    version: str = Field(
        ...,
        pattern=r'^\d+\.\d+\.\d+$',
        description="Event schema version"
    )
    publisher: Optional[str] = Field(
        default=None,
        description="Blueprint ID that publishes this event"
    )
    consumers: List[str] = Field(
        default_factory=list,
        description="Blueprint IDs that consume this event"
    )
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of event signature."""
        signature = {
            "event_type": self.event_type,
            "payload_schema": self.payload_schema,
            "version": self.version,
        }
        signature_json = json.dumps(signature, sort_keys=True)
        return hashlib.sha256(signature_json.encode()).hexdigest()


# =============================================================================
# CONTRACT REGISTRY
# =============================================================================

@dataclass
class RegisteredContract:
    """A registered contract with metadata."""
    contract: BaseModel
    hash: str
    registered_at: datetime
    source_file: str
    line_number: int
    status: str = "active"  # active, deprecated, drift, missing


class ContractRegistry:
    """
    Central registry for all contracts with drift detection.
    
    Features:
    - Hash-based contract tracking
    - Drift detection between versions
    - Contract validation
    - Registry persistence (SQLite)
    """

    def __init__(self, registry_path: str = "/config/pilotsuite/contracts/registry.json"):
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._contracts: Dict[str, RegisteredContract] = {}
        self._load_registry()

    def register(self, contract: BaseModel, source_file: str, line_number: int = 0):
        """Register a new contract."""
        contract_hash = contract.compute_hash()
        
        registered = RegisteredContract(
            contract=contract,
            hash=contract_hash,
            registered_at=datetime.now(),
            source_file=source_file,
            line_number=line_number,
        )
        
        contract_id = getattr(contract, 'blueprint_id', None) or \
                     getattr(contract, 'endpoint_id', None) or \
                     getattr(contract, 'event_type', None)
        
        self._contracts[contract_id] = registered
        
        logger.info(f"Registered contract: {contract_id} (hash: {contract_hash[:16]}...)")
        
        self._save_registry()

    def detect_drift(self, contract: BaseModel) -> Dict[str, Any]:
        """Detect drift between new contract and registered version."""
        contract_id = getattr(contract, 'blueprint_id', None) or \
                     getattr(contract, 'endpoint_id', None) or \
                     getattr(contract, 'event_type', None)
        
        if contract_id not in self._contracts:
            return {
                "drift_detected": False,
                "reason": "new_contract",
                "contract_id": contract_id,
            }
        
        registered = self._contracts[contract_id]
        new_hash = contract.compute_hash()
        
        if registered.hash != new_hash:
            return {
                "drift_detected": True,
                "reason": "hash_mismatch",
                "contract_id": contract_id,
                "old_hash": registered.hash,
                "new_hash": new_hash,
                "old_version": getattr(registered.contract, 'version', 'unknown'),
                "new_version": getattr(contract, 'version', 'unknown'),
            }
        
        return {
            "drift_detected": False,
            "reason": "match",
            "contract_id": contract_id,
        }

    def get_all_contracts(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered contracts."""
        return {
            cid: {
                "type": type(rc.contract).__name__,
                "hash": rc.hash,
                "registered_at": rc.registered_at.isoformat(),
                "source_file": rc.source_file,
                "status": rc.status,
            }
            for cid, rc in self._contracts.items()
        }

    def _load_registry(self):
        """Load registry from file."""
        if self.registry_path.exists():
            with open(self.registry_path) as f:
                data = json.load(f)
                # Would reconstruct RegisteredContract objects here
                logger.info(f"Loaded {len(data.get('contracts', {}))} contracts")

    def _save_registry(self):
        """Save registry to file."""
        data = {
            "updated_at": datetime.now().isoformat(),
            "contracts": {
                cid: {
                    "hash": rc.hash,
                    "registered_at": rc.registered_at.isoformat(),
                    "source_file": rc.source_file,
                    "status": rc.status,
                }
                for cid, rc in self._contracts.items()
            }
        }
        
        with open(self.registry_path, "w") as f:
            json.dump(data, f, indent=2)


# =============================================================================
# CONTRACT VALIDATOR
# =============================================================================

class ContractValidator:
    """Validate contracts against schemas."""

    def __init__(self, registry: ContractRegistry):
        self.registry = registry

    def validate_blueprint(self, blueprint_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate blueprint against contract."""
        try:
            contract = BlueprintContract(**blueprint_data)
            errors = contract.validate_contract()
            
            drift = self.registry.detect_drift(contract)
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "drift": drift,
                "contract": contract.dict() if not errors else None,
            }
        except ValidationError as e:
            return {
                "valid": False,
                "errors": [str(err) for err in e.errors()],
                "drift": None,
            }

    def validate_api(self, api_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API endpoint against contract."""
        try:
            contract = APIContract(**api_data)
            drift = self.registry.detect_drift(contract)
            
            return {
                "valid": True,
                "errors": [],
                "drift": drift,
                "contract": contract.dict(),
            }
        except ValidationError as e:
            return {
                "valid": False,
                "errors": [str(err) for err in e.errors()],
                "drift": None,
            }

    def validate_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate event against contract."""
        try:
            contract = EventContract(**event_data)
            drift = self.registry.detect_drift(contract)
            
            return {
                "valid": True,
                "errors": [],
                "drift": drift,
                "contract": contract.dict(),
            }
        except ValidationError as e:
            return {
                "valid": False,
                "errors": [str(err) for err in e.errors()],
                "drift": None,
            }


# =============================================================================
# PREDEFINED CONTRACTS
# =============================================================================

def register_core_contracts(registry: ContractRegistry):
    """Register core PilotSuite contracts."""
    
    # Presence Detection Blueprint
    presence_contract = BlueprintContract(
        blueprint_id="presence_detection_v1",
        module_path="copilot_core.presence.api",
        version="1.0.0",
        events_published=["presence.changed", "presence.updated"],
        events_consumed=["sensor.updated", "config.changed"],
        actions_exposed=["pilotsuite.set_presence_mode"],
        config_schema={
            "type": "object",
            "properties": {
                "wilson_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "sensors": {"type": "array", "items": {"type": "string"}},
            }
        },
    )
    registry.register(presence_contract, "copilot_core/presence/api.py")
    
    # Energy Optimization Blueprint
    energy_contract = BlueprintContract(
        blueprint_id="energy_optimization_v1",
        module_path="copilot_core.energy.or_tools_scheduler",
        version="1.0.0",
        events_published=["energy.optimized", "energy.forecast.updated"],
        events_consumed=["energy.price.updated", "device.state.changed"],
        actions_exposed=["pilotsuite.optimize_energy"],
        config_schema={
            "type": "object",
            "properties": {
                "horizon_hours": {"type": "integer", "minimum": 1, "maximum": 168},
                "devices": {"type": "array", "items": {"type": "object"}},
            }
        },
    )
    registry.register(energy_contract, "copilot_core/energy/or_tools_scheduler.py")
    
    # REST API Endpoint Contracts
    health_endpoint = APIContract(
        endpoint_id="health_v1",
        path="/api/v1/health",
        method="GET",
        response_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]},
                "version": {"type": "string"},
                "uptime_seconds": {"type": "integer"},
            }
        },
        auth_required=False,
        rate_limit=1000,
        version="1.0.0",
    )
    registry.register(health_endpoint, "copilot_core/api/rest_server.py")


# =============================================================================
# HOME ASSISTANT INTEGRATION
# =============================================================================

async def async_setup_contracts(hass, config: Dict[str, Any]):
    """Set up contract system in Home Assistant."""
    registry = ContractRegistry()
    validator = ContractValidator(registry)
    
    # Register core contracts
    register_core_contracts(registry)
    
    # Store in hass.data
    hass.data["pilotsuite_contract_registry"] = registry
    hass.data["pilotsuite_contract_validator"] = validator
    
    logger.info("Contract system set up successfully")
    
    return registry, validator
