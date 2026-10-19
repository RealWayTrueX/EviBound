// Run every v3 task x variant x condition x scripted persona through demo/engine.js
// and print one JSON line per episode. Used by demo/tests/test_demo_engine.py.
"use strict";
const path = require("path");
const fs = require("fs");
const vm = require("vm");
const E = require(path.join(__dirname, "..", "engine.js"));

const ctx = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "..", "data", "bundle.js"), "utf8"), ctx);
const D = ctx.window.EVIBOUND_DATA;

for (const persona of Object.keys(E.PERSONAS)) {
  const plan = (c) => E.scriptedPlan(persona, c);
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
          events: ep.trace.events.map((e) => [e.kind, e.device, e.value, e.reason, e.before, e.after]),
          metrics: ep.metrics,
        }) + "\n");
      }
    }
  }
}
