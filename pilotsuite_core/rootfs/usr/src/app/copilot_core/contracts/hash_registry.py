"""Hash-Based Blueprint Registry (E2).

Tracks blueprint versions and detects drift via SHA-256 hashes.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, DateTime, create_engine
from sqlalchemy.orm import sessionmaker
from copilot_core.db.models import Base

_LOGGER = logging.getLogger(__name__)

class BlueprintRegistryEntry(Base):
    __tablename__ = 'blueprint_registry'
    blueprint_id = Column(String(100), primary_key=True)
    hash = Column(String(64), nullable=False)
    module_path = Column(String(200))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(20)) # "OK", "DRIFT", "MISSING"

class BlueprintHashRegistry:
    def __init__(self, db_url: str = "sqlite:////config/data/pilotsuite_platinum.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def calculate_hash(self, blueprint_data: Dict[str, Any]) -> str:
        """Computes deterministic SHA-256 hash of blueprint signature."""
        dump = json.dumps(blueprint_data, sort_keys=True)
        return hashlib.sha256(dump.encode()).hexdigest()

    def register_and_check(self, blueprint_id: str, data: Dict[str, Any], module_path: str):
        """Registers a blueprint and checks for drift."""
        current_hash = self.calculate_hash(data)
        session = self.Session()
        
        entry = session.query(BlueprintRegistryEntry).filter_by(blueprint_id=blueprint_id).first()
        
        if not entry:
            entry = BlueprintRegistryEntry(
                blueprint_id=blueprint_id, 
                hash=current_hash, 
                module_path=module_path,
                status="OK"
            )
            session.add(entry)
            _LOGGER.info("Registered new blueprint: %s", blueprint_id)
        elif entry.hash != current_hash:
            entry.status = "DRIFT"
            entry.last_seen = datetime.now(timezone.utc)
            _LOGGER.warning("DRIFT DETECTED for blueprint: %s", blueprint_id)
        else:
            entry.status = "OK"
            entry.last_seen = datetime.now(timezone.utc)
            
        session.commit()
        return entry.status

# Integration into System API
def init_blueprint_drift_api(bp):
    @bp.route("/blueprints/drift/status", methods=["GET"])
    def get_drift_status():
        registry = BlueprintHashRegistry()
        session = registry.Session()
        items = session.query(BlueprintRegistryEntry).all()
        return {
            "ok": True,
            "total": len(items),
            "drift_count": sum(1 for i in items if i.status == "DRIFT"),
            "items": [{"id": i.blueprint_id, "status": i.status} for i in items]
        }
