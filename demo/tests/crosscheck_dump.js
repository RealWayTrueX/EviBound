// Run every v3 task x variant x condition through demo/engine.js with the three
// scripted personas plus adversarial personas that emit malformed or ambiguous
// model output, and print one JSON line per episode. demo/tests/test_demo_engine.py
// feeds the same replies to the Python runner and requires identical results.
// Usage: node crosscheck_dump.js [path/to/bundle.js]
"use strict";
const path = require("path");
const fs = require("fs");
const vm = require("vm");
const E = require(path.join(__dirname, "..", "engine.js"));

const bundlePath = process.argv[2] || path.join(__dirname, "..", "data", "bundle.js");
const ctx = { window: {} };
vm.runInNewContext(fs.readFileSync(bundlePath, "utf8"), ctx);
const D = ctx.window.EVIBOUND_DATA;

if (!E.PARSE_SOURCE_SUPPORTED) {
  console.error("this node cannot tag float literals (JSON.parse source access); use node >= 21");
  process.exit(2);
}

/* Adversarial personas: take the careful plan, then damage the reply the way a model might. */
const F = (n) => new E.PyFloat(n);
const careful = (c) => JSON.parse(E.scriptedPlan("careful", c));
const withEvidence = (c, mutate) => {
  const plan = careful(c);
  const evidence = E.clone(c.observation);
  const out = mutate(plan, evidence, c) || { actions: plan.actions, evidence };
  return E.pyDumps(out, false);
};
const nestedMap = (value, fn) => {
  if (value && typeof value === "object" && !(value instanceof Number)) {
    const out = {};
    for (const [k, v] of Object.entries(value)) out[k] = nestedMap(v, fn);
    return out;
  }
  return fn(value);
};
const ADVERSARIAL = {
  proto_level: (c) => withEvidence(c, (plan, evidence) => ({ actions: [{ device: "light", value: "toString" }], evidence })),
  extra_evidence_key: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions, evidence: Object.assign(evidence, { note: "x" }) })),
  wrong_record_id: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions, evidence: Object.assign(evidence, { id: "obs-nope" }) })),
  wrong_sensor: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions, evidence: Object.assign(evidence, { sensor: "presence_x" }) })),
  epoch_float: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions, evidence: Object.assign(evidence, { epoch: F(1) }) })),
  observed_at_float: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions, evidence: Object.assign(evidence, { observed_at: F(evidence.observed_at) }) })),
  nested_float: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions,
    evidence: Object.assign(evidence, { value: nestedMap(evidence.value, (v) => (typeof v === "number" ? F(v) : v)) }) })),
  nested_bool: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions,
    evidence: Object.assign(evidence, { value: nestedMap(evidence.value, (v) => (v === 1 ? true : v === 0 ? false : v)) }) })),
  value_as_string: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions, evidence: Object.assign(evidence, { value: String(E.pyDumps(evidence.value)) }) })),
  too_many_actions: (c) => withEvidence(c, (plan, evidence) => ({ actions: [1, 2, 3, 4].map(() => ({ device: "fan", value: "low" })), evidence })),
  action_extra_key: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions.map((a) => Object.assign({}, a, { why: "because" })), evidence })),
  not_json: () => "I will turn the fan on now.",
  evidence_list: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions, evidence: [evidence] })),
  dollar_text: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions, evidence, note: "$& $$ {instruction} \b\f" })),
  wrong_epoch: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions, evidence: Object.assign(evidence, { epoch: 2 }) })),
  // Plans the branch the reading does NOT suggest: legal under the believed presence, often illegal under the true one.
  opposite_branch: (c) => {
    const flipped = Object.assign({}, c, { observation: Object.assign({}, c.observation,
      { value: E.believedPresence(c.scenario, c.observation) ? c.scenario.observation.payload_absent : c.scenario.observation.payload_present }) });
    const plan = careful(flipped);
    return E.pyDumps({ actions: plan.actions, evidence: E.clone(c.observation) }, false);
  },
  // Asks for fan=high first in every plan (fan_off_to_high / R6 / load paths), then the careful plan.
  greedy_fan: (c) => withEvidence(c, (plan, evidence) => ({ actions: [{ device: "fan", value: "high" }].concat(plan.actions).slice(0, 3), evidence })),
  // Reaches the goal, then keeps writing: light=high after the plan (load_exceeds_limit when fan is high).
  overload: (c) => withEvidence(c, (plan, evidence) => ({ actions: plan.actions.slice(0, 2).concat([{ device: "light", value: "high" }]), evidence })),
  // Turn 0: two careful writes plus a malformed third (rejection -> recovery); turn 1: pads the careful
  // plan to three writes so the episode budget (3 successful writes) runs out (write_budget).
  budget_overrun: (c) => withEvidence(c, (plan, evidence) => {
    if (c.turn === 0) return { actions: plan.actions.slice(0, 2).concat([{ device: "fan", value: "toString" }]), evidence };
    const acts = plan.actions.length ? plan.actions.slice() : [{ device: c.scenario.authorized[0], value: "low" }];
    while (acts.length < 3) acts.push(acts[acts.length - 1]);
    return { actions: acts, evidence };
  }),
};

const personas = Object.assign({}, Object.fromEntries(Object.keys(E.PERSONAS).map((p) => [p, (c) => E.scriptedPlan(p, c)])), ADVERSARIAL);
for (const [persona, plan] of Object.entries(personas)) {
  for (const scenario of D.scenarios) {
    for (const variant of ["clean", "perturbed", "boundary"]) {
      for (const condition of Object.keys(E.CONDITION_SPECS)) {
        const ep = E.runEpisode(scenario, variant, condition, plan, { prompts: D.prompts });
        const first = E.firstMessages(D.prompts, scenario,
          { light: scenario.initial.light, fan: scenario.initial.fan },
          new E.World(scenario, variant).observe());
        process.stdout.write(JSON.stringify({
          persona, task_id: ep.task_id, variant, condition, trigger: ep.trigger,
          first_user: first[1].content,
          retry_user: ep.feedback ? E.pyDumps(ep.feedback, true) : null,
          raws: ep.proposals.map((p) => p.raw),
          events: ep.trace.events.map((e) => [e.kind, e.device === undefined ? null : e.device,
            e.value === undefined ? null : e.value, e.reason, e.before, e.after]),
          metrics: ep.metrics,
        }) + "\n");
      }
    }
  }
}
