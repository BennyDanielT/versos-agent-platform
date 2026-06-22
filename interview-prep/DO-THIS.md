# DO-THIS

Read top to bottom. Do one box. Tick it. Next box. Don't skip ahead. Don't polish.

> Rule: working ugly beats pretty broken. Always have a thing that RUNS.
> Rule: stuck 10 min? Stop. Use the escape hatch. Move on.
> Rule: the sim is a black box. Wrap it. Do NOT read its guts.

---

## PHASE 0 — Calm start (first 5 min). Don't code yet.

- [ ] Breathe. Read the prompt twice. Slow.
- [ ] Say out loud in one line: "Agent must ____ the sim to reach ____."
- [ ] Find the 3 sim verbs: how to SEE state, how to ACT, how to know DONE.
- [ ] Write those 3 verbs on paper. That's it for now.

---

## PHASE 1 — Make the smallest thing run (next ~30 min)

Copy your skeleton. `interview-prep/agent_skeleton/`. It already works.

- [ ] Open `sim_adapter.py`. Point `observe` / `act` / `reset` at THEIR 3 verbs.
- [ ] Use a DUMB policy first (pick any valid action). No LLM yet.
- [ ] Run it. See one action hit the sim. **It runs = you are safe now.**
- [ ] Print every step (you already have `trace.py`). See the loop turn.

🚪 Stuck? Hardcode one action. Just prove the loop moves. Come back later.

---

## PHASE 2 — Make it smart (next ~30 min)

- [ ] Swap dumb policy for the LLM planner (`llm.py` -> `ClaudeLLM`, model `claude-opus-4-8`).
- [ ] LLM returns JSON only: `{reason, tool, args}`. Validate args BEFORE the sim.
- [ ] Add your real actions to `tools.py`. Small. Typed. Give each a risk.
- [ ] Run. Watch it reason -> pick -> act. Good enough. STOP adding tools.

🚪 Stuck on the LLM? Keep the dumb policy. A working dumb agent > a broken smart one.

---

## PHASE 3 — Make it safe + explainable (next ~20 min)

This is where points live. Don't skip.

- [ ] Turn on the gate (`gate.py`): low/med = auto, high = ask human.
- [ ] Add the 3 loop guards: MAX_STEPS, done-check, reject-bad-action-and-continue.
- [ ] Confirm the trace log reads like a story: saw X, thought Y, did Z.

---

## PHASE 4 — Prove it works (next ~15 min)

- [ ] Pick ONE number: did it reach the goal? how many steps? (`trace.summary()`).
- [ ] Run 3 times. Write the numbers down.
- [ ] Break it on purpose ONCE: flip kill switch -> show agent stops acting, keeps thinking.

---

## PHASE 5 — Stop building. Get ready to talk (last 15 min)

- [ ] STOP CODING. Hands off. Whatever runs, runs.
- [ ] Open the trace output. That's your demo screen.
- [ ] Say the one-line bet out loud once: see SAY-THIS below.

---

## SAY-THIS (your script — memorize the first line)

1. "My bet: the LLM is the **planner**, not the executor. Every action is typed, gated, logged before it touches the sim."
2. "Only the **adapter** knows the sim's API. If the sim changes, one file changes."
3. "The **gate** holds risky actions for a human. Watch —" (flip kill switch).
4. "Here's the **trace**: it saw this, reasoned this, acted. That's the why."
5. "My **number**: reached goal in N steps, X out of 3 runs."
6. "With more time: memory across runs. I skipped auth/multi-agent on purpose — no points at this scope."

---

## IF EVERYTHING BREAKS (panic button)

- Go back to the last box that ticked. Run that. Demo THAT.
- A small thing that runs + a clear story BEATS a big thing that crashes.
- You already have a working skeleton. You can always fall back to it.

---

## DON'T (the rabbit holes)

- ❌ Don't make the sim fancier. Not your job.
- ❌ Don't add a 6th tool. 4 is plenty.
- ❌ Don't build UI unless code is DONE and time is left.
- ❌ Don't refactor for pretty. Ugly + running wins.
- ❌ Don't chase one bug past 10 min. Escape hatch. Move.
