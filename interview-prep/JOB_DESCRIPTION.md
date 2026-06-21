# Versos AI — Lead Agentic Engineer (the actual JD)

> Saved verbatim from the posting so it's not lost. Build/compare against THIS.
> See `interview-step-by-step.md` → "DAY-OF STRATEGY" for the spine + JD-alignment cheat-sheet,
> and `my-technical-qa.md` Q47/Q48 for gaps-to-speak-to and the alignment map.

Versos AI brings "The World" to the world models. We do this by collecting and processing AI
training data in multiple modalities. We currently run two main technical surfaces: a
high-throughput data processing pipeline (versos-processor) and a data marketplace, along with the
customer engagements that sit on top of it. Four techs split two and two. We ship fast, we own
production, and we've reached the point where the next unit of leverage will rest on an agent swarm
orchestrated by a pair of capable human hands.

## The Role
We're hiring our fifth engineer to build and own that layer.

You will design, deploy, monitor, audit, and continuously improve a fleet of agents whose job it is
to run, watch, and repair Versos services. On day one, this looks like agents that catch the kind of
issues we currently fix by hand: missing indexes, slow queries, broken jobs, stale data,
customer-visible regressions.

By the end of year one, it looks like an orchestration substrate where most routine production work
(triage, remediation, productization of new algorithms) will reside. customer support is executed,
and verified by agents, with humans reviewing exceptions and steering policy rather than tending to
tickets.

We call the destination dark-factory operations: the company runs, mostly, while no one is watching.
You are the person who builds our path there.

## What you'll do
- **Stand up and operate an agent platform.** Choose the orchestration primitives (frameworks, tool
  layers, sandboxes, eval harnesses), wire them into our infra, and own the platform as a first-class
  production system.
- **Ship agents into the loop.** Start with high-leverage, well-bounded jobs (incident triage, schema
  and index hygiene, cost watchers, data-quality auditors, pipeline self-healers) and graduate them
  from suggest-only, to human-approved, to autonomous as evidence accumulates and comfort zone builds up.
- **Build the audit and trust layer.** Logs, traces, replays, evals, regression suites, kill switches,
  blast-radius controls. We will only move agents toward autonomy as fast as our ability to prove
  they're behaving, and that proof is your work product too.
- **Productize new algorithms quickly.** As the team develops new methods, you wrap them in agentic
  interfaces so they reach customers and internal users in days, not quarters.
- **Push the frontier.** Keep us honest about what's actually possible at the leading edge each month,
  and continually retire abstractions you built months ago when something better lands.
- **Force-multiply the existing team.** Your success is measured by what the rest of the team stops
  having to do.

## Who you are
- A deep, strategic thinker and a tireless builder. You think in systems and abstractions, not
  scripts. You can hold the whole stack (model, tools, orchestration, infra, product) in your head and
  pick the right layer to intervene at.
- Strong production engineering background. You've built and operated non-trivial distributed systems,
  and you have the instincts of someone who has been paged at 3am and learned from it. Comfortable
  across backend, data, and infra.
- Fluent with modern agent tooling: structured outputs, evals, agent frameworks, sandboxed execution,
  retrieval, prompt and context engineering. You don't need to have used the specific stack we land
  on. You need to be able to evaluate many of them and make the right call.
- Good intuition about autonomy. You know when an agent is ready to act unsupervised and when it
  isn't, and you build the instrumentation that makes the answer justifiable to others.
- Bias toward shipping. You prefer one agent in production catching real bugs to three perfect ones in
  a notebook.
- High ownership. This is a small team; the role spans research, engineering, and ops. You're
  energized by that, not bothered or intimidated by it.

## Nice to have
- Experience operating LLM systems at scale (cost, latency, reliability, drift).
- Background in data infrastructure, pipelines, or marketplaces as well as data science and machine
  learning ops.
- A track record of replacing human processes with automated ones, and being honest about when it
  didn't work.
- Open-source contributions to agent frameworks, eval tooling, or orchestration layers.
