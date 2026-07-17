# Cover Letter — Ascend (AI / Agentic Product Engineer)

Dear Ascend Hiring Team,

Reinventing document-heavy, high-stakes workflows by hiding them behind a chat-first
interface is exactly the problem I've been building toward — and it's the problem I find
genuinely exciting. Your posting reads like a checklist of the two things I care most about:
shipping production-grade LLM agents, and doing it with real frontend craft so the power
actually reaches a user's fingertips. Most people are strong at one or the other. I've spent
my recent work deliberately at the seam between them.

The clearest evidence is a system I built end-to-end: an agent-ops platform (Python + NVIDIA
NeMo Agent Toolkit + Postgres) where a support-triage agent *graduates* from **suggest →
human-approved → autonomous** only as evidence accumulates. It's not a demo with mocks — it
runs. What I think maps directly to what you're hiring for:

- **Agentic workflows with safe tool invocation.** The agent produces structured output, but
  code — not the model — decides autonomy from a human-owned policy table. Every decision is
  logged and auditable. That's the "safe and auditable from day one" tool layer you describe,
  built the way I'd build it here: guardrails in the inference path, not bolted on after.

- **Evaluation as first-class code.** I own the whole eval stack in that project — an offline
  golden-set eval plus online SQL views over live reviews and CSAT — with a scheduled promotion
  job that only advances a segment's autonomy when the metrics clear a human-set bar, and a kill
  switch to bound blast radius. Your "prototype in hours, A/B with real metrics, roll back with
  confidence" is the discipline I already reach for.

- **Guardrails and trust.** Layered guardrails per stage, policy-as-data, and a monitoring job
  watching for regressions. I think about red-team surface, PII, and role-based access as design
  inputs, not afterthoughts.

On the frontend side, which your qualifications rightly weigh heavily: I work daily in
AI-assisted coding tools (Claude Code, Cursor) — not as a novelty but as how I move fast — and
I care about the craft of UI engineering: TypeScript and modern React, component-driven
architecture and design systems, responsive and accessible (WCAG) interfaces, and frontend
performance as a feature, not a cleanup task. The "developer canvas / playground" you want to
ship — an internal surface where PMs and engineers compose and test agent chains without local
setup — is the kind of thing I'd genuinely enjoy owning, because it's where clean UI and agent
plumbing meet.

What draws me to Ascend specifically is the combination: deep domain workflows that matter,
short idea-to-user cycles, and a stated commitment (via Alpine) to empowerment, intellectual
honesty, and fairness. I do my best work close to real users, translating fuzzy pain into
concrete agent capabilities and shipping in hours or days — then measuring whether it actually
helped. That loop is what I want to keep doing, and it's what your role is built around.

I'd welcome the chance to walk through the platform above and talk about how I'd approach the
context engine, the tooling layer, and the playground for your team.

Thank you for your consideration.

Warm regards,
Benny Daniel
benny28dany@gmail.com
