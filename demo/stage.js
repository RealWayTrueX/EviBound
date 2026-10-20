/* EviBound demo stage: a blueprint of the simulated home plus the data chain around it,
 * with packet animations, guard LEDs, stamps and full-screen effects.
 *
 * API (window.EviStage):
 *   mount(svgHost, fxCanvas, fxOverlay)         build the SVG once
 *   setScene({room, modality, authorized})       which room/sensor is live
 *   setState({truth, belief, actuators, clock, unsafe, beliefKnown})
 *   status(key, text)                            key: room|hub|cloud|attacker|agent|guard|oracle|devices
 *   setSpeed(mult)                               0 = instant, 1 = normal, 2 = slow
 *   reset()                                      clear packets, stamps, highlights
 *   fx(name, detail) -> Promise                  animations listed in FX below
 */
(function (root) {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const ROOMS = {
    kitchen: { zh: "厨房", en: "KITCHEN", x: 60, y: 70, w: 240, h: 290 },
    hallway: { zh: "门厅", en: "HALLWAY", x: 300, y: 70, w: 240, h: 290 },
    bedroom: { zh: "卧室", en: "BEDROOM", x: 540, y: 70, w: 240, h: 290 },
    garage: { zh: "车库", en: "GARAGE", x: 60, y: 360, w: 240, h: 290 },
    office: { zh: "书房", en: "OFFICE", x: 300, y: 360, w: 240, h: 290 },
    nursery: { zh: "婴儿房", en: "NURSERY", x: 540, y: 360, w: 240, h: 290 },
  };
  const NODES = {
    hub: { x: 352, y: 302, zh: "网关 · 可信记录库", en: "HUB · RECORD STORE", w: 150, enName: "Hub · record store" },
    cloud: { x: 1000, y: 112, zh: "云端 / 集成层", en: "CLOUD · INTEGRATIONS", w: 210, enName: "Cloud / integrations" },
    attacker: { x: 1196, y: 112, zh: "攻击者", en: "ATTACKER", w: 120, enName: "Attacker" },
    agent: { x: 1000, y: 332, zh: "智能体 · Qwen2.5-7B", en: "LLM AGENT", w: 210, enName: "Agent · Qwen2.5-7B" },
    guard: { x: 1000, y: 540, zh: "EviBound 守卫", en: "EVIBOUND GUARD", w: 210, enName: "EviBound guard" },
    oracle: { x: 1196, y: 650, zh: "独立判分", en: "ORACLE", w: 120, enName: "Independent oracle" },
  };
  const EN = () => root.EVI_LANG === "en";
  const L = (zh, en) => (EN() ? en : zh);
  const LED_LABELS = () => [L("来源", "Prov"), L("时效", "Fresh"), L("授权", "Auth"), "R1", "R2", "R3", "R4", "R5", "R6"];
  const LEVEL_ZH = { off: "关", low: "1档", high: "2档" };
  const LEVEL_EN = { off: "off", low: "low", high: "high" };
  const LV = (v) => (EN() ? LEVEL_EN : LEVEL_ZH)[v];
  const FURNITURE = {
    kitchen: ["M20 40 h70 v40 h-70 z", "M20 80 v160 h40 v-160", "M32 110 a6 6 0 1 0 12 0 a6 6 0 1 0 -12 0", "M32 140 a6 6 0 1 0 12 0 a6 6 0 1 0 -12 0", "M150 200 h60 v40 h-60 z", "M160 210 h40 v20 h-40 z"],
    hallway: ["M40 80 h160 v120 h-160 z", "M52 92 h136 v96 h-136 z", "M20 240 h80 v22 h-80 z"],
    bedroom: ["M30 110 h120 v140 h-120 z", "M38 118 h46 v30 h-46 z", "M96 118 h46 v30 h-46 z", "M30 160 h120", "M170 110 h40 v40 h-40 z"],
    garage: ["M40 70 h150 v170 h-150 z", "M55 95 h120 v45 h-120 z", "M40 110 a10 10 0 1 0 0 -0.1", "M40 230 h20", "M170 230 h20", "M20 60 h20 v180 h-20 z"],
    office: ["M40 120 h140 v50 h-140 z", "M80 150 h60 v8 h-60 z", "M100 190 a16 16 0 1 0 32 0 a16 16 0 1 0 -32 0", "M190 200 h30 v60 h-30 z"],
    nursery: ["M40 120 h110 v90 h-110 z", "M52 120 v90 M68 120 v90 M84 120 v90 M100 120 v90 M116 120 v90 M132 120 v90", "M170 200 q25 -40 50 0", "M175 210 h40"],
  };
  const EL = (tag, attrs, parent) => {
    const el = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v !== undefined && v !== null) el.setAttribute(k, v);
    if (parent) parent.appendChild(el);
    return el;
  };
  const TEXT = (parent, x, y, str, cls, attrs) => {
    const t = EL("text", Object.assign({ x, y, class: cls }, attrs || {}), parent);
    t.textContent = str;
    return t;
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const reduced = () => root.matchMedia && root.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const S = {
    svg: null, layers: {}, rooms: {}, nodes: {}, paths: {}, leds: [], active: "office", modality: "presence_flag",
    authorized: ["light", "fan"], state: { truth: false, belief: null, actuators: { light: "off", fan: "off" }, unsafe: false },
    speed: 1, canvas: null, overlay: null, particles: [], raf: null, packets: new Set(),
  };
  const dur = (ms) => (S.speed === 0 || reduced() ? 0 : ms * S.speed);

  /* ---------------- construction ---------------- */
  function mount(host, canvas, overlay) {
    S.canvas = canvas; S.overlay = overlay;
    // inner: one positioned box holding the star field, the drawing and the payload callouts,
    // so all three scale and scroll together.
    const inner = document.createElement("div");
    inner.className = "stage-inner";
    host.appendChild(inner);
    S.inner = inner;
    const sky = document.createElement("canvas");
    sky.className = "starfield";
    sky.setAttribute("aria-hidden", "true");
    inner.appendChild(sky);
    S.sky = sky;
    const svg = EL("svg", { viewBox: "0 0 1280 720", class: "stage-svg", role: "img", "aria-label": L("智能家居平面图与数据链路", "Smart-home floor plan and data chain") });
    inner.appendChild(svg);
    const calloutLayer = document.createElement("div");
    calloutLayer.className = "callout-layer";
    inner.appendChild(calloutLayer);
    S.calloutLayer = calloutLayer;
    S.svg = svg;
    buildDefs(svg);
    EL("rect", { x: 0, y: 0, width: 1280, height: 720, fill: "url(#grid)" }, svg);
    for (const k of ["links", "house", "chain", "packets", "stamps"]) S.layers[k] = EL("g", { class: "layer-" + k }, svg);
    // house outline
    EL("rect", { x: 48, y: 58, width: 744, height: 604, rx: 6, class: "house-outline" }, S.layers.house);
    TEXT(S.layers.house, 60, 48, L("SIMULATED HOME · 模拟住宅 · 平面图", "SIMULATED HOME · FLOOR PLAN"), "stage-eyebrow");
    for (const [key, r] of Object.entries(ROOMS)) buildRoom(key, r);
    for (const [key, n] of Object.entries(NODES)) buildNode(key, n);
    buildLinks();
    setScene({ room: "office", modality: "presence_flag", authorized: ["light", "fan"] });
    setState({ truth: false, belief: null, actuators: { light: "off", fan: "off" } });
    resizeCanvas();
    root.addEventListener("resize", resizeCanvas);
    startSky();
  }
  function buildDefs(svg) {
    const defs = EL("defs", {}, svg);
    const grid = EL("pattern", { id: "grid", width: 40, height: 40, patternUnits: "userSpaceOnUse" }, defs);
    EL("path", { d: "M40 0 H0 V40", class: "grid-line" }, grid);
    EL("path", { d: "M20 0 V40 M0 20 H40", class: "grid-line-minor" }, grid);
    const glow = EL("filter", { id: "glow", x: "-60%", y: "-60%", width: "220%", height: "220%" }, defs);
    EL("feGaussianBlur", { stdDeviation: 6, result: "b" }, glow);
    const merge = EL("feMerge", {}, glow);
    EL("feMergeNode", { in: "b" }, merge); EL("feMergeNode", { in: "SourceGraphic" }, merge);
    const soft = EL("filter", { id: "soft", x: "-50%", y: "-50%", width: "200%", height: "200%" }, defs);
    EL("feGaussianBlur", { stdDeviation: 14 }, soft);
    const glitch = EL("filter", { id: "glitch", x: "-20%", y: "-20%", width: "140%", height: "140%" }, defs);
    EL("feOffset", { in: "SourceGraphic", dx: 3, dy: 0, result: "r" }, glitch);
    EL("feColorMatrix", { in: "r", type: "matrix", values: "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0", result: "rr" }, glitch);
    EL("feOffset", { in: "SourceGraphic", dx: -3, dy: 0, result: "c" }, glitch);
    EL("feColorMatrix", { in: "c", type: "matrix", values: "0 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0", result: "cc" }, glitch);
    const gm = EL("feMerge", {}, glitch);
    EL("feMergeNode", { in: "rr" }, gm); EL("feMergeNode", { in: "cc" }, gm); EL("feMergeNode", { in: "SourceGraphic" }, gm);
    const lamp = EL("radialGradient", { id: "lampglow" }, defs);
    EL("stop", { offset: "0%", "stop-color": "var(--amber)", "stop-opacity": 0.55 }, lamp);
    EL("stop", { offset: "100%", "stop-color": "var(--amber)", "stop-opacity": 0 }, lamp);
  }
  function buildRoom(key, r) {
    const g = EL("g", { class: "room", "data-room": key, transform: `translate(${r.x} ${r.y})` }, S.layers.house);
    EL("rect", { x: 0, y: 0, width: r.w, height: r.h, class: "room-floor" }, g);
    EL("rect", { x: 0, y: 0, width: r.w, height: r.h, class: "room-tint" }, g);
    const glow = EL("circle", { cx: r.w / 2, cy: 48, r: 0, class: "lamp-glow", fill: "url(#lampglow)" }, g);
    const furniture = EL("g", { class: "furniture" }, g);
    for (const d of FURNITURE[key] || []) EL("path", { d, transform: "translate(14 40)" }, furniture);
    EL("rect", { x: 0, y: 0, width: r.w, height: r.h, class: "room-wall" }, g);
    // door gap on the wall facing the hallway
    if (EN()) TEXT(g, 14, 24, r.en.charAt(0) + r.en.slice(1).toLowerCase(), "room-name");
    else { TEXT(g, 14, 24, r.zh, "room-name"); TEXT(g, 14 + r.zh.length * 16 + 6, 24, r.en, "room-name-en"); }
    const status = TEXT(g, r.w - 14, 24, "", "room-status", { "text-anchor": "end" });
    // light fixture
    const light = EL("g", { class: "light", transform: `translate(${r.w / 2} 48)` }, g);
    EL("circle", { r: 13, class: "light-ring" }, light);
    EL("circle", { r: 7, class: "light-bulb" }, light);
    EL("path", { d: "M-4 -18 h8 M0 -22 v4", class: "light-wire" }, light);
    const lightLabel = TEXT(light, 0, 32, L("灯 关", "light off"), "fixture-label", { "text-anchor": "middle" });
    // fan
    const fan = EL("g", { class: "fan", transform: `translate(${r.w - 54} ${r.h / 2 + 4})` }, g);
    const blades = EL("g", { class: "fan-blades" }, fan);
    for (const a of [0, 90, 180, 270]) EL("path", { d: "M0 0 C 6 -8 12 -26 0 -30 C -12 -26 -6 -8 0 0 z", transform: `rotate(${a})` }, blades);
    EL("circle", { r: 5, class: "fan-hub" }, fan);
    const fanLabel = TEXT(fan, 0, 46, L("风扇 关", "fan off"), "fixture-label", { "text-anchor": "middle" });
    // sensor
    const sensor = EL("g", { class: "sensor", transform: `translate(26 ${r.h / 2})` }, g);
    const sensorIcon = EL("g", { class: "sensor-icon" }, sensor);
    const sensorLabel = TEXT(sensor, 0, 36, L("传感器", "sensor"), "fixture-label", { "text-anchor": "middle" });
    // people
    const px = r.w / 2 - 10, py = r.h / 2 + 34;
    const person = EL("g", { class: "person", transform: `translate(${px} ${py})` }, g);
    EL("circle", { cx: 0, cy: -34, r: 10 }, person);
    EL("path", { d: "M-16 24 C -16 -6 -10 -18 0 -18 C 10 -18 16 -6 16 24 Z" }, person);
    const personLabel = TEXT(person, 0, 42, "", "person-label", { "text-anchor": "middle" });
    const ghost = EL("g", { class: "ghost", transform: `translate(${px + 44} ${py})` }, g);
    EL("circle", { cx: 0, cy: -34, r: 10 }, ghost);
    EL("path", { d: "M-16 24 C -16 -6 -10 -18 0 -18 C 10 -18 16 -6 16 24 Z" }, ghost);
    const ghostLabel = TEXT(ghost, 0, 42, L("幻影", "phantom"), "ghost-label", { "text-anchor": "middle" });
    S.rooms[key] = { g, r, glow, light, lightLabel, fan, blades, fanLabel, sensor, sensorIcon, sensorLabel, person, personLabel, ghost, ghostLabel, status };
  }
  function sensorGlyph(modality) {
    const paths = {
      presence_flag: ["M-12 6 a12 12 0 0 1 24 0 z", "M-4 10 h8"],
      motion_timer: ["M-6 6 a7 7 0 0 1 12 0", "M-11 10 a13 13 0 0 1 22 0", "M-16 14 a19 19 0 0 1 32 0"],
      camera_caption: ["M-14 -6 h20 v16 h-20 z", "M6 0 l8 -5 v14 l-8 -5", "M-4 2 a4 4 0 1 0 0.1 0"],
      multi_sensor: ["M-18 -6 h16 v14 h-16 z", "M-2 0 l6 -4 v12 l-6 -4", "M8 6 a6 6 0 0 1 12 0", "M3 11 a12 12 0 0 1 22 0"],
    };
    return paths[modality] || paths.presence_flag;
  }
  function buildNode(key, n) {
    const pos = EL("g", { transform: `translate(${n.x} ${n.y})` }, S.layers.chain);
    const g = EL("g", { class: "node node-" + key }, pos);
    const w = n.w, h = 54;
    EL("rect", { x: -w / 2, y: -h / 2, width: w, height: h, rx: 8, class: "node-box" }, g);
    const icon = EL("g", { class: "node-icon", transform: `translate(${-w / 2 + 22} 0)` }, g);
    const glyphs = {
      hub: ["M-9 -9 h18 v18 h-18 z", "M-5 -3 h10 M-5 2 h10 M-5 7 h6"],
      cloud: ["M-12 6 a6 6 0 0 1 2 -12 a9 9 0 0 1 17 -2 a7 7 0 0 1 3 14 z"],
      attacker: ["M0 -10 a7 7 0 0 1 7 7 v3 h-14 v-3 a7 7 0 0 1 7 -7 z", "M-10 12 q10 -8 20 0", "M-4 -2 h2 M2 -2 h2"],
      agent: ["M-10 -8 h20 v16 h-20 z", "M-4 -12 h8 v4 h-8 z", "M-5 -1 h2 M3 -1 h2", "M-5 4 h10"],
      guard: ["M0 -12 L10 -8 V2 C10 8 5 12 0 14 C-5 12 -10 8 -10 2 V-8 Z", "M-5 1 l4 4 l7 -8"],
      oracle: ["M-10 -10 h20 v20 h-20 z", "M-6 2 l4 4 l8 -9"],
    };
    for (const d of glyphs[key]) EL("path", { d }, icon);
    TEXT(g, -w / 2 + 44, -3, EN() ? n.enName : n.zh, "node-zh");
    TEXT(g, -w / 2 + 44, 13, n.en, "node-en");
    const status = TEXT(g, 0, h / 2 + 18, "", "node-status", { "text-anchor": "middle" });
    const ring = EL("circle", { cx: 0, cy: 0, r: 0, class: "node-ring" }, g);
    S.nodes[key] = { g, n, status, ring };
    if (key === "guard") {
      const leds = EL("g", { class: "leds", transform: `translate(${-w / 2 + 10} ${h / 2 + 30})` }, g);
      LED_LABELS().forEach((label, i) => {
        const x = i * 22;
        const c = EL("circle", { cx: x + 6, cy: 0, r: 4.5, class: "led" }, leds);
        TEXT(leds, x + 6, 16, label, "led-label", { "text-anchor": "middle" });
        S.leds.push(c);
      });
      S.nodes.guard.status.setAttribute("y", h / 2 + 62);
    }
    if (key === "attacker") g.classList.add("hidden-node");
  }
  function buildLinks() {
    const L = S.layers.links;
    S.paths.hubCloud = EL("path", { class: "link", d: `M ${NODES.hub.x} ${NODES.hub.y - 27} C ${NODES.hub.x} -10 ${NODES.cloud.x} -30 ${NODES.cloud.x} ${NODES.cloud.y - 27}` }, L);
    S.paths.cloudAgent = EL("path", { class: "link", d: `M ${NODES.cloud.x} ${NODES.cloud.y + 27} L ${NODES.agent.x} ${NODES.agent.y - 27}` }, L);
    S.paths.agentGuard = EL("path", { class: "link", d: `M ${NODES.agent.x} ${NODES.agent.y + 27} L ${NODES.guard.x} ${NODES.guard.y - 27}` }, L);
    S.paths.attackerCloud = EL("path", { class: "link link-attack", d: `M ${NODES.attacker.x - 60} ${NODES.attacker.y} L ${NODES.cloud.x + 105} ${NODES.cloud.y}` }, L);
    S.paths.hubAgent = EL("path", { class: "link link-faint", d: `M ${NODES.hub.x + 75} ${NODES.hub.y} C 700 ${NODES.hub.y} 800 ${NODES.agent.y} ${NODES.agent.x - 105} ${NODES.agent.y}` }, L);
    S.paths.guardOracle = EL("path", { class: "link link-faint", d: `M ${NODES.guard.x + 105} ${NODES.guard.y} L ${NODES.oracle.x - 60} ${NODES.oracle.y}` }, L);
    S.paths.sensorHub = EL("path", { class: "link link-room" }, L);
    S.paths.guardLight = EL("path", { class: "link link-room" }, L);
    S.paths.guardFan = EL("path", { class: "link link-room" }, L);
  }

  /* ---------------- scene & state ---------------- */
  function setScene({ room, modality, authorized }) {
    if (ROOMS[room]) S.active = room;
    S.modality = modality || S.modality;
    S.authorized = authorized || S.authorized;
    for (const [key, R] of Object.entries(S.rooms)) {
      R.g.classList.toggle("active", key === S.active);
      R.sensor.style.display = key === S.active ? "" : "none";
      R.person.style.display = key === S.active ? "" : "none";
      R.ghost.style.display = "none";
      R.light.classList.toggle("unauthorized", key === S.active && !S.authorized.includes("light"));
      R.fan.classList.toggle("unauthorized", key === S.active && !S.authorized.includes("fan"));
    }
    const R = S.rooms[S.active], r = R.r;
    R.sensorIcon.innerHTML = "";
    for (const d of sensorGlyph(S.modality)) EL("path", { d }, R.sensorIcon);
    R.sensorLabel.textContent = (EN() ? { presence_flag: "presence sensor", motion_timer: "motion sensor", camera_caption: "camera", multi_sensor: "camera + motion" } : { presence_flag: "存在传感器", motion_timer: "运动传感器", camera_caption: "摄像头", multi_sensor: "摄像头+运动" })[S.modality] || L("传感器", "sensor");
    const sx = r.x + 26, sy = r.y + r.h / 2;
    const hub = NODES.hub;
    S.paths.sensorHub.setAttribute("d", `M ${sx} ${sy} C ${sx} ${sy - 60} ${hub.x - 75} ${hub.y - 40} ${hub.x - 75} ${hub.y}`);
    const lx = r.x + r.w / 2, ly = r.y + 48, fx = r.x + r.w - 54, fy = r.y + r.h / 2 + 4;
    const g = NODES.guard;
    S.paths.guardLight.setAttribute("d", `M ${g.x - 105} ${g.y} C ${g.x - 260} ${g.y} ${lx} ${ly + 160} ${lx} ${ly + 16}`);
    S.paths.guardFan.setAttribute("d", `M ${g.x - 105} ${g.y + 6} C ${g.x - 220} ${g.y + 40} ${fx + 60} ${fy + 120} ${fx} ${fy + 28}`);
    S.paths.guardLight.style.display = S.authorized.includes("light") ? "" : "none";
    S.paths.guardFan.style.display = S.authorized.includes("fan") ? "" : "none";
  }
  function setState({ truth, belief, beliefKnown, actuators, unsafe, clock }) {
    Object.assign(S.state, { truth, belief, actuators: actuators || S.state.actuators, unsafe: Boolean(unsafe) });
    const R = S.rooms[S.active];
    const a = S.state.actuators;
    const glowR = { off: 0, low: 70, high: 120 }[a.light] || 0;
    R.glow.setAttribute("r", glowR);
    R.light.classList.toggle("on", a.light !== "off");
    R.light.classList.toggle("high", a.light === "high");
    R.lightLabel.textContent = L("灯 ", "light ") + LV(a.light);
    R.fan.classList.remove("low", "high");
    if (a.fan !== "off") R.fan.classList.add(a.fan);
    R.fanLabel.textContent = L("风扇 ", "fan ") + LV(a.fan);
    R.g.classList.toggle("unsafe", S.state.unsafe);
    // truth figure
    R.person.style.display = truth ? "" : "none";
    R.personLabel.textContent = truth ? L("真实：有人", "truth: occupied") : "";
    // belief phantom
    const known = beliefKnown !== undefined ? beliefKnown : belief !== null && belief !== undefined;
    const wrong = known && belief !== truth;
    R.ghost.style.display = wrong && belief ? "" : "none";
    R.ghostLabel.textContent = L("幻影：智能体以为有人", "phantom: agent thinks occupied");
    R.person.classList.toggle("hidden-from-agent", wrong && !belief);
    R.personLabel.textContent = truth ? (wrong && !belief ? L("真实：有人 · 智能体以为没人", "truth: occupied · agent thinks empty") : L("真实：有人", "truth: occupied")) : "";
    R.status.textContent = truth ? L("有人", "occupied") : L("没人", "empty");
    R.status.classList.toggle("ok", !known || !wrong);
    S.nodes.agent.g.classList.toggle("deceived", wrong);
  }
  function status(key, text) {
    if (key === "room" || key === "devices") { const R = S.rooms[S.active]; if (key === "devices") R.status.textContent = text; return; }
    const n = S.nodes[key];
    if (n) n.status.textContent = text || "";
  }
  function setSpeed(mult) { S.speed = mult; }
  function reset() {
    S.layers.packets.innerHTML = "";
    S.layers.stamps.innerHTML = "";
    S.packets.forEach((cancel) => cancel());
    S.packets.clear();
    for (const led of S.leds) led.setAttribute("class", "led");
    for (const n of Object.values(S.nodes)) { n.g.classList.remove("hot", "glitch", "deceived"); n.status.textContent = ""; }
    S.nodes.attacker.g.classList.add("hidden-node");
    for (const R of Object.values(S.rooms)) { R.g.classList.remove("unsafe", "blocked"); R.status.textContent = ""; }
    if (S.overlay) S.overlay.className = "fx-overlay";
    if (S.calloutLayer) S.calloutLayer.innerHTML = "";
    document.body.classList.remove("shake");
    S.particles = [];
  }

  /* ---------------- primitives ---------------- */
  function pulse(key, color) {
    const n = S.nodes[key];
    if (!n) return;
    const ring = EL("circle", { cx: 0, cy: 0, r: 20, class: "ring", style: `stroke:${color}` }, n.g);
    ring.addEventListener("animationend", () => ring.remove());
    if (dur(1) === 0) ring.remove();
  }
  function roomPulse(color) {
    const R = S.rooms[S.active];
    const ring = EL("rect", { x: -6, y: -6, width: R.r.w + 12, height: R.r.h + 12, rx: 8, class: "room-ring", style: `stroke:${color}` }, R.g);
    ring.addEventListener("animationend", () => ring.remove());
    if (dur(1) === 0) ring.remove();
  }
  function hot(key, on) { const n = S.nodes[key]; if (n) n.g.classList.toggle("hot", on); }
  function glitch(key, ms) {
    const n = S.nodes[key];
    if (!n || dur(1) === 0) return Promise.resolve();
    n.g.classList.add("glitch");
    return sleep(dur(ms || 450)).then(() => n.g.classList.remove("glitch"));
  }
  /* Move a glowing packet with a label along an SVG path. */
  function travel(pathEl, { color, label, ms, dashed, reverse } = {}) {
    const total = pathEl.getTotalLength();
    const g = EL("g", { class: "packet" + (dashed ? " dashed" : "") }, S.layers.packets);
    const trail = [0.9, 0.75, 0.6, 0.45].map((k) => EL("circle", { r: 7 * k, style: `fill:${color};opacity:${0.5 * k}` }, g));
    EL("circle", { r: 16, style: `fill:${color};opacity:.18`, filter: "url(#soft)" }, g);
    const dot = EL("circle", { r: 7, style: `fill:${color}` , filter: "url(#glow)" }, g);
    const text = label ? TEXT(g, 0, -18, label, "packet-label", { "text-anchor": "middle", style: `fill:${color}` }) : null;
    pathEl.classList.add("lit");
    const duration = dur(ms || 900);
    return new Promise((resolve) => {
      // requestAnimationFrame does not fire in hidden or background tabs, so a timer also
      // finishes the packet; a reset cancels it. Either way the promise always settles.
      let done = false;
      const finish = (removeNow) => {
        if (done) return;
        done = true;
        S.packets.delete(cancel);
        clearTimeout(fallback);
        if (removeNow) { g.remove(); pathEl.classList.remove("lit"); }
        else setTimeout(() => { g.remove(); pathEl.classList.remove("lit"); }, duration === 0 ? 0 : 120);
        resolve();
      };
      const cancel = () => finish(true);
      S.packets.add(cancel);
      const fallback = setTimeout(() => finish(false), duration + 400);
      if (duration === 0) { finish(true); return; }
      const start = performance.now();
      const place = (el, t) => {
        const p = pathEl.getPointAtLength(Math.max(0, Math.min(total, (reverse ? 1 - t : t) * total)));
        el.setAttribute("transform", `translate(${p.x} ${p.y})`);
      };
      const frame = (now) => {
        if (done) return;
        const t = Math.min(1, (now - start) / duration);
        const e = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;  // ease in-out
        place(dot, e);
        if (text) text.setAttribute("transform", dot.getAttribute("transform"));
        g.querySelector("circle[filter='url(#soft)']").setAttribute("transform", dot.getAttribute("transform"));
        trail.forEach((c, i) => place(c, Math.max(0, e - (i + 1) * 0.035)));
        if (t < 1) requestAnimationFrame(frame);
        else finish(false);
      };
      requestAnimationFrame(frame);
    });
  }
  function stamp(text, sub, color, where) {
    const pos = where || { x: 640, y: 380 };
    const anchor = EL("g", {}, S.layers.stamps);
    const g = EL("g", { class: "stamp", style: `--c:${color}` }, anchor);
    const box = EL("rect", { y: -62, height: sub ? 118 : 96, rx: 10, class: "stamp-box" }, g);
    const main = TEXT(g, 0, 4, text, "stamp-text", { "text-anchor": "middle" });
    const subText = sub ? TEXT(g, 0, 38, sub, "stamp-sub", { "text-anchor": "middle" }) : null;
    // Size the box from the rendered text and keep the whole stamp inside the stage.
    let w = 260;
    try { w = Math.max(w, main.getBBox().width + 52, subText ? subText.getBBox().width + 52 : 0); } catch (e) { w = Math.max(w, text.length * 26 + 52); }
    box.setAttribute("x", -w / 2); box.setAttribute("width", w);
    const x = Math.min(1280 - w / 2 - 16, Math.max(w / 2 + 16, pos.x));
    const y = Math.min(720 - 70, Math.max(80, pos.y));
    anchor.setAttribute("transform", `translate(${x} ${y})`);
    if (dur(1) === 0) g.classList.add("instant");
    setTimeout(() => g.classList.add("fade"), dur(1) === 0 ? 1400 : Math.max(1600, dur(1700)));
    g.addEventListener("animationend", (e) => { if (e.animationName === "stampOut") anchor.remove(); });
    return g;
  }
  function overlay(cls, ms, origin) {
    if (!S.overlay || dur(1) === 0) return Promise.resolve();
    if (origin) {
      const p = svgToScreen(origin.x, origin.y);
      S.overlay.style.setProperty("--wx", p.x + "px");
      S.overlay.style.setProperty("--wy", p.y + "px");
    }
    S.overlay.className = "fx-overlay " + cls;
    return sleep(dur(ms)).then(() => { S.overlay.className = "fx-overlay"; });
  }
  function shake(ms) {
    if (dur(1) === 0) return Promise.resolve();
    document.body.classList.add("shake");
    return sleep(dur(ms || 500)).then(() => document.body.classList.remove("shake"));
  }
  function svgToScreen(x, y) {
    const rect = S.svg.getBoundingClientRect();
    return { x: rect.left + (x / 1280) * rect.width, y: rect.top + (y / 720) * rect.height, scale: rect.width / 1280 };
  }
  function resizeCanvas() {
    if (!S.canvas) return;
    S.canvas.width = root.innerWidth * (root.devicePixelRatio || 1);
    S.canvas.height = root.innerHeight * (root.devicePixelRatio || 1);
  }
  function burst(x, y, color, { n = 60, speed = 6, gravity = 0.18, life = 60, shape = "shard" } = {}) {
    if (!S.canvas || dur(1) === 0) return;
    const p = svgToScreen(x, y), dpr = root.devicePixelRatio || 1;
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, v = (0.4 + Math.random()) * speed;
      S.particles.push({ x: p.x * dpr, y: p.y * dpr, vx: Math.cos(a) * v * dpr, vy: Math.sin(a) * v * dpr - 2 * dpr, g: gravity * dpr,
        life, max: life, color, size: (3 + Math.random() * 5) * dpr, rot: Math.random() * 6, vr: (Math.random() - 0.5) * 0.3, shape });
    }
    if (!S.raf) S.raf = requestAnimationFrame(tick);
  }
  function tick() {
    const ctx = S.canvas.getContext("2d");
    ctx.clearRect(0, 0, S.canvas.width, S.canvas.height);
    S.particles = S.particles.filter((q) => q.life > 0);
    for (const q of S.particles) {
      q.x += q.vx; q.y += q.vy; q.vy += q.g; q.life -= 1; q.rot += q.vr;
      ctx.save();
      ctx.globalAlpha = Math.max(0, q.life / q.max);
      ctx.translate(q.x, q.y); ctx.rotate(q.rot);
      ctx.fillStyle = q.color;
      if (q.shape === "confetti") ctx.fillRect(-q.size / 2, -q.size / 4, q.size, q.size / 2);
      else { ctx.beginPath(); ctx.moveTo(0, -q.size); ctx.lineTo(q.size * 0.7, q.size * 0.5); ctx.lineTo(-q.size * 0.7, q.size * 0.5); ctx.closePath(); ctx.fill(); }
      ctx.restore();
    }
    S.raf = S.particles.length ? requestAnimationFrame(tick) : null;
  }
  async function leds(steps) {
    // steps: [{ok:boolean, idx:number}] in order; unlisted LEDs stay dark
    for (const led of S.leds) led.setAttribute("class", "led");
    for (const s of steps) {
      const led = S.leds[s.idx];
      if (!led) continue;
      led.setAttribute("class", "led " + (s.ok ? "pass" : "fail"));
      await sleep(dur(s.ok ? 90 : 220));
      if (!s.ok) break;
    }
  }
  const ledIndex = { sensor: 0, epoch: 0, record: 0, provenance: 0, freshness: 1, Auth: 2, R1: 3, R2: 4, R3: 5, R4: 6, R5: 7, R6: 8 };
  function ledSteps(checks) {
    const out = [];
    if (!checks) return out;
    if (checks.provenance) {
      const prov = checks.provenance.filter((s) => s.id !== "freshness");
      if (prov.length) out.push({ idx: 0, ok: prov.every((s) => s.ok) });
      const fresh = checks.provenance.find((s) => s.id === "freshness");
      if (fresh) out.push({ idx: 1, ok: fresh.ok });
    }
    if (checks.rules) for (const r of checks.rules) out.push({ idx: ledIndex[r.id], ok: r.ok });
    return out;
  }
  const C = {
    cyan: "var(--cyan)", amber: "var(--amber)", mint: "var(--mint)", violet: "var(--violet)", ember: "var(--ember)", rose: "var(--rose)",
  };
  const roomCenter = () => { const r = S.rooms[S.active].r; return { x: r.x + r.w / 2, y: r.y + r.h / 2 + 10 }; };
  const devicePos = (device) => { const r = S.rooms[S.active].r; return device === "light" ? { x: r.x + r.w / 2, y: r.y + 48 } : { x: r.x + r.w - 54, y: r.y + r.h / 2 + 4 }; };

  /* ---------------- star field (cheap: one canvas, ~30 fps, paused when off-screen) ---------------- */
  function startSky() {
    const cv = S.sky, ctx = cv.getContext("2d");
    let stars = [], shooting = null, visible = true, last = 0, w = 0, h = 0, dpr = 1;
    const seed = () => {
      dpr = Math.min(2, root.devicePixelRatio || 1);
      w = cv.clientWidth; h = cv.clientHeight;
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      const n = Math.round((w * h) / 5200);
      const hues = ["210,235,255", "170,225,255", "255,236,200", "200,190,255"];
      stars = Array.from({ length: n }, () => ({
        x: Math.random() * w, y: Math.random() * h, r: Math.random() < 0.08 ? 1.6 + Math.random() : 0.4 + Math.random() * 0.9,
        base: 0.25 + Math.random() * 0.55, amp: 0.15 + Math.random() * 0.45, speed: 0.4 + Math.random() * 1.6,
        phase: Math.random() * Math.PI * 2, drift: 0.02 + Math.random() * 0.06, c: hues[(Math.random() * hues.length) | 0] }));
    };
    const draw = (t) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      for (const st of stars) {
        const a = Math.max(0, Math.min(1, st.base + st.amp * Math.sin(st.phase + t * 0.001 * st.speed)));
        st.x -= st.drift; if (st.x < -2) st.x = w + 2;
        ctx.fillStyle = `rgba(${st.c},${a})`;
        ctx.beginPath(); ctx.arc(st.x, st.y, st.r, 0, Math.PI * 2); ctx.fill();
        if (st.r > 1.5 && a > 0.6) {  // a soft cross glint on the brightest stars
          ctx.strokeStyle = `rgba(${st.c},${(a - 0.6) * 0.8})`; ctx.lineWidth = 0.6;
          ctx.beginPath(); ctx.moveTo(st.x - 5, st.y); ctx.lineTo(st.x + 5, st.y); ctx.moveTo(st.x, st.y - 5); ctx.lineTo(st.x, st.y + 5); ctx.stroke();
        }
      }
      if (!shooting && Math.random() < 0.004) shooting = { x: Math.random() * w * 0.8 + w * 0.2, y: Math.random() * h * 0.4, vx: -7 - Math.random() * 4, vy: 2.5 + Math.random() * 2, life: 1 };
      if (shooting) {
        const g = ctx.createLinearGradient(shooting.x, shooting.y, shooting.x - shooting.vx * 12, shooting.y - shooting.vy * 12);
        g.addColorStop(0, `rgba(220,245,255,${shooting.life})`); g.addColorStop(1, "rgba(220,245,255,0)");
        ctx.strokeStyle = g; ctx.lineWidth = 1.4;
        ctx.beginPath(); ctx.moveTo(shooting.x, shooting.y); ctx.lineTo(shooting.x - shooting.vx * 12, shooting.y - shooting.vy * 12); ctx.stroke();
        shooting.x += shooting.vx; shooting.y += shooting.vy; shooting.life -= 0.02;
        if (shooting.life <= 0 || shooting.x < -50) shooting = null;
      }
    };
    const loop = (t) => {
      if (visible && !document.hidden && t - last > 33) { last = t; draw(t); }
      requestAnimationFrame(loop);
    };
    seed();
    if (reduced()) { draw(0); return; }
    if ("IntersectionObserver" in root) new IntersectionObserver((es) => { visible = es[0].isIntersecting; }).observe(cv);
    root.addEventListener("resize", () => { seed(); });
    requestAnimationFrame(loop);
  }

  /* ---------------- payload callouts: the content of the current hop, inside the stage ---------------- */
  /* Placed in the half of the house away from the active room, so it never hides the action. */
  function callout(html, opts) {
    const layer = S.calloutLayer;
    if (!layer) return;
    layer.innerHTML = "";
    if (!html) return;
    const r = S.rooms[S.active].r;
    // the other row of rooms; in the top row it stops above the hub node (y≈275)
    const top = r.y < 300 ? 372 : 64, height = r.y < 300 ? 280 : 206;
    const box = document.createElement("div");
    box.className = "callout " + ((opts && opts.tone) ? "tone-" + opts.tone : "");
    box.style.left = (60 / 1280 * 100) + "%";
    box.style.top = (top / 720 * 100) + "%";
    box.style.width = (720 / 1280 * 100) + "%";
    box.style.height = (height / 720 * 100) + "%";
    box.innerHTML = html;
    if (dur(1) === 0) box.classList.add("instant");
    layer.appendChild(box);
    const close = box.querySelector(".callout-close");
    if (close) close.addEventListener("click", () => { box.remove(); });
  }

  /* ---------------- choreographed effects ---------------- */
  const FX = {
    async setup() {
      roomPulse(C.cyan);
      hot("hub", true); await sleep(dur(300)); hot("hub", false);
    },
    async "read-clean"(d) {
      await travel(S.paths.sensorHub, { color: C.cyan, label: L("读数", "reading"), ms: 700 });
      pulse("hub", C.cyan);
      await travel(S.paths.hubCloud, { color: C.cyan, label: d && d.label, ms: 800 });
      await travel(S.paths.cloudAgent, { color: C.cyan, ms: 500 });
      pulse("agent", C.cyan);
    },
    async "read-boundary"(d) { return FX["read-clean"]({ label: (d && d.label) || L("年龄 = 2.0（上限）", "age = 2.0 (limit)") }); },
    async "attack-tamper"(d) {
      S.nodes.attacker.g.classList.remove("hidden-node");
      await travel(S.paths.sensorHub, { color: C.cyan, label: L("真实读数", "true reading"), ms: 700 });
      pulse("hub", C.cyan);
      await travel(S.paths.hubCloud, { color: C.cyan, label: d && d.truthLabel, ms: 800 });
      hot("attacker", true);
      await travel(S.paths.attackerCloud, { color: C.ember, label: (d && d.injectLabel) || L("篡改", "tamper"), ms: 350 });
      overlay("scan", 700);
      await glitch("cloud", 500);
      stamp("TAMPERED", L("读数内容被改成相反含义 · 来源与时间戳未变", "value flipped · id and timestamp unchanged"), C.ember, { x: NODES.cloud.x - 230, y: NODES.cloud.y + 60 });
      await travel(S.paths.cloudAgent, { color: C.ember, label: d && d.label, ms: 600, dashed: true });
      await glitch("agent", 400);
      hot("attacker", false);
    },
    async "attack-replay"(d) {
      S.nodes.attacker.g.classList.remove("hidden-node");
      const p = travel(S.paths.sensorHub, { color: C.cyan, label: L("真实读数", "true reading"), ms: 700 }).then(() => travel(S.paths.hubCloud, { color: C.cyan, label: L("被扣下", "held back"), ms: 800, dashed: true }));
      await p;
      hot("attacker", true);
      await travel(S.paths.attackerCloud, { color: C.ember, label: (d && d.injectLabel) || L("旧记录 t=0", "old record t=0"), ms: 400 });
      overlay("scan", 700);
      await glitch("cloud", 450);
      stamp("REPLAYED", L("一条真实但过期的旧记录被当成当前读数", "a genuine but stale record served as current"), C.ember, { x: NODES.cloud.x - 230, y: NODES.cloud.y + 60 });
      await travel(S.paths.cloudAgent, { color: C.ember, label: d && d.label, ms: 600, dashed: true });
      await glitch("agent", 400);
      hot("attacker", false);
    },
    async prompt() {
      hot("agent", true); pulse("agent", C.violet);
      await sleep(dur(500));
      hot("agent", false);
    },
    async plan(d) {
      const label = d && d.parseError ? L("格式错误", "malformed") : d && d.empty ? L("空计划", "empty plan") : (d && d.label) || L("计划", "plan");
      await travel(S.paths.agentGuard, { color: d && d.parseError ? C.ember : C.violet, label, ms: 650, dashed: Boolean(d && d.parseError) });
      pulse("guard", C.violet);
    },
    async "guard-pass"(d) {
      hot("guard", true);
      await leds(ledSteps(d.checks));
      pulse("guard", C.mint);
      const path = d.device === "light" ? S.paths.guardLight : S.paths.guardFan;
      if (path.style.display !== "none") await travel(path, { color: C.mint, label: d.label, ms: 800 });
      hot("guard", false);
    },
    async "write-effect"(d) {
      const pos = devicePos(d.device);
      burst(pos.x, pos.y, d.device === "light" ? "#ffc857" : "#5ee1ff", { n: 24, speed: 3, gravity: 0.08, life: 40, shape: "confetti" });
      await sleep(dur(350));
    },
    async unsafe(d) {
      const R = S.rooms[S.active];
      R.g.classList.add("unsafe");
      stamp("UNSAFE EFFECT", d.label || L("不安全后果", "unsafe effect"), C.rose, roomCenter());
      await Promise.all([overlay("flash-rose", 1600), shake(600)]);
      hot("oracle", true); await sleep(dur(200)); hot("oracle", false);
    },
    async block(d) {
      hot("guard", true);
      await leds(ledSteps(d.checks));
      burst(NODES.guard.x, NODES.guard.y, "#ff5c3a", { n: 70, speed: 7, life: 55 });
      S.nodes.guard.g.classList.add("jolt");
      setTimeout(() => S.nodes.guard.g.classList.remove("jolt"), 500);
      stamp("BLOCKED", d.label || L("已拦截", "blocked"), C.mint, { x: NODES.guard.x - 220, y: NODES.guard.y - 10 });
      await overlay("wave-mint", 900, { x: NODES.guard.x, y: NODES.guard.y });
      hot("guard", false);
    },
    async reread() {
      S.nodes.attacker.g.classList.add("hidden-node");
      await travel(S.paths.sensorHub, { color: C.cyan, label: L("重新读取", "re-read"), ms: 600 });
      pulse("hub", C.cyan);
      await travel(S.paths.hubAgent, { color: C.cyan, label: L("真实当前记录", "authentic current record"), ms: 800 });
      pulse("agent", C.cyan);
    },
    async feedback(d) {
      await travel(S.paths.agentGuard, { color: C.mint, label: d && d.label ? d.label : L("反馈", "feedback"), ms: 650, reverse: true });
      pulse("agent", C.mint);
    },
    async score(d) {
      hot("oracle", true);
      await travel(S.paths.guardOracle, { color: C.ember, ms: 500 });
      if (d.unsafe) {
        stamp("VERDICT · UNSAFE", d.label || L("出现不安全后果", "unsafe effect occurred"), C.rose, { x: 640, y: 560 });
        await overlay("flash-rose", 900);
      } else if (d.complete) {
        stamp("VERDICT · SAFE", d.label || L("安全完成任务", "task completed safely"), C.mint, { x: 640, y: 560 });
        const c = roomCenter();
        burst(c.x, c.y, "#46f2b6", { n: 90, speed: 6, gravity: 0.12, life: 80, shape: "confetti" });
        burst(c.x, c.y, "#5ee1ff", { n: 50, speed: 5, gravity: 0.12, life: 80, shape: "confetti" });
        await overlay("sweep-mint", 1100);
      } else {
        stamp("VERDICT · INCOMPLETE", d.label || L("安全但任务未完成", "safe but task not completed"), C.amber, { x: 640, y: 560 });
        await sleep(dur(500));
      }
      hot("oracle", false);
    },
  };
  async function fx(name, detail) {
    const f = FX[name];
    if (!f) return;
    try { await f(detail || {}); } catch (err) { console.warn("fx", name, err); }
  }

  root.EviStage = { mount, setScene, setState, status, setSpeed, reset, fx, callout, ROOMS, NODES };
})(window);
