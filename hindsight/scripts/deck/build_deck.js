// HindsightBench — space-coordinate figures as native PowerPoint slides
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const { applyTheme } = require("/root/.claude/skills/synced/8a4ccaa5-4000-4f7b-aa55-45cd08c7f586_ef7ce321-547e-4b0f-9af0-bb894a6b504c/pptx/scripts/apply_theme.js");

const D = JSON.parse(fs.readFileSync(path.join(__dirname, "deckdata.json"), "utf8"));
const OUT = path.join(__dirname, "HindsightBench_figures.pptx");

// palette = the paper's figures: date red, place blue, false-place gold, joint purple
const HEX = { text: "1F2328", bg: "FFFFFF", dark: "1B1F24", light: "F1F3F5", date: "9E2A2B", place: "2B5C8F",
  gold: "C87D20", purple: "6A4C93", gray: "6E737B", green: "3E7B52", muted: "C9CDD2", grid: "E3E6EA" };
const THEME = {
  name: "HindsightBench",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: { dk1: HEX.text, lt1: HEX.bg, dk2: HEX.dark, lt2: HEX.light, accent1: HEX.date, accent2: HEX.place,
    accent3: HEX.gold, accent4: HEX.purple, accent5: HEX.gray, accent6: HEX.green, hlink: HEX.place, folHlink: HEX.purple },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "HindsightBench: the space coordinate";
pres.author = "Haozhe Jia";
const C = pres.SchemeColor;
const W = 13.333, M = 0.6;

// ---------- layouts
pres.defineSlideMaster({
  title: "COVER",
  background: { color: HEX.dark },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.0, w: 8.2, h: 2.0, fontSize: 44, bold: true,
      color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 4.25, w: 8.2, h: 1.0, fontSize: 18,
      color: C.background2, valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "FIGURE",
  background: { color: HEX.bg },
  margin: [0.4, M, 0.5, M],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.35, w: W - 2 * M, h: 0.85, fontSize: 36, bold: true,
      color: C.text1, valign: "middle", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "takeaway", type: "body", x: M, y: 6.45, w: W - 2 * M - 1.2, h: 0.55, fontSize: 14,
      italic: true, color: C.text2, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "HindsightBench · space-coordinate figures · generated from the frozen ST-1 rows",
      options: { x: M, y: 7.08, w: 9, h: 0.3, fontSize: 10, color: HEX.gray, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: 7.08, w: 0.6, h: 0.3, fontSize: 10, color: HEX.gray, align: "right" },
});

const sign = (v, d = 0) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d);
const months = D.months;
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const lab = (m) => MON[+m.split("-")[1] - 1] + " " + m.split("-")[0];
// sparse category labels so every renderer shows the same few ticks, unrotated
const monLab = months.map((m, i) => (i % 12 === 0 ? lab(m) : ""));
const monLab6 = months.map((m, i) => (i % 6 === 0 ? lab(m) : ""));

// ---------- 1. cover
pres.addSection({ title: "Cover" });
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: "Cover" });
  s.addText("What a Coordinate Does to an LLM's Judgment", { placeholder: "title" });
  s.addText("HindsightBench · the space coordinate\nten regions, 310 region-months, five models from four vendors",
    { placeholder: "body" });
  s.addText([
    { text: "(", options: { color: C.background2 } },
    { text: "t", options: { color: HEX.date } },
    { text: ", ", options: { color: C.background2 } },
    { text: "ℓ", options: { color: "6CA0DC" } },
    { text: ")", options: { color: C.background2 } },
  ], { x: 9.2, y: 2.0, w: 3.6, h: 2.6, fontSize: 110, bold: true, align: "center", valign: "middle",
    fontFace: "Cambria", isTextBox: true, objectName: "coordinate motif" });
  s.addText([
    { text: "date", options: { color: HEX.date, bold: true } },
    { text: "  is the trigger     ", options: { color: C.background2 } },
    { text: "place", options: { color: "6CA0DC", bold: true } },
    { text: "  is read through the date", options: { color: C.background2 } },
  ], { x: 9.0, y: 4.6, w: 4.0, h: 0.5, fontSize: 12, align: "center", isTextBox: true, objectName: "motif caption" });
  s.addNotes("封面。(t, ℓ) 是决策的时空坐标：t 是日期，ℓ 是地点。整组图要说的就是：日期是触发器，地点只通过日期被读。");
}

