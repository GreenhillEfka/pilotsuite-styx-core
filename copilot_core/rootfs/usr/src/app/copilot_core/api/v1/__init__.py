# API v1 Module — Complete Route Registration
from . import backend_ui_v2
from . import backend_ui
from . import habitus_zone
from . import habitus_admin
from . import room_context
from . import room_context_admin
from . import device_link
from . import device_link_admin
from . import presence_entity
from . import presence_entity_admin
from . import intent_manager
from . import intent_manager_admin
from . import action_executor
from . import action_executor_admin
from . import event_bus
from . import event_bus_admin
from . import learning_memory
from . import learning_memory_admin
from . import scenes_api
from . import registry_blueprints
from . import sync_api

__all__ = [
    'backend_ui_v2', 'backend_ui',
    'habitus_zone', 'habitus_admin',
    'room_context', 'room_context_admin',
    'device_link', 'device_link_admin',
    'presence_entity', 'presence_entity_admin',
    'intent_manager', 'intent_manager_admin',
    'action_executor', 'action_executor_admin',
    'event_bus', 'event_bus_admin',
    'learning_memory', 'learning_memory_admin',
    'scenes_api',
    'sync_api',
    'registry_blueprints',
]