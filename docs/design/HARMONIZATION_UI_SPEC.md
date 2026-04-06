# Harmonization UI: Cross-Module Logic Visualisation

**Status:** Finalized (2026-04-06)
**Owner:** DesignClaw
**Core-Worktree:** pilotsuite-styx-core-current

## 1. Overview
This document specifies how cross-module intelligence (Harmonization) is represented in the Backend UI. The goal is to make "Emergent Behaviour" transparent.

## 2. Component: The Intelligence Linker
- **Visual:** Smooth lines (SVG Bezier) connecting module tiles in the Zone View.
- **Color Coding:**
  - **Blue:** Optimization (e.g., Energy/Climate)
  - **Gold:** Comfort (e.g., Adaptive Lighting)
  - **Red:** Security (e.g., Alarm Sensitivity)

## 3. Interaction: The "Reasoning Bubble"
When a user hovers over an entity changed by cross-module logic:
- **Pop-over:** "Changed by [Harmonization Rule ID] because [Condition from Module B]."
- **Button:** "Disable this link for this zone."

## 4. Admin View: Harmonization Matrix
A dedicated table showing all active cross-module rules:
| Trigger Module | Target Module | Rule Name | Active Status | Success Rate |
| :--- | :--- | :--- | :--- | :--- |
| Climate | Lighting | Warm Glow on Heat | Enabled | 98% |
| Presence | Alarm | Confidence Guard | Enabled | 100% |

## 5. Success Signal
Users can trace every automated action back to its source module and the specific harmonization rule that triggered it.
