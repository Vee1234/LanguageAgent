# Game Plan: A Triggered Multi-Agent Language Learning System

**The target architecture**, so you know what you're building toward: three domain agents (Articles, Vocabulary, Grammar), each with their own scope, tools, and memory — plus an orchestration layer that lets one agent's finished work *trigger* another agent's task automatically. The Articles agent isn't just "a feature," it's the one that kicks the other two into motion when it finds something worth teaching. That triggering mechanism — not any single capability — is the actual hard problem here, and it's deliberately Phase 4, not Phase 1, because you need working, well-scoped agents to trigger *before* triggering itself makes sense to build.

Every phase below has: a **decision point** (the actual judgment call, with the real trade-offs — not a false choice), a **suggested starting point** (one reasonable way to build it, so you're not staring at a blank page), and a **deliverable** (something working, not something read).


## Phase 0 — Decide the architecture before writing anything
**Deliverable**: a one-page written design doc. No code yet.

**The decision**: how many separate "things" does this system actually have, and what does each one own?
- Do Articles, Vocabulary, and Grammar need to be three separate agents, or could this start as one agent with three Skills? (Hint for later phases: yes, separate — but decide *why*, not just because I said so. What's different about their tool needs? Their memory? Would giving the Vocabulary agent write-access to your grammar weak-point tracker ever be a mistake?)
- Who owns state? Sketch, roughly: does each domain get its own memory, or is there one shared store all three read/write?
- What triggers what? Even roughly: does Articles → Vocabulary happen automatically, or does Articles just produce a resource you hand to Vocabulary yourself for now?

**Suggested starting point**: three domains, three separate memory scopes to start (merge later if it turns out to be a mistake — easier to merge than to un-tangle), one shared "vocabulary encountered" log that Articles writes to and Vocabulary reads from.

**Deliverable**: your design doc, plus one sentence per domain: "this agent owns ___, and needs tool access to ___."

---

## Phase 1 — Vocabulary, alone, no subagents yet
**Deliverable**: a working vocabulary conversation you'd actually use, with no multi-agent machinery.

**The decision**: does this need a subagent at all yet?
No. This is the phase that proves the discipline from earlier in this conversation — don't reach for delegation before a single well-configured agent is insufficient. One session, tools, memory, and a Skill is enough for real depth here.

**Suggested starting point**:
- Connect one MCP server for real lexical data — a dictionary/thesaurus API, not Claude's own knowledge alone, so etymology and register data is grounded rather than guessed
- A Skill encoding exactly what "active, not passive" means to you: always ends in "now use this in a sentence about ___," never just a definition dump
- Memory tracking every word covered, so week 3 doesn't re-teach week 1's word
- Practice: ask Claude to actively quiz you on register/connotation ("would a lawyer or a friend use this word?") rather than you asking it questions

**Deliverable**: one real vocabulary session, end to end, covering etymology, synonyms, register, and at least one active-production exercise — using your MCP-connected source, not memory alone.

---

## Phase 2 — Grammar, as your first genuinely separate agent
**Deliverable**: a Grammar capability that corrects you and gives targeted lessons, built as a distinct scoped agent from Vocabulary.

**The decision**: subagent of the same session, or a fully separate top-level agent?
Real trade-off, not obvious: a subagent is cheaper to set up and shares your main session's context automatically. A separate top-level agent has its own isolated context and memory, and doesn't accidentally see your vocabulary conversation history. Ask yourself: does Grammar *benefit* from knowing what words you've been studying (probably yes — sentence-level correction is more useful with vocab context), or does it need isolation to work correctly on its own scope (probably not, here)? This is a case where the "correct" answer might actually be a subagent *with read access to Vocabulary's memory* — a middle option worth considering rather than defaulting to full separation just because Phase 0 said "separate."

**Suggested starting point**: a subagent, read access to the Vocabulary memory store, its own write-access memory for tracking your recurring grammar weak points (which tenses you get wrong, which registers you conflate).

**Deliverable**: paste in something you wrote (a sentence, a paragraph), get corrected, and get one targeted mini-lesson generated specifically from a pattern in your actual mistakes — not a generic grammar topic.

---

## Phase 3 — Articles, and your first real MCP ingestion + fan-out
**Deliverable**: an Articles agent that pulls real content and generates first-draft resources — not yet wired to trigger anything else.

**The decision**: one article at a time via a tool call, or fan-out for a backlog?
Depends entirely on volume. Pulling and discussing one article together is just tool use (web fetch, or a scraping MCP server) — no fan-out needed. But if you want to seed the system with, say, 15 articles from a site you like, processing them one at a time is slow and each one is genuinely independent — that's the actual test for "does this deserve fan-out" from earlier in this conversation.

**Suggested starting point**: an MCP server (or the web-fetch server tool) for pulling articles; work through one live, together, to nail the "analyze with me" interaction before automating anything; then trigger a fan-out workflow ("workflow: pull and analyze these 10 articles, extract vocab and grammar-worthy sentences from each") once the single-article flow is solid.

**Deliverable**: one article, pulled and discussed live, producing an actual vocab list and a set of grammar-notable sentences as output — plus, separately, one successful fan-out run across a small backlog.

---

## Phase 4 — Wire the trigger: agents that start because another agent finished
**Deliverable**: Articles finishing an analysis automatically kicks off Vocabulary and Grammar work — the thing you said you most want to learn.

**The decision**: this is the real one. Three genuinely different mechanisms exist, and picking wrong means rebuilding later:
- **A hook** — fires deterministically on an event (e.g. "Articles agent's task completed") and dispatches a subagent. Best when the trigger condition is simple and you want a guarantee, not a maybe.
- **Cross-session messaging / agent teams** — Articles, Vocabulary, and Grammar run as separate, longer-lived sessions that message each other directly. Best when the agents are genuinely independent, long-running things, not one-shot dispatches.
- **MCP channels / webhooks** — an external event (a new article appearing in an RSS feed, not something you triggered) pushes into a running session. Best when the trigger originates *outside* your own agent system entirely.

Ask yourself: is the trigger "Articles finished, now do X" (internal, deterministic — hook territory) or "a new article showed up somewhere" (external — channel/webhook territory)? For most of what you described, it's the former to start.

**Suggested starting point**: a hook on Articles' completion that dispatches the Vocabulary subagent with the new words found, and separately dispatches the Grammar subagent with any notable sentences — both firing off the same completion event, running in parallel rather than sequentially since they don't depend on each other's output.

**Deliverable**: pull one article, and *without you doing anything else*, watch Vocabulary and Grammar material get generated from it automatically.

---

## Phase 5 — Fix the shared state problem
**Deliverable**: one coherent state layer all three agents read/write to correctly, with no silent overwrites.

**The decision**: now that agents are triggering each other and writing concurrently, the "who owns writes" question from Phase 0 gets real. Plain files risk one agent's write clobbering another's if they fire close together. Options: keep domains' memory strictly separate (safest, but loses cross-domain insight — e.g. Grammar noticing a word Vocabulary flagged), or a single structured store (an MCP-connected lightweight database) with clear per-field ownership so agents can read broadly but only write their own lane.

**Suggested starting point**: separate memory per domain (as in Phase 0), plus one shared, append-only log of "vocabulary encountered" that only Articles and Vocabulary write to, that Grammar can read from but never writes to — avoids races by having exactly one writer per piece of shared state.

**Deliverable**: run the Phase 4 trigger chain twice in a row and confirm nothing got silently overwritten or duplicated.

---

## Phase 6 — Make the whole loop run without you starting it
**Deliverable**: a daily cycle — new article in, all three agents run, a briefing and quiz land in front of you — with no session opened by hand.

**The decision**: session-scoped (`/loop`, `/goal`) or persistent (Scheduled Task / Routine)? This only needs to survive your session if you're actively supervising it; it needs to be persistent if the whole point is "this happens whether or not I'm at my desk," which — given you want a daily habit — it does.

**Suggested starting point**: a persistent Routine that pulls one new article each morning, runs the Phase 4 trigger chain, and delivers you a short briefing plus an active-recall quiz — the daily version of what Phase 3–5 built, now unattended.

**Deliverable**: one morning where the system already did the work before you opened anything.

---

## Phase 7 — Extract it as a standalone system, and decide who should run it
**Deliverable**: the orchestration logic (the "what triggers what" layer from Phase 4) rebuilt with the Agent SDK, outside Claude Code.

**The decision**: hand-build the orchestration yourself (Agent SDK — full control over exactly when Vocabulary and Grammar fire, how state is shared, how retries work) or lean on Managed Agents' built-in multi-agent orchestration, memory, and webhooks (less code, less control, Anthropic runs the harness)? Weigh it on what actually matters here: do you want fine-grained control over the trigger logic you just designed in Phase 4, or would you rather Anthropic's platform handle scaling, retries, and persistence for you? There's a real case for Managed Agents specifically for the "grade my grammar correction quality" piece — that's close to what Outcomes (rubric + independent grader) is built for.

**Suggested starting point**: rebuild it yourself first with the SDK, specifically because you learn more by owning the trigger logic once — you can always migrate the running system to Managed Agents later once you know exactly what you'd be delegating away.

**Deliverable**: the same Phase 4 trigger chain, running as standalone code, independent of a Claude Code session.

---

## Phase 8 — Your decision log (the actual point of this whole plan)
**Deliverable**: not code. A written record of every real decision you made across Phases 0–7, and why.

At minimum, capture your answers to: subagent vs. separate top-level agent (Phase 2), fan-out vs. sequential (Phase 3), hook vs. cross-session messaging vs. webhook (Phase 4), separated vs. shared state (Phase 5), session-scoped vs. persistent (Phase 6), build vs. configure (Phase 7) — each with the actual reasoning, not just the choice.

This document is the transferable skill. The language-learning system is real and you'll keep using it, but the decision log is what you take into the *next* system you build, on a completely different problem, where none of this exact code applies but every one of these judgment calls will come up again.