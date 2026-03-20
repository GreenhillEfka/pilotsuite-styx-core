"""Input validation utilities for neuron evaluation."""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)


class NeuronInputValidator:
    """Validator for neuron input data."""
    
    @staticmethod
    def validate_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize evaluation context.
        
        Args:
            context: Raw context dictionary
            
        Returns:
            Normalized context dictionary
        """
        normalized = context.copy() if context else {}
        
        # Ensure required keys exist
        if "states" not in normalized:
            normalized["states"] = {}
            _LOGGER.debug("Added missing 'states' key to context")
        
        if "now" not in normalized:
            normalized["now"] = datetime.now()
            _LOGGER.debug("Added missing 'now' key to context")
        
        # Validate states structure
        if not isinstance(normalized["states"], dict):
            _LOGGER.warning("States is not a dict, converting to empty dict")
            normalized["states"] = {}
        
        # Validate presence data
        if "presence" not in normalized:
            normalized["presence"] = {}
        
        # Validate sun data
        if "sun" not in normalized:
            normalized["sun"] = {}
        
        # Validate weather data
        if "weather" not in normalized:
            normalized["weather"] = {}
        
        # Validate history data
        if "history" not in normalized:
            normalized["history"] = {}
        
        # Validate neurons data
        if "neurons" not in normalized:
            normalized["neurons"] = {}
        
        # Validate household data
        if "household" not in normalized:
            normalized["household"] = {}
        
        # Validate present persons
        if "present_persons" not in normalized:
            normalized["present_persons"] = []
        
        return normalized
    
    @staticmethod
    def validate_ha_state(state: Any, entity_id: str) -> Dict[str, Any]:
        """Validate and normalize Home Assistant state data.
        
        Args:
            state: Raw state data from HA
            entity_id: Entity ID for the state
            
        Returns:
            Normalized state dictionary
        """
        # Handle string states
        if isinstance(state, str):
            return {
                "state": state,
                "attributes": {},
                "last_updated": None,
                "last_changed": None
            }
        
        # Handle dict states
        if isinstance(state, dict):
            normalized = {
                "state": state.get("state", ""),
                "attributes": state.get("attributes", {}),
                "last_updated": state.get("last_updated"),
                "last_changed": state.get("last_changed")
            }
            
            # Ensure attributes is a dict
            if not isinstance(normalized["attributes"], dict):
                normalized["attributes"] = {}
                _LOGGER.warning("Attributes for %s is not a dict, converting to empty dict", entity_id)
            
            return normalized
        
        # Handle other types by converting to string
        _LOGGER.warning("Unexpected state type for %s: %s, converting to string", entity_id, type(state))
        return {
            "state": str(state) if state is not None else "",
            "attributes": {},
            "last_updated": None,
            "last_changed": None
        }
    
    @staticmethod
    def validate_entity_id(entity_id: str) -> bool:
        """Validate Home Assistant entity ID format.
        
        Args:
            entity_id: Entity ID to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(entity_id, str):
            return False
        
        if not entity_id:
            return False
        
        # Basic format check: domain.object_id
        if "." not in entity_id:
            return False
        
        parts = entity_id.split(".")
        if len(parts) != 2:
            return False
        
        domain, object_id = parts
        
        # Domain should be alphanumeric and underscore
        if not all(c.isalnum() or c == "_" for c in domain):
            return False
        
        # Object ID should be alphanumeric, underscore, and hyphen
        if not all(c.isalnum() or c in "_-" for c in object_id):
            return False
        
        return True
    
    @staticmethod
    def sanitize_entity_ids(entity_ids: List[str]) -> List[str]:
        """Sanitize a list of entity IDs, removing invalid ones.
        
        Args:
            entity_ids: List of entity IDs to sanitize
            
        Returns:
            List of valid entity IDs
        """
        if not isinstance(entity_ids, list):
            _LOGGER.warning("Entity IDs is not a list, converting to empty list")
            return []
        
        valid_ids = []
        for entity_id in entity_ids:
            if NeuronInputValidator.validate_entity_id(entity_id):
                valid_ids.append(entity_id)
            else:
                _LOGGER.debug("Skipping invalid entity ID: %s", entity_id)
        
        return valid_ids


def validate_and_normalize_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to validate and normalize evaluation context."""
    validator = NeuronInputValidator()
    return validator.validate_context(context)


def validate_ha_state(state: Any, entity_id: str) -> Dict[str, Any]:
    """Convenience function to validate and normalize HA state."""
    validator = NeuronInputValidator()
    return validator.validate_ha_state(state, entity_id)


def validate_entity_ids(entity_ids: List[str]) -> List[str]:
    """Convenience function to validate entity IDs."""
    validator = NeuronInputValidator()
    return validator.sanitize_entity_ids(entity_ids)