// ---------- 2. mechanism schematic (native shapes)
pres.addSection({ title: "Mechanism" });
{
  const s = pres.addSlide({ masterName: "FIGURE", sectionTitle: "Mechanism" });
  s.addText("One snapshot, three keys", { placeholder: "title" });
  const P = D.prof;
  const R = D.reloc;
  const lanes = [
    { y: 1.95, col: HEX.date, key: "date\nMarch 2020", mech: "retrieves the\nglobal episode",
      big: sign(P["D-M"][0]) + " pp", small: "bearish in March 2020;\nflat in every other month" },
    { y: 3.55, col: HEX.place, key: "place\nLombardy", mech: "a place spans every\nperiod: no episode",
      big: sign(P["L-M"][0]) + " pp", small: "flat everywhere" },
    { y: 5.15, col: HEX.gold, key: "date +\nfalse place", mech: "moves the episode to\nthe asserted place",
      big: sign(R["deepseek-v4-flash"].relocation.pt, 1) + " / " + sign(R["claude-sonnet-5"].relocation.pt, 1) + " pp",
      small: "on the false place's onset months\n(2 of 4 models); true months kept" },
  ];
  const H = 1.0;
  lanes.forEach((L, i) => {
    const top = L.y - H / 2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: top, w: 1.55, h: H, rectRadius: 0.12,
      fill: { color: HEX.light }, line: { color: "ADB5BD", width: 1 }, objectName: `snapshot ${i + 1}` });
    s.addText("same\nsnapshot", { x: M, y: top, w: 1.55, h: H, fontSize: 14, color: C.text2, align: "center",
      valign: "middle", margin: 0, isTextBox: true, objectName: `snapshot label ${i + 1}` });
    s.addText("+", { x: 2.2, y: top, w: 0.35, h: H, fontSize: 24, color: HEX.gray, align: "center", valign: "middle",
      margin: 0, isTextBox: true, objectName: `plus ${i + 1}` });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.6, y: top, w: 1.85, h: H, rectRadius: 0.12,
      fill: { color: L.col }, line: { color: L.col, width: 1 }, objectName: `key ${i + 1}` });
    s.addText(L.key, { x: 2.6, y: top, w: 1.85, h: H, fontSize: 16, bold: true, color: C.background1, align: "center",
      valign: "middle", margin: 0, isTextBox: true, objectName: `key label ${i + 1}` });
    s.addShape(pres.shapes.LINE, { x: 4.5, y: L.y, w: 0.5, h: 0, line: { color: "495057", width: 1.5, endArrowType: "triangle" },
      objectName: `arrow a ${i + 1}` });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.05, y: top, w: 1.0, h: H, rectRadius: 0.12,
      fill: { color: HEX.dark }, line: { color: HEX.dark, width: 1 }, objectName: `llm ${i + 1}` });
    s.addText("LLM", { x: 5.05, y: top, w: 1.0, h: H, fontSize: 16, bold: true, color: C.background1, align: "center",
      valign: "middle", margin: 0, isTextBox: true, objectName: `llm label ${i + 1}` });
    s.addShape(pres.shapes.LINE, { x: 6.1, y: L.y, w: 0.5, h: 0, line: { color: "495057", width: 1.5, endArrowType: "triangle" },
      objectName: `arrow b ${i + 1}` });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.65, y: top - 0.05, w: 2.75, h: H + 0.1, rectRadius: 0.12,
      fill: { color: HEX.bg }, line: { color: L.col, width: 1.75 }, objectName: `mechanism ${i + 1}` });
    s.addText(L.mech, { x: 6.65, y: top - 0.05, w: 2.75, h: H + 0.1, fontSize: 15, color: L.col, align: "center",
      valign: "middle", margin: 0, isTextBox: true, objectName: `mechanism label ${i + 1}` });
    s.addShape(pres.shapes.LINE, { x: 9.45, y: L.y, w: 0.45, h: 0, line: { color: L.col, width: 1.75, endArrowType: "triangle" },
      objectName: `arrow c ${i + 1}` });
    s.addText(L.big, { x: 10.0, y: top - 0.12, w: 2.75, h: 0.6, fontSize: 28, bold: true, color: L.col, margin: 0,
      valign: "bottom", fontFace: "Cambria", isTextBox: true, objectName: `effect ${i + 1}` });
    s.addText(L.small, { x: 10.0, y: top + 0.5, w: 2.75, h: 0.62, fontSize: 12, color: C.text2, margin: 0, valign: "top",
      isTextBox: true, objectName: `effect caption ${i + 1}` });
  });
  s.addText("Same data, only the coordinate label changes: the date carries the episode, the place is read through the date",
    { placeholder: "takeaway" });
  s.addNotes("机制图。三条路，快照完全相同，只改坐标：给日期，模型调出 2020 年 3 月这一个全球剧目，看空 +19pp；给地点，地点跨越所有时期，没有剧目可调，+3pp；真日期加假地点，剧目被搬到假地点自己的封城月上，DeepSeek +10.7、Sonnet +8.0（4 个模型里 2 个排零），真地点的月份不受影响（interference≈0）。");
}

