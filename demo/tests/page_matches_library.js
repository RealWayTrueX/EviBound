// Drives the demo page in headless Chromium and checks every whole-chain attack against
// demo/attacks/chain_attacks.js: for scripted planners the step-by-step page must end in
// the same state as runChainEpisode; with a live model (a stub endpoint that always answers
// light=off) the model-API swap (H6) must still replace the reply and worst-case raw hooks
// must not. Not part of the unittest run (needs Playwright and Chromium).
// Usage: NODE_PATH=$(npm root -g) node demo/tests/page_matches_library.js [--quick]
//        (--quick: M_full only; Playwright resolved from the global modules)
"use strict";
const path = require("path");
const fs = require("fs");
const os = require("os");
const vm = require("vm");
const http = require("http");
const { spawn } = require("child_process");
const { chromium } = require("playwright");

const ROOT = path.join(__dirname, "..", "..");
const E = require(path.join(ROOT, "demo", "engine.js"));
const A = require(path.join(ROOT, "demo", "attacks", "chain_attacks.js"));
const ctx = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(ROOT, "demo", "data", "bundle.js"), "utf8"), ctx);
const D = ctx.window.EVIBOUND_DATA;
const PARAMS = { maxAge: D.constants.max_observation_age, maxWrites: D.constants.max_writes,
  clockStep: D.constants.write_clock_step, startClock: D.constants.start_clock, recordTimes: D.constants.record_times };
const CONDITIONS = process.argv.includes("--quick") ? ["M_full"] : ["B0", "B2", "B2_full", "M", "M_full"];
const PAGE_PORT = 8790, MODEL_PORT = 8791;
const canon = (o) => JSON.stringify(o, (k, v) => (v && typeof v === "object" && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort()) : v));
const outcome = (sc, m) => canon({ final_state: m.final_state, unsafe: m.unsafe_effect, unauthorized: m.authorization_violation,
  hijacked: typeof m.hijacked === "boolean" ? m.hijacked : A.hijacked(sc, m), executed: m.executed_writes, rejected: m.rejected_proposals });
const devTasks = (attack) => {
  const tasks = D.scenarios.filter((s) => s.split === "dev" && (!attack.applies || attack.applies(s)));
  return [tasks.find((s) => s.initial.presence), tasks.find((s) => !s.initial.presence)].filter(Boolean);
};

/* Stub OpenAI-compatible model: always light=off, citing the observation it was shown. */
function stubModel() {
  return http.createServer((req, res) => {
    let body = "";
    req.on("data", (c) => { body += c; });
    req.on("end", () => {
      const text = JSON.parse(body).messages.slice(-1)[0].content;
      const m = text.match(/Observation \(copy only this object into evidence\): (\{.*\})/);
      let evidence = {};
      try { evidence = m ? JSON.parse(m[1]) : JSON.parse(text).fresh_observation || {}; } catch (e) { evidence = {}; }
      const reply = JSON.stringify({ actions: [{ device: "light", value: "off" }], evidence });
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ choices: [{ message: { role: "assistant", content: reply } }] }));
    });
  }).listen(MODEL_PORT, "127.0.0.1");
}

async function runEpisode(page, sc, condition, planner, attackId) {
  await page.selectOption("#taskSelect", sc.task_id);
  await page.selectOption("#conditionSelect", condition);
  await page.selectOption("#plannerSelect", planner);
  await page.selectOption("#attackSelect", attackId);
  await page.click("#btnFinish");
  await page.waitForFunction(() => /Oracle verdict|判分器的结论/.test(document.querySelector("#wire").innerText), null, { timeout: 20000 });
  // The verdict step's wire pane is the oracle summary as JSON.
  return JSON.parse(await page.evaluate(() => { const p = [...document.querySelectorAll("#wire pre")]; return p[p.length - 1].innerText; }));
}

(async () => {
  const server = spawn("python3", [path.join(ROOT, "demo", "serve.py"), "--port", String(PAGE_PORT)], { stdio: "ignore" });
  const model = stubModel();
  const browser = await chromium.launch();
  let failures = 0, checked = 0;
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    for (let i = 0; i < 50; i++) {
      try { await page.goto(`http://127.0.0.1:${PAGE_PORT}/`); break; } catch (e) { await new Promise((r) => setTimeout(r, 200)); }
    }
    await page.waitForSelector("#attackSelect option", { state: "attached" });
    const attacks = A.ATTACKS.filter((a) => a.hop && a.run !== false);

    // 1. Scripted planners: the page and the library agree episode by episode.
    for (const attack of attacks) for (const sc of devTasks(attack)) for (const condition of CONDITIONS) for (const persona of ["careful", "hasty"]) {
      const got = await runEpisode(page, sc, condition, "scripted:" + persona, attack.id);
      const want = A.runChainEpisode(E, sc, condition, persona, attack, D.prompts, PARAMS).metrics;
      checked += 1;
      if (outcome(sc, got) !== outcome(sc, want)) {
        failures += 1;
        console.log(`MISMATCH ${attack.id} ${sc.task_id} ${condition} ${persona}\n  page    ${outcome(sc, got)}\n  library ${outcome(sc, want)}`);
      }
    }

    // 2. Live model (stub): swaps still apply; worst-case raw hooks give way to the model's own reply.
    const preset = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "evibound-")), "stub.json");
    fs.writeFileSync(preset, JSON.stringify({ kind: "evibound-demo-preset", version: 1,
      settings: { backend: { id: "custom", custom: { type: "openai", base_url: `http://127.0.0.1:${MODEL_PORT}/v1`, model: "stub" } } },
      selection: { planner: "live:custom" } }));
    await page.setInputFiles("#presetFile", preset);
    await page.waitForTimeout(300);
    for (const attack of attacks.filter((a) => a.hooks.swap || a.hooks.raw)) for (const sc of devTasks(attack)) for (const condition of ["B2", "M_full"]) {
      const got = await runEpisode(page, sc, condition, "live:custom", attack.id);
      checked += 1;
      const ok = attack.hooks.swap
        ? outcome(sc, got) === outcome(sc, A.runChainEpisode(E, sc, condition, "careful", attack, D.prompts, PARAMS).metrics)
        : got.final_state.light === "off" && got.final_state.fan === sc.initial.fan && !got.hijacked && !got.unsafe_effect;
      if (!ok) { failures += 1; console.log(`LIVE ${attack.id} ${sc.task_id} ${condition}: ${outcome(sc, got)}`); }
    }
    failures += errors.length;
    errors.forEach((e) => console.log("PAGE ERROR", e));
  } finally {
    await browser.close();
    model.close();
    server.kill();
  }
  console.log(`${checked} episodes checked, ${failures} failure(s)`);
  process.exit(failures ? 1 : 0);
})();
