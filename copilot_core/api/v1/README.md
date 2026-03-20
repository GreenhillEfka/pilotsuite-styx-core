# Module Configuration API

This API provides endpoints for managing module configurations in the PilotSuite system. Each module represents a functional component that can be triggered by specific conditions and execute actions based on those triggers.

## Module Types

The system supports 7 distinct module types:

1. **LIGHT** - Lighting control modules
2. **AUDIO** - Audio/entertainment system modules
3. **CLIMATE** - Climate/HVAC control modules
4. **COVER** - Cover/curtain control modules
5. **ENERGY** - Energy monitoring and management modules
6. **SCENE** - Scene activation modules that coordinate multiple devices
7. **SECURITY** - Security and surveillance modules

## Core Components

### Triggers
Triggers define the conditions under which a module should activate. Each trigger consists of:
- Unique ID
- Human-readable name
- Optional description
- Conditions (expressed as key-value pairs)

### Actions
Actions define what happens when a trigger is activated. Each action consists of:
- Unique ID
- Human-readable name
- Optional description
- Parameters (expressed as key-value pairs)

### Zone Overrides
Zone overrides allow customization of module behavior for specific zones/areas:
- Zone identifier
- Enabled status
- Zone-specific settings

### Priority Rules
Priority rules determine how conflicts between modules are resolved:
- Unique ID
- Human-readable name
- Condition for when rule applies
- Priority level (higher number = higher priority)
- Action to take when rule applies

## API Endpoints

### GET `/module-config/schema`
Retrieve all module configurations in the system.

### GET `/module-config/{module_id}`
Retrieve configuration for a specific module by ID.

### POST `/module-config/`
Create a new module configuration.

### PUT `/module-config/{module_id}`
Update an existing module configuration.

### DELETE `/module-config/{module_id}`
Delete a module configuration.

## Data Models

All data models are defined using Pydantic for validation and serialization. See `module_config.py` for the complete implementation.

## Example Usage

The system is initialized with example configurations for each module type to demonstrate proper usage patterns.