// ---------- 3. trigger pair (native combo charts)
pres.addSection({ title: "Trigger" });
function triggerChart(s, x, key, col, label) {
  const prof = D.prof[key];
  const other = prof.slice(1);
  const lo = Math.min(...other), hi = Math.max(...other);
  const first = prof.map((v, i) => (i === 0 ? v : 0));
  const rest = prof.map((v, i) => (i === 0 ? 0 : v));
  s.addChart([
    { type: pres.charts.BAR, data: [
        { name: "March 2020", labels: monLab, values: first },
        { name: "other months", labels: monLab, values: rest }],
      options: { barGrouping: "stacked", chartColors: [col, HEX.muted], barGapWidthPct: 25 } },
    { type: pres.charts.LINE, data: [
        { name: "highest other month", labels: monLab, values: prof.map(() => +hi.toFixed(2)) },
        { name: "lowest other month", labels: monLab, values: prof.map(() => +lo.toFixed(2)) }],
      options: { chartColors: ["8E949B", "8E949B"], lineSize: 1.25, lineDash: "dash", lineDataSymbol: "none" } },
  ], {
    x, y: 2.55, w: 5.9, h: 3.75, objectName: `${label} chart`,
    valAxisMinVal: -20, valAxisMaxVal: 30, valAxisMajorUnit: 10, valAxisLabelFontSize: 12, valAxisLabelColor: HEX.gray,
    valAxisLabelFontFace: "+mn-lt", valAxisTitle: "change in bearish share (pp)", showValAxisTitle: x < 3,
    valAxisTitleFontSize: 12, valAxisTitleColor: HEX.gray, valAxisTitleFontFace: "+mn-lt", catAxisLabelRotate: 0,
    catAxisLabelFontSize: 12, catAxisLabelColor: HEX.gray, catAxisLabelFontFace: "+mn-lt", catAxisLabelFrequency: 1,
    catAxisLabelPos: "low", catAxisLineShow: true, catAxisLineColor: "8E949B",
    valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: "none" }, showLegend: false,
    layout: { x: 0.12, y: 0.04, w: 0.86, h: 0.84 },
  });
  return { v0: prof[0], lo, hi };
}
{
  const s = pres.addSlide({ masterName: "FIGURE", sectionTitle: "Trigger" });
  s.addText("The date is the trigger; the place alone is not", { placeholder: "title" });
  const L = triggerChart(s, M, "D-M", HEX.date, "date");
  const Rr = triggerChart(s, 6.85, "L-M", HEX.place, "place");
  const V = D.vendor_mar;
  const vend = (k) => `DeepSeek ${sign(V["deepseek-v4-flash"][k])} · Gemini ${sign(V["gemini-2.5-flash-pooled"][k])} · ` +
    `Sonnet 5 ${sign(V["claude-sonnet-5"][k])} · GPT-mini ${sign(V["gpt-5.4-mini"][k])}`;
  [[M, HEX.date, "Date stated", L, "D-M"], [6.85, HEX.place, "Place stated", Rr, "L-M"]].forEach(([x, col, head, S, k], i) => {
    s.addText(head, { x, y: 1.3, w: 2.6, h: 0.4, fontSize: 18, bold: true, color: col, margin: 0, isTextBox: true,
      objectName: `${head} header` });
    s.addText(sign(S.v0) + " pp", { x, y: 1.68, w: 2.6, h: 0.75, fontSize: 40, bold: true, color: col, margin: 0,
      fontFace: "Cambria", valign: "top", isTextBox: true, objectName: `${head} stat` });
    s.addText([
      { text: `in March 2020; the other 30 months stay between ${sign(S.lo)} and ${sign(S.hi)} pp (dashed)`, options: { breakLine: true } },
      { text: "each vendor, March 2020: " + vend(k), options: { color: HEX.gray } },
    ], { x: x + 2.65, y: 1.4, w: 3.25, h: 1.0, fontSize: 12, color: C.text2, margin: 0, valign: "middle", isTextBox: true,
      objectName: `${head} detail` });
  });
  s.addText("Same panel, same scale: the date lifts one month far outside its range; the place moves none",
    { placeholder: "takeaway" });
  s.addNotes("核心对照图。左右同一纵轴。左：给日期，2020 年 3 月（全球封城）看空 +19pp，远超其余 30 个月的波动范围（虚线，−13 到 +8）；四家厂商都在 +16 到 +23。右：给地点，3 月只有 +3pp，没有任何月份冲出范围。GPT-mini 在右边 3 月是 +12.5，但它自己逐月波动有 ±13.8，不算触发。");
}

