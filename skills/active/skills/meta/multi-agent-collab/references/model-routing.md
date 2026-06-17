# Model Routing

Use model profiles to describe required capability without hard-coding host-specific model names.

## Profiles

| model_profile | Use for | Reasoning need | Cost/latency bias |
|---------------|---------|----------------|-------------------|
| `fast_probe` | File search, symbol lookup, simple config checks, quick evidence gathering | low to medium | fast and cheap |
| `deep_research` | Complex root cause, cross-module reasoning, ambiguous evidence, multi-hypothesis analysis | high | accuracy over speed |
| `code_worker` | Bounded implementation, local refactor, targeted tests | medium to high | balanced |
| `reviewer` | Bug review, regression risk, test gap analysis, acceptance review | high | accuracy over speed |
| `integrator` | Conflict arbitration, multi-handoff synthesis, final acceptance judgment | high to max available | accuracy over speed |

## Host Mapping

Map profiles to the best available controls in the current host:
- If model selection is available, choose the model that best fits the profile.
- If reasoning controls are available, choose the closest reasoning level.
- If neither is available, use the default model and keep `model_profile` in the prompt so the role intent remains clear.

## Routing Rules

- Do not use a stronger profile only because multiple agents are available.
- Use `fast_probe` for bounded read-only inventory.
- Escalate to `deep_research` when evidence is contradictory, cross-system, or root-cause heavy.
- Use `code_worker` only after ownership is clear.
- Use `reviewer` only after there is a concrete target: diff, handoff, file list, or evidence bundle.
- Use `integrator` only when there are multiple handoffs, conflicts, or a final cross-module decision.

## Fallback

When the host cannot route models:
1. Preserve the `model_profile` field.
2. Reduce task scope to fit the default model.
3. Prefer stronger handoff evidence over relying on model capability.
