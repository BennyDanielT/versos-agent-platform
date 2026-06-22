# POCKET-CARD — keep this ONE file open the whole time

## HOW TO PROMPT CLAUDE (so you don't drown)

Paste this at the top of build prompts:
> "One file. Code only. Max 3 lines explain. No alternatives. If unsure, pick the standard way and do it."

- One thing at a time. "Write the adapter." Not "help me build the agent."
- Gives you options? Reply: "Just pick one and do it."
- Don't read its reasoning. Grab the code, paste, run. Read only if it BREAKS.
- 10 min, still no run? Drop Claude. Write the dumb version yourself.

---

## DEMO TALK TRACK — read these out loud, in order. Don't trust memory.

1. "My bet: the LLM is the **planner**, not the executor. Every action is typed, gated, and logged before it touches the sim."
2. "Only the **adapter** knows the sim's API — sim changes, one file changes."
3. "Small set of **typed tools**. Bad/hallucinated args get rejected before the sim sees them."
4. "The **gate** holds risky actions for a human. Watch —" → flip kill switch → "it keeps reasoning, stops acting."
5. "Here's the **trace**: saw this → reasoned this → acted. That's the *why*."
6. "My **number**: reached goal in N steps, X/3 runs."
7. "More time: memory across runs. Skipped auth + multi-agent on purpose — no points at this scope."

---

## IF I BLANK
- Just read line 1 above. Then point at the trace and describe what it did.
- "Let me show you" + run it > trying to explain from memory.

## IF IT BREAKS
- Go to last thing that ran. Demo THAT. Small + runs > big + crashes.
