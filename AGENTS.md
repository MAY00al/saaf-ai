# Working in SAAF

- Follow the phase order and acceptance criteria in ROADMAP.md. Wait for explicit approval before Phase 1. Phase 0 is documentation and scaffolding only.
- Preserve the two JSON inputs and their metadata. Read both `about` sections before changing ingestion or any interpretation of the data. Store generated indexes and databases separately.
- Ground scientific claims in approved knowledge records. Attach the source, evidence type, study conditions where supplied, and caveats. Preserve qualifiers such as “estimated” and “more than.” Treat unsupported claims as insufficient evidence.
- Apply `agent_rules_ar` to recommendations. Preserve the distinction between soil moisture, evaporation, and measured irrigation consumption. Present the study dose as a research reference and avoid translating it into a farm application amount without validated inputs and methodology.
- Label simulated farm inputs and every derived result as simulated. Carry field-level origin and measurement or estimation method when adding real inputs. Treat missing values as unknown.
- Keep secrets in environment variables, keep local derived state out of version control, and avoid logging farm data or credentials. Use dependency injection for external services and Pytest for repeatable checks.
- Introduce dependencies only in the phase that needs them. Train or evaluate a predictive model only with suitable, licensed data and a documented evaluation protocol.
- Commit or push only when the owner explicitly requests it.