// ---------- 4. calendar ridgeline (four native bar charts on one plot geometry)
pres.addSection({ title: "Calendar" });
{
  const s = pres.addSlide({ masterName: "FIGURE", sectionTitle: "Calendar" });
  s.addText("Only the date moves a month, and only March 2020", { placeholder: "title" });
  const rows = [["D-M", "date stated", HEX.date, "F2C9C9"], ["DL-M", "date and place stated", HEX.purple, "D9CFE8"],
    ["L-M", "place stated", HEX.place, "C9D8EA"], ["S-D", "false place added", HEX.gold, "F1DDBF"]];
  const top = 1.35, hRow = 1.18, gap = 0.04, xC = 3.0, wC = 7.9;
  rows.forEach(([k, lab, col, tint], i) => {
    const prof = D.prof[k];
    const y = top + i * (hRow + gap);
    const last = i === rows.length - 1;
    s.addChart(pres.charts.BAR, [
      { name: "March 2020", labels: monLab6, values: prof.map((v, j) => (j === 0 ? v : 0)) },
      { name: "other months", labels: monLab6, values: prof.map((v, j) => (j === 0 ? 0 : v)) },
    ], {
      x: xC, y, w: wC, h: hRow + (last ? 0.35 : 0), objectName: `${lab} row`, barGrouping: "stacked",
      chartColors: [col, tint], barGapWidthPct: 25,
      valAxisMinVal: -15, valAxisMaxVal: 25, valAxisHidden: true, valGridLine: { style: "none" },
      catGridLine: { style: "none" }, catAxisHidden: !last, catAxisLabelFrequency: 1, catAxisLabelRotate: 0, catAxisLabelPos: "low",
      catAxisLabelFontSize: 12, catAxisLabelColor: HEX.gray, catAxisLabelFontFace: "+mn-lt", catAxisLineColor: "ADB5BD",
      showLegend: false,
      layout: { x: 0.01, y: 0.02, w: 0.98, h: last ? 0.96 * hRow / (hRow + 0.35) : 0.96 },
    });
    s.addText(lab, { x: M, y: y + 0.25, w: xC - M - 0.15, h: 0.55, fontSize: 16, bold: true, color: col, align: "right",
      valign: "middle", margin: 0, isTextBox: true, objectName: `${lab} label` });
    s.addText([
      { text: sign(prof[0]) + " pp", options: { fontSize: 24, bold: true, color: col, fontFace: "Cambria", breakLine: true } },
      { text: `${D.n_up[k]}/10 regions ≥ +10 in March 2020`, options: { fontSize: 11, color: HEX.gray } },
    ], { x: xC + wC + 0.2, y: y + 0.12, w: W - M - (xC + wC + 0.2), h: 0.85, margin: 0, valign: "middle", isTextBox: true,
      objectName: `${lab} value` });
  });
  s.addText("Each bar is one month, averaged over ten regions and the four models above the memory gate; first bar = March 2020",
    { placeholder: "takeaway" });
  s.addNotes("四种干预的逐月效果。每根柱子一个月，十个区域、四个过记忆门的模型平均。只有给日期（以及日期+地点）的两行在第一根柱子（2020 年 3 月）有大幅上升，十个区域里七个超过 +10；给地点、加假地点的两行在 3 月和其他月份都是小幅波动。");
}

