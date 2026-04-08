"""
ML Model Store for PilotSuite Core

Provides persistent storage and versioning for ML models.
Supports model metadata, training history, and A/B testing.

Features:
- Model persistence with versioning
- Training metadata tracking
- Model comparison and selection
- Automatic backup and rollback
"""

from __future__ import annotations

import logging
import os
import json
import shutil
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Metadata for a stored ML model."""
    
    # Model identification
    model_id: str
    model_type: str  # e.g., "isolation_forest", "feature_extractor"
    version: str
    
    # Training information
    created_at: str
    trained_at: Optional[str] = None
    training_samples: int = 0
    training_duration_seconds: Optional[float] = None
    
    # Performance metrics
    metrics: Dict[str, float] = field(default_factory=dict)
    
    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Feature information
    feature_names: List[str] = field(default_factory=list)
    
    # Status
    status: str = "active"  # active, archived, deprecated
    
    # Checksum for integrity verification
    checksum: Optional[str] = None
    
    # Tags for organization
    tags: List[str] = field(default_factory=list)
    
    # Description
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetadata":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class TrainingRecord:
    """Record of a model training session."""
    
    # Training identification
    training_id: str
    model_id: str
    
    # Timing
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    # Data information
    training_samples: int = 0
    validation_samples: int = 0
    data_hash: Optional[str] = None
    
    # Hyperparameters
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    
    # Results
    metrics: Dict[str, float] = field(default_factory=dict)
    status: str = "completed"  # completed, failed, interrupted
    
    # Error information
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrainingRecord":
        """Create from dictionary."""
        return cls(**data)


class ModelStore:
    """
    Persistent storage for ML models with versioning and metadata.
    
    Directory structure:
    model_store/
    ├── models/
    │   ├── anomaly_detector/
    │   │   ├── v1.0.0/
    │   │   │   ├── model.json
    │   │   │   ├── metadata.json
    │   │   │   └── scaler.npy
    │   │   └── v1.1.0/
    │   └── feature_extractor/
    │       └── v1.0.0/
    ├── training/
    │   └── <training_id>.json
    └── registry.json
    
    Usage:
        store = ModelStore("/path/to/store")
        
        # Save a model
        store.save_model(
            model_id="anomaly_detector",
            version="1.0.0",
            model_data=model_dict,
            metadata=metadata
        )
        
        # Load a model
        model_data, metadata = store.load_model("anomaly_detector", "1.0.0")
        
        # List versions
        versions = store.list_versions("anomaly_detector")
    """
    
    def __init__(self, store_path: str):
        self.store_path = Path(store_path)
        self.models_path = self.store_path / "models"
        self.training_path = self.store_path / "training"
        self.registry_path = self.store_path / "registry.json"
        
        # Ensure directories exist
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.training_path.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize registry
        self._registry = self._load_registry()
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load model registry from disk."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load registry: {e}")
        
        return {
            "models": {},
            "training_records": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def _save_registry(self) -> None:
        """Save registry to disk."""
        with open(self.registry_path, "w") as f:
            json.dump(self._registry, f, indent=2)
    
    def _compute_checksum(self, data: Dict[str, Any]) -> str:
        """Compute SHA256 checksum of model data."""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def save_model(
        self,
        model_id: str,
        version: str,
        model_data: Dict[str, Any],
        metadata: Optional[ModelMetadata] = None,
        extra_files: Optional[Dict[str, bytes]] = None
    ) -> ModelMetadata:
        """
        Save a model to the store.
        
        Args:
            model_id: Unique model identifier
            version: Semantic version string
            model_data: Model parameters/data as dictionary
            metadata: Optional model metadata (created automatically if not provided)
            extra_files: Optional additional files to save (e.g., numpy arrays as bytes)
            
        Returns:
            ModelMetadata for the saved model
        """
        # Create model directory
        model_dir = self.models_path / model_id / version
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Create metadata if not provided
        if metadata is None:
            metadata = ModelMetadata(
                model_id=model_id,
                model_type="unknown",
                version=version,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        
        # Compute checksum
        metadata.checksum = self._compute_checksum(model_data)
        
        # Save model data
        model_file = model_dir / "model.json"
        with open(model_file, "w") as f:
            json.dump(model_data, f, indent=2)
        
        # Save metadata
        metadata_file = model_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)
        
        # Save extra files
        if extra_files:
            for filename, content in extra_files.items():
                file_path = model_dir / filename
                with open(file_path, "wb") as f:
                    f.write(content)
        
        # Update registry
        if model_id not in self._registry["models"]:
            self._registry["models"][model_id] = {
                "versions": [],
                "latest": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        
        version_info = {
            "version": version,
            "created_at": metadata.created_at,
            "status": metadata.status,
            "checksum": metadata.checksum,
        }
        
        self._registry["models"][model_id]["versions"].append(version_info)
        self._registry["models"][model_id]["latest"] = version
        
        self._save_registry()
        
        logger.info(f"Saved model {model_id} v{version} to {model_dir}")
        return metadata
    
    def load_model(
        self,
        model_id: str,
        version: Optional[str] = None
    ) -> Tuple[Dict[str, Any], ModelMetadata]:
        """
        Load a model from the store.
        
        Args:
            model_id: Model identifier
            version: Specific version to load (uses latest if not specified)
            
        Returns:
            Tuple of (model_data, metadata)
            
        Raises:
            FileNotFoundError: If model or version not found
        """
        if version is None:
            version = self.get_latest_version(model_id)
            if version is None:
                raise FileNotFoundError(f"No versions found for model {model_id}")
        
        model_dir = self.models_path / model_id / version
        
        if not model_dir.exists():
            raise FileNotFoundError(f"Model {model_id} v{version} not found")
        
        # Load model data
        model_file = model_dir / "model.json"
        with open(model_file, "r") as f:
            model_data = json.load(f)
        
        # Load metadata
        metadata_file = model_dir / "metadata.json"
        with open(metadata_file, "r") as f:
            metadata_dict = json.load(f)
        
        metadata = ModelMetadata.from_dict(metadata_dict)
        
        # Verify checksum
        computed_checksum = self._compute_checksum(model_data)
        if computed_checksum != metadata.checksum:
            logger.warning(
                f"Checksum mismatch for {model_id} v{version}: "
                f"expected {metadata.checksum}, got {computed_checksum}"
            )
        
        return model_data, metadata
    
    def load_extra_file(
        self,
        model_id: str,
        version: str,
        filename: str
    ) -> bytes:
        """
        Load an extra file associated with a model.
        
        Args:
            model_id: Model identifier
            version: Model version
            filename: Name of the file to load
            
        Returns:
            File content as bytes
        """
        model_dir = self.models_path / model_id / version
        file_path = model_dir / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"File {filename} not found for {model_id} v{version}")
        
        with open(file_path, "rb") as f:
            return f.read()
    
    def list_versions(self, model_id: str) -> List[str]:
        """
        List all versions of a model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            List of version strings
        """
        if model_id not in self._registry["models"]:
            return []
        
        return [v["version"] for v in self._registry["models"][model_id]["versions"]]
    
    def get_latest_version(self, model_id: str) -> Optional[str]:
        """
        Get the latest version of a model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Latest version string or None if not found
        """
        if model_id not in self._registry["models"]:
            return None
        
        return self._registry["models"][model_id].get("latest")
    
    def list_models(self) -> List[str]:
        """
        List all model IDs in the store.
        
        Returns:
            List of model identifiers
        """
        return list(self._registry["models"].keys())
    
    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary information about a model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Dictionary with model information or None if not found
        """
        if model_id not in self._registry["models"]:
            return None
        
        model_info = self._registry["models"][model_id].copy()
        
        # Add latest metadata
        latest_version = model_info.get("latest")
        if latest_version:
            try:
                _, metadata = self.load_model(model_id, latest_version)
                model_info["latest_metadata"] = metadata.to_dict()
            except Exception as e:
                logger.warning(f"Failed to load metadata for {model_id}: {e}")
        
        return model_info
    
    def archive_model(self, model_id: str, version: str) -> None:
        """
        Archive a model version (mark as inactive).
        
        Args:
            model_id: Model identifier
            version: Version to archive
        """
        model_dir = self.models_path / model_id / version
        
        if not model_dir.exists():
            raise FileNotFoundError(f"Model {model_id} v{version} not found")
        
        # Update metadata
        metadata_file = model_dir / "metadata.json"
        with open(metadata_file, "r") as f:
            metadata_dict = json.load(f)
        
        metadata_dict["status"] = "archived"
        
        with open(metadata_file, "w") as f:
            json.dump(metadata_dict, f, indent=2)
        
        # Update registry
        for version_info in self._registry["models"][model_id]["versions"]:
            if version_info["version"] == version:
                version_info["status"] = "archived"
                break
        
        self._save_registry()
        logger.info(f"Archived model {model_id} v{version}")
    
    def delete_model(self, model_id: str, version: str) -> None:
        """
        Delete a model version from the store.
        
        Args:
            model_id: Model identifier
            version: Version to delete
        """
        model_dir = self.models_path / model_id / version
        
        if not model_dir.exists():
            raise FileNotFoundError(f"Model {model_id} v{version} not found")
        
        # Remove directory
        shutil.rmtree(model_dir)
        
        # Update registry
        versions = self._registry["models"][model_id]["versions"]
        self._registry["models"][model_id]["versions"] = [
            v for v in versions if v["version"] != version
        ]
        
        # Update latest if needed
        if self._registry["models"][model_id]["latest"] == version:
            remaining = self._registry["models"][model_id]["versions"]
            if remaining:
                self._registry["models"][model_id]["latest"] = remaining[-1]["version"]
            else:
                del self._registry["models"][model_id]
        
        self._save_registry()
        logger.info(f"Deleted model {model_id} v{version}")
    
    def save_training_record(self, record: TrainingRecord) -> None:
        """
        Save a training record.
        
        Args:
            record: TrainingRecord to save
        """
        record_file = self.training_path / f"{record.training_id}.json"
        
        with open(record_file, "w") as f:
            json.dump(record.to_dict(), f, indent=2)
        
        # Add to registry
        self._registry["training_records"].append({
            "training_id": record.training_id,
            "model_id": record.model_id,
            "status": record.status,
            "completed_at": record.completed_at,
        })
        
        self._save_registry()
        logger.info(f"Saved training record {record.training_id}")
    
    def get_training_record(self, training_id: str) -> Optional[TrainingRecord]:
        """
        Load a training record.
        
        Args:
            training_id: Training record identifier
            
        Returns:
            TrainingRecord or None if not found
        """
        record_file = self.training_path / f"{training_id}.json"
        
        if not record_file.exists():
            return None
        
        with open(record_file, "r") as f:
            record_dict = json.load(f)
        
        return TrainingRecord.from_dict(record_dict)
    
    def list_training_records(
        self,
        model_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[TrainingRecord]:
        """
        List training records with optional filtering.
        
        Args:
            model_id: Filter by model ID
            status: Filter by status
            limit: Maximum number of records to return
            
        Returns:
            List of TrainingRecord objects
        """
        records = []
        
        for record_file in self.training_path.glob("*.json"):
            with open(record_file, "r") as f:
                record_dict = json.load(f)
            
            record = TrainingRecord.from_dict(record_dict)
            
            # Apply filters
            if model_id and record.model_id != model_id:
                continue
            if status and record.status != status:
                continue
            
            records.append(record)
        
        # Sort by completion time (most recent first)
        records.sort(
            key=lambda r: r.completed_at or r.started_at,
            reverse=True
        )
        
        return records[:limit]
    
    def get_training_history(self, model_id: str) -> List[TrainingRecord]:
        """
        Get complete training history for a model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            List of TrainingRecord objects
        """
        return self.list_training_records(model_id=model_id, limit=1000)
    
    def compare_models(
        self,
        model_id: str,
        versions: List[str]
    ) -> Dict[str, Any]:
        """
        Compare multiple versions of a model.
        
        Args:
            model_id: Model identifier
            versions: List of versions to compare
            
        Returns:
            Comparison report dictionary
        """
        comparison = {
            "model_id": model_id,
            "versions": {},
            "metrics_comparison": [],
        }
        
        for version in versions:
            try:
                _, metadata = self.load_model(model_id, version)
                comparison["versions"][version] = {
                    "created_at": metadata.created_at,
                    "training_samples": metadata.training_samples,
                    "metrics": metadata.metrics,
                    "status": metadata.status,
                }
            except Exception as e:
                comparison["versions"][version] = {"error": str(e)}
        
        # Extract metrics for comparison
        all_metrics = set()
        for version_info in comparison["versions"].values():
            if "metrics" in version_info:
                all_metrics.update(version_info["metrics"].keys())
        
        for metric in all_metrics:
            metric_values = {}
            for version, version_info in comparison["versions"].items():
                if "metrics" in version_info and metric in version_info["metrics"]:
                    metric_values[version] = version_info["metrics"][metric]
            
            comparison["metrics_comparison"].append({
                "metric": metric,
                "values": metric_values,
            })
        
        return comparison
    
    def get_store_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the model store.
        
        Returns:
            Dictionary with store statistics
        """
        total_models = len(self._registry["models"])
        total_versions = sum(
            len(info["versions"])
            for info in self._registry["models"].values()
        )
        total_training = len(self._registry["training_records"])
        
        # Calculate storage size
        total_size = 0
        for model_dir in self.models_path.iterdir():
            if model_dir.is_dir():
                for version_dir in model_dir.iterdir():
                    if version_dir.is_dir():
                        for file_path in version_dir.rglob("*"):
                            if file_path.is_file():
                                total_size += file_path.stat().st_size
        
        return {
            "total_models": total_models,
            "total_versions": total_versions,
            "total_training_records": total_training,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "models": list(self._registry["models"].keys()),
        }


def create_model_store(store_path: str) -> ModelStore:
    """
    Factory function to create a ModelStore.
    
    Args:
        store_path: Path to the model store directory
        
    Returns:
        Configured ModelStore instance
    """
    return ModelStore(store_path)
