# Built-in skill worst-case review

These reviews apply to the two bundled skills. A new skill should add a matching review before it is enabled.

## `demo`

- **Worst case:** untrusted arguments are echoed into logs or a future UI, or a future maintainer replaces the harmless critical demonstration with an external side effect.
- **Guards:** echo accepts only a string up to 4,000 characters; request bodies and tool arguments are not written to the audit log; the critical demonstration is marked critical and requires one-time approval; the current action explicitly makes no external changes.
- **Residual risk:** output can still contain malicious text. Any future renderer must escape it, and any replacement action needs its own review and an approval gate.

## `system`

- **Worst case:** status or time access becomes a broader host inspection or reveals sensitive system details.
- **Guards:** the skill is read-only, has only two declared tools, and returns a small status object and local timestamp. It does not read files, environment variables, or process details.
- **Residual risk:** the local time string can reveal the machine's timezone. Do not add more telemetry without documenting fields and applying least privilege.

## Core execution boundary

All skill code runs in the JARVIS process with the current user's operating-system rights. Manifests and permission tiers are application-level controls, not an OS sandbox. Install only trusted skills; validate inputs in each skill; declare sensitive actions as high risk or critical; write audit records before side effects; make actions idempotent or reversible where practical; and add a dedicated failure review and tests for each new skill.