// ---------- 5. memory vs reflex (native scatter)
pres.addSection({ title: "Memory" });
{
  const s = pres.addSlide({ masterName: "FIGURE", sectionTitle: "Memory" });
  s.addText("Memory is not the reflex", { placeholder: "title" });
  const macro = D.macro, st = D.st;
  const readable = st.filter((p) => p.gate), gated = st.filter((p) => !p.gate);
  const xs = [...macro.map((p) => p.x), ...readable.map((p) => p.x), ...gated.map((p) => p.x)];
  const n1 = macro.length, n2 = readable.length;
  const ser = (from, to, src) => xs.map((_, i) => (i >= from && i < to ? src[i - from].y : null));
  const lab = (from, to, src) => xs.map((_, i) => (i >= from && i < to ? src[i - from].name : ""));
  s.addChart(pres.charts.SCATTER, [
    { name: "X", values: xs },
    { name: "macro panel: E2 (readable rows)", values: ser(0, n1, macro), labels: xs.map(() => "") },
    { name: "sensing panel: joint key", values: ser(n1, n1 + n2, readable), labels: lab(n1, n1 + n2, readable) },
    { name: "sensing panel, below the memory gate", values: ser(n1 + n2, xs.length, gated), labels: lab(n1 + n2, xs.length, gated) },
  ], {
    x: M, y: 1.35, w: 8.2, h: 5.0, objectName: "memory vs reflex",
    lineSize: 0, lineDataSymbol: "circle", lineDataSymbolSize: 10, chartColors: ["B8BDC3", HEX.place, HEX.gray],
    showLabel: true, dataLabelFormatScatter: "custom", dataLabelPosition: "r", dataLabelFontSize: 11,
    dataLabelColor: HEX.text, dataLabelFontFace: "+mn-lt",
    valAxisMinVal: -15, valAxisMaxVal: 45, valAxisMajorUnit: 15, catAxisMinVal: -30, catAxisMaxVal: 45, catAxisMajorUnit: 15,
    valAxisTitle: "date trigger (pp)", showValAxisTitle: true, catAxisTitle: "outcome recall above the majority rate (pp)",
    showCatAxisTitle: true, valAxisTitleFontSize: 12, catAxisTitleFontSize: 12, valAxisTitleColor: HEX.gray,
    catAxisTitleColor: HEX.gray, valAxisTitleFontFace: "+mn-lt", catAxisTitleFontFace: "+mn-lt",
    valAxisLabelFontSize: 12, catAxisLabelFontSize: 12, valAxisLabelColor: HEX.gray, catAxisLabelColor: HEX.gray,
    valAxisLabelFontFace: "+mn-lt", catAxisLabelFontFace: "+mn-lt", catAxisLabelPos: "low", valAxisLabelPos: "low",
    valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { color: HEX.grid, size: 0.5 },
    showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", legendColor: HEX.text,
  });
  // right column: the reading
  const gpt = st.find((p) => p.name === "GPT-5.4-mini");
  const cards = [
    ["Memory and reflex", "upper right", "most macro-panel models; DeepSeek and Gemini on the sensing panel", HEX.date],
    ["Memory, no reflex", "lower right", `GPT-5.4-mini recalls the panel (${sign(gpt.x)} pp above chance) and triggers ${sign(gpt.y, 1)} pp; Llama 3.1 70B does the same on the macro panel`, HEX.place],
    ["Below the memory gate", "left", "Haiku 4.5 on the sensing panel: no reading", HEX.gray],
  ];
  cards.forEach(([h, where, body, col], i) => {
    const y = 1.5 + i * 1.6;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.15, y, w: 3.6, h: 1.4, rectRadius: 0.1, fill: { color: HEX.light },
      line: { color: HEX.light, width: 0.5 }, objectName: `card ${i + 1}` });
    s.addText([
      { text: h, options: { bold: true, fontSize: 15, color: col, breakLine: true } },
      { text: where, options: { italic: true, fontSize: 11, color: HEX.gray, breakLine: true } },
      { text: body, options: { fontSize: 12, color: C.text2 } },
    ], { x: 9.3, y: y + 0.08, w: 3.3, h: 1.25, margin: 0, valign: "top", isTextBox: true, objectName: `card text ${i + 1}` });
  });
  s.addText("Recalling what happened does not make a model act on the date: memory without reflex appears on both panels",
    { placeholder: "takeaway" });
  s.addNotes("记忆不等于反射。横轴：结果回忆超出多数类比率多少（记忆）；纵轴：日期触发强度（反射）。右上是既有记忆又有反射；右下是有记忆没反射——时空面板上的 GPT-5.4-mini，宏观面板上的 Llama 3.1 70B；左边是低于记忆门槛的 Haiku 4.5。");
}

