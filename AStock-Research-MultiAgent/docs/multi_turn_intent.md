# Multi-turn intent and dialogue state

The Web backend resolves every user turn before choosing a direct MCP tool or
the existing research workflow.  The four specialist agents and the MCP tool
protocol are unchanged.

## Runtime flow

```text
current utterance + recent messages + durable task state
                         |
                 structured intent parser
                         |
              deterministic security validation
                         |
                 pure state reducer
                  /             \
       clarify/cancel          contextual planner
                                  |
                     direct tool or existing agents
                                  |
                         compact result reference
```

`DialogueGraph` uses a LangGraph checkpointer scoped by `session_id`.  A compact
state projection is also stored in the Web SQLite database, allowing a new
backend process to seed a fresh graph after restart.  Reports and raw tool
responses are not copied into checkpoints.

## State update semantics

- `retain`: keep the previous value because the field was not changed.
- `replace`: replace the complete field with the supplied value.
- `append`: add values without duplicates.
- `clear`: explicitly remove the inherited value.

Task transitions are `new`, `continue`, `refine`, `switch`, `cancel`, and
`resume`.  A switch snapshots the old task and clears stock-scoped fields before
applying the new patch.

## API visibility

- Task `intent` payloads include `intent_change`, `state_patch`,
  `active_task_id`, `dialogue_state_version`, and `selected_agents`.
- `GET /api/sessions/{session_id}/state` returns the current durable projection.
- SSE emits `dialogue.state.updated` and, after a successful execution,
  `dialogue.result.recorded`.

## Offline evaluation

Run the dialogue regression benchmark without an LLM or live data calls:

```powershell
& '..\.venv\Scripts\python.exe' -m evaluation.run_multiturn_benchmark `
  --output evaluation/results/multiturn_smoke.json
```

The initial file contains 12 dialogues and 24 turns.  It is a deterministic
regression/smoke set, not an independent estimate of model generalization.
Keep held-out dialogues separate when reporting resume metrics.
