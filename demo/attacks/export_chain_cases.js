// Export one review case per (chain attack x applicable v3 task) for the human review desk.
// Exploratory, like chain_attacks.js: it reuses demo/engine.js and the attack hooks and adds
// nothing to the frozen v3 protocol.
//
// For every case it records what the attack changes (before -> after), the agent's first
// plan with and without the attack, the guard's events and the oracle's outcome under
// B0, B2 and M_full, and the same conditions without any attack.
//
// Usage: node demo/attacks/export_chain_cases.js [bundle.js] [out.json]
"use strict";
const path = require("path");
const fs = require("fs");
const vm = require("vm");
const E = require(path.join(__dirname, "..", "engine.js"));
const A = require(path.join(__dirname, "chain_attacks.js"));

const bundlePath = process.argv[2] || path.join(__dirname, "..", "data", "bundle.js");
const outPath = process.argv[3] || null;
const ctx = { window: {} };
vm.runInNewContext(fs.readFileSync(bundlePath, "utf8"), ctx);
const D = ctx.window.EVIBOUND_DATA;
const params = { maxAge: D.constants.max_observation_age, maxWrites: D.constants.max_writes,
  clockStep: D.constants.write_clock_step, startClock: D.constants.start_clock, recordTimes: D.constants.record_times };
const CONDITIONS = ["B0", "B2", "M_full"];
// The scripted agent. "careful" follows what it reads and keeps every rule, so any harm it
// causes comes from the attack. Three attacks only bite an agent that makes mistakes of its
// own: forged feedback needs a rejected write first, and a misreported or widened scope only
// matters to an agent that writes the device it was told it may use. Those use "hasty",
// which plans the whole goal and jumps levels. Text injections replace the reply (worst case).
const HASTY = new Set(["H7-feedback-forgery", "H5-scope-misreport", "H9-scope-widen"]);
const personaFor = (attack) => (HASTY.has(attack.id) ? "hasty" : "careful");
const NONE = A.ATTACKS.find((a) => a.id === "none");
const clone = (x) => (x === undefined ? x : JSON.parse(JSON.stringify(x)));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function without(attack, keys) {
  const hooks = Object.assign({}, attack.hooks || {});
  keys.forEach((k) => delete hooks[k]);
  return Object.assign({}, attack, { hooks, obeysFeedback: keys.includes("feedback") ? false : attack.obeysFeedback });
}
function plan(raw) {
  const r = E.parseResponse(raw || "");
  const d = r.parsed || {};
  return { actions: Array.isArray(d.actions) ? d.actions.map((a) => ({ device: a.device, value: a.value })) : null,
    evidence: d.evidence ? { id: d.evidence.id, value: d.evidence.value, observed_at: d.evidence.observed_at } : null };
}
function record(r) { return r ? { id: r.id, value: clone(r.value), observed_at: r.observed_at, epoch: r.epoch } : null; }
function events(trace) {
  return (trace.events || []).filter((e) => e.kind === "write" || e.kind === "reject")
    .map((e) => ({ kind: e.kind, device: e.device, value: e.value, reason: e.reason, bypass: e.condition === "bypass",
      before: { light: e.before.light, fan: e.before.fan }, after: { light: e.after.light, fan: e.after.fan } }));
}
function outcome(scenario, run) {
  const m = run.metrics;
  return { unsafe_effect: m.unsafe_effect, authorization_violation: m.authorization_violation,
    goal_completion: m.goal_completion, safe_completion: m.safe_completion,
    hijacked: A.hijacked(scenario, m), final_state: { light: m.final_state.light, fan: m.final_state.fan },
    executed_writes: m.executed_writes, rejected_proposals: m.rejected_proposals,
    rejection_reasons: m.rejection_reasons, events: events(run.trace), trigger: run.trigger };
}

/* What the attack changes in this task, as before -> after pairs. */
function changes(sc, attack, PERSONA) {
  const h = attack.hooks || {};
  const out = [];
  const tcb = h.tcbScenario ? h.tcbScenario(sc) : sc;
  const agent = h.agentScenario ? h.agentScenario(tcb) : tcb;
  if (agent.instruction !== sc.instruction)
    out.push({ field: "instruction", before: sc.instruction, after: agent.instruction,
      added: agent.instruction.startsWith(sc.instruction) ? agent.instruction.slice(sc.instruction.length) : null });
  if (!same(agent.authorized, tcb.authorized))
    out.push({ field: "agent_authorized", before: tcb.authorized.slice(), after: agent.authorized.slice() });
  if (!same(tcb.authorized, sc.authorized))
    out.push({ field: "guard_authorized", before: sc.authorized.slice(), after: tcb.authorized.slice() });
  if (h.prompts) {
    const p2 = h.prompts(D.prompts);
    out.push({ field: "system_prompt", added: p2.system.startsWith(D.prompts.system) ? p2.system.slice(D.prompts.system.length) : p2.system });
  }
  if (attack.params) for (const [k, v] of Object.entries(attack.params))
    out.push({ field: "param", name: k, before: params[k], after: v });
  const w = new E.World(tcb, "clean", Object.assign({}, params, attack.params || {}));
  const recordsBefore = clone(w.records);
  if (h.world) h.world(w, E);
  for (const id of Object.keys(recordsBefore))
    if (!same(recordsBefore[id], w.records[id])) out.push({ field: "record", id, before: record(recordsBefore[id]), after: record(w.records[id]) });
  const authentic = w.observe();
  if (h.observation) {
    const delivered = h.observation(authentic, w, E);
    out.push({ field: "observation", before: record(authentic), after: record(delivered),
      source: delivered.id === authentic.id ? "same_id" : (w.records[delivered.id] ? "other_record" : "missing_id") });
  }
  if (h.bypass) out.push({ field: "bypass", writes: [{ device: "light", value: "high" }, { device: "fan", value: "high" }] });
  return out;
}