// ---------- 6. false place (native clustered bar; error bars added in post-processing)
pres.addSection({ title: "False place" });
{
  const s = pres.addSlide({ masterName: "FIGURE", sectionTitle: "False place" });
  s.addText("A false place moves the episode; the true one stays", { placeholder: "title" });
  const order = [["deepseek-v4-flash", "DeepSeek"], ["gemini-2.5-flash-pooled", "Gemini"], ["claude-sonnet-5", "Sonnet 5"], ["gpt-5.4-mini", "GPT-5.4-mini"]];
  const R = D.reloc;
  s.addChart(pres.charts.BAR, [
    { name: "relocation: asserted place's onset months", labels: order.map((o) => o[1]), values: order.map((o) => R[o[0]].relocation.pt) },
    { name: "interference: true place's onset months", labels: order.map((o) => o[1]), values: order.map((o) => R[o[0]].interference.pt) },
  ], {
    x: M, y: 1.35, w: 7.6, h: 5.0, objectName: "false place chart", barDir: "col", barGrouping: "clustered", barGapWidthPct: 70,
    chartColors: [HEX.gold, "9AA0A6"], valAxisMinVal: -15, valAxisMaxVal: 25, valAxisMajorUnit: 5,
    valAxisTitle: "change against the date alone (pp)", showValAxisTitle: true, valAxisTitleFontSize: 12,
    valAxisTitleColor: HEX.gray, valAxisTitleFontFace: "+mn-lt", valAxisLabelFontSize: 12, valAxisLabelColor: HEX.gray,
    valAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 14, catAxisLabelColor: HEX.text, catAxisLabelFontFace: "+mn-lt",
    catAxisLabelPos: "low", valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", legendColor: HEX.text,
  });
  const rows = [[{ text: "", options: { bold: true } }, ...order.map((o) => ({ text: o[1], options: { bold: true, align: "center" } }))]];
  [["relocation", "Relocation"], ["interference", "Interference"]].forEach(([k, lab]) => {
    rows.push([{ text: lab, options: { bold: true } }, ...order.map((o) => {
      const c = R[o[0]][k]; const ex = c.lo > 0 || c.hi < 0;
      return { text: `${sign(c.pt, 1)}\n[${sign(c.lo, 1)}, ${sign(c.hi, 1)}]`, options: { align: "center", bold: ex, color: ex ? HEX.gold : HEX.gray } };
    })]);
  });
  s.addText("Estimate and 95% CI (pp); bold excludes zero: relocation on DeepSeek and Sonnet 5, interference nowhere", { x: 8.4, y: 1.45, w: 4.35, h: 0.75,
    fontSize: 14, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "table heading" });
  s.addTable(rows, { x: 8.4, y: 2.35, w: 4.35, colW: [1.03, 0.83, 0.83, 0.83, 0.83], fontSize: 11, fontFace: "Calibri",
    color: HEX.text, border: { type: "solid", color: HEX.grid, pt: 0.75 }, rowH: [0.42, 0.62, 0.62], valign: "middle", margin: 0.04, objectName: "ci table" });
  s.addText("Whiskers: node-level paired bootstrap, 95%. Relocation = bearishness gained on the asserted region's onset months; interference = bearishness lost on the true region's.",
    { x: 8.4, y: 4.2, w: 4.35, h: 1.3, fontSize: 12, color: HEX.gray, margin: 0, valign: "top", isTextBox: true, objectName: "definition" });
  s.addText("The place acts only through the date: it moves where the episode lands on two of four models, and never erases the true signal",
    { placeholder: "takeaway" });
  s.addNotes("假地点的作用。金色是假地点封城月上增加的看空（relocation），灰色是真地点封城月上减少的看空（interference）。DeepSeek +10.7、Sonnet +8.0 排零；Gemini 和 GPT 不显著；interference 四个都是零。结论：地点只能通过日期起作用——它改变剧目落在哪里，但不会抹掉真实信号。");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
