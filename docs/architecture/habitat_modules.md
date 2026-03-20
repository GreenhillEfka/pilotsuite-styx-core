# Habitat Modules and Neuron Input Pipeline

## Goal
PilotSuite Core should not process raw Home Assistant events directly as business logic. Instead, external systems connect through **Habitat Modules** that normalize inbound events into a shared Core input model.

## Core principle
- **Habitat Module** = external adapter layer
- **NeuronInput** = normalized event/input contract for the Core
- **Brain** = correlation, neuron evaluation, habitus inference, proposals/actions
- **Habitus** = interpreted situational state
- **Proposal / ActionIntent** = normalized outbound result

## Recommended flow
1. `HabitatModuleEvent`
2. `NeuronInput`
3. `Neuron evaluation`
4. `Brain analysis`
5. `Habitus state`
6. `ProposalIntent / ActionIntent`
7. `HabitatModuleCommand`

## First Habitat Module
The first official Habitat Module is:
- `homeassistant`

Responsibilities:
- ingest Home Assistant entities, areas, states, and events
- normalize signals into `NeuronInputV1`
- attach zone and tag context
- forward normalized inputs to the Core brain
- receive proposals/actions from Core
- return proposals/actions to Home Assistant

## Module-level schema
Each zone module override can carry:
- `module_category`
- `input_model`
- `pipeline_role`
- `input_adapter`
- `input_signals`
- `neuron_targets`
- `output_adapter`
- `output_mode`
- `autonomy_mode`
- `suggestion_mode`
- `direct_execution_enabled`
- `approval_required`
- `explanation_required`
- `priority`
- `notes`

## Autonomy semantics
- `autonomous`: may auto-execute if all participating neurons are autonomous
- `learning`: ask before execution
- `off`: suppress action

## Design note
Home Assistant is the first Habitat Module, not the brain itself. The Core remains the place where signals are evaluated, correlated, and turned into proposals or actions.