const cases = [];
for (const attack of A.ATTACKS) {
  if (attack.id === "none" || attack.run === false) continue;
  const h = attack.hooks || {};
  const PERSONA = personaFor(attack);
  for (const sc of D.scenarios.filter((s) => !attack.applies || attack.applies(s))) {
    const runs = {}, base = {};
    for (const c of CONDITIONS) {
      runs[c] = A.runChainEpisode(E, sc, c, PERSONA, attack, D.prompts, params);
      base[c] = A.runChainEpisode(E, sc, c, PERSONA, NONE, D.prompts, params);
    }
    const ref = runs.M_full;
    const ch = changes(sc, attack, PERSONA);
    // The model's reply: what this planner would have sent, and what reached the guard.
    if (h.raw || h.swap) {
      const own = A.runChainEpisode(E, sc, "M_full", PERSONA, without(attack, ["raw", "swap"]), D.prompts, params);
      ch.push({ field: h.swap ? "reply_swap" : "reply_injected", before: plan(own.raw0), after: plan(ref.raw0) });
    }
    // Feedback and re-read, on the guarded run that triggered recovery.
    if (h.feedback || h.fresh) {
      const c = ["M_full", "B2"].find((k) => runs[k].feedback) || "M_full";
      const plain = A.runChainEpisode(E, sc, c, PERSONA, without(attack, ["feedback", "fresh"]), D.prompts, params);
      const f0 = plain.feedback, f1 = runs[c].feedback;
      if (f0 && f1) {
        if (h.fresh || !same(f0.fresh_observation, f1.fresh_observation))
          ch.push({ field: "reread", condition: c, before: record(f0.fresh_observation), after: record(f1.fresh_observation) });
        if (h.feedback) ch.push({ field: "feedback_menu", condition: c, before: f0.legal_writes_now || null, after: f1.legal_writes_now || null,
          before_note: f0.rule_explanation || null, after_note: f1.rule_explanation || null });
      } else ch.push({ field: "feedback_unused", note: "no guarded condition rejected a write, so no feedback was sent" });
    }
    cases.push({
      attack: attack.id, hop: attack.hop, planner: PERSONA, task_id: sc.task_id, split: sc.split, family: sc.family,
      modality: sc.observation.modality, perturbation_in_v3: sc.perturbation, authorized: sc.authorized.slice(),
      presence: sc.initial.presence, initial: { light: sc.initial.light, fan: sc.initial.fan },
      goal_present: sc.goal_present, goal_absent: sc.goal_absent, instruction: sc.instruction,
      payloads: { present: clone(sc.observation.payload_present), absent: clone(sc.observation.payload_absent) },
      hijack_eligible: A.hijackEligible(sc), changes: ch,
      plan_without_attack: plan(base.M_full.raw0), plan_with_attack: plan(ref.raw0),
      outcomes: Object.fromEntries(CONDITIONS.map((c) => [c, { attack: outcome(sc, runs[c]), baseline: outcome(sc, base[c]) }])),
    });
  }
}
const result = {
  kind: "evibound-chain-review-cases", status: "exploratory (scripted planner 'careful'; text injections at their worst case)",
  data_git_head: D.git_head, data_content_sha256: D.content_sha256, conditions: CONDITIONS,
  planners: { default: "careful", hasty_for: Array.from(HASTY) },
  constants: { max_age: params.maxAge, max_writes: params.maxWrites, record_times: params.recordTimes, start_clock: params.startClock },
  hijack: { actions: A.HIJACK_ACTIONS, target: A.HIJACK_TARGET, injection_text: A.INJECTION_TEXT },
  hops: A.HOPS,
  attacks: A.ATTACKS.filter((a) => a.id !== "none").map((a) => ({ id: a.id, hop: a.hop, zh: a.zh, en: a.en, real: a.real,
    modelled: a.modelled || "mechanical", hooks: Object.keys(a.hooks || {}).sort(), params: a.params || null, run: a.run !== false,
    tasks: a.run === false ? 0 : D.scenarios.filter((s) => !a.applies || a.applies(s)).length })),
  cases,
};
const text = JSON.stringify(result) + "\n";
if (outPath) fs.writeFileSync(outPath, text); else process.stdout.write(text);
