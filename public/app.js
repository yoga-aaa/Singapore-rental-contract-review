"use strict";
const $ = id => document.getElementById(id);
const state = {config: null, method: "example", fragments: [], report: null, busy: false, ready: false, revision: 0};
const labels = {
  review_required: ["Clarify a supported potential risk", "risk"],
  no_material_difference_found: ["No material adverse difference in this comparison", "pass"],
  insufficient_evidence: ["Evidence insufficient — no conclusion", "unsettled"],
  model_needed: ["Offline rules cannot settle this clause", "unsettled"],
  stopped: ["Execution stopped — not assessed", "unsettled"]
};
function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
}
function officialLink(url, title) {
  try {
    const u = new URL(url);
    const allowed = ["www.hdb.gov.sg", "www.ura.gov.sg", "www.iras.gov.sg", "www.judiciary.gov.sg", "www.cea.gov.sg", "isomer-user-content.by.gov.sg"];
    if (u.protocol !== "https:" || !allowed.includes(u.hostname) || u.username || u.password) return node("span", title);
    const a = node("a", title); a.href = u.href; a.target = "_blank"; a.rel = "noopener noreferrer"; return a;
  } catch { return node("span", title); }
}
function error(message) { $("error").textContent = message || ""; $("error").hidden = !message; }
function invalidate(checkAgain = false) {
  state.revision++; state.report = null; $("report-section").hidden = true; error("");
  if (checkAgain) $("checked").checked = false;
  refreshButtons();
}
function selectedClauses() {
  if (state.method === "paste") {
    const text = $("clause").value.trim();
    return text ? [{clause_id: "CL_01", pages: [], text}] : [];
  }
  if (state.method === "pdf") return state.fragments.filter((_, i) => $("fragment-" + i)?.checked);
  const example = state.config?.examples[Number($("example").value)];
  return (example?.clauses || []).map((text, i) => ({clause_id: "CL_" + String(i + 1).padStart(2, "0"), pages: [], text}));
}
function refreshButtons() {
  const clauses = selectedClauses();
  $("review").disabled = !state.ready || state.busy || !$("synthetic").checked || !$("checked").checked || !clauses.length || clauses.length > 20;
  $("extract").disabled = state.busy || !$("synthetic").checked || !$("pdf").files.length;
}
function showExample() {
  const example = state.config?.examples[Number($("example").value)];
  $("example-purpose").textContent = example?.purpose || "";
  $("example-text").textContent = (example?.clauses || []).join("\n\n");
  $("demo-pdf").href = "/api/demo-pdf/" + (Number($("example").value) + 1);
}
function updateHousing() {
  $("example").replaceChildren();
  (state.config?.examples || []).forEach((example, i) => {
    if (example.housing_type === $("housing").value) {
      const option = node("option", example.title); option.value = String(i); $("example").append(option);
    }
  });
  state.fragments = []; $("fragments").replaceChildren(); showExample(); invalidate(true);
}
function updateVersion() {
  $("version-note").textContent = $("version").value === "v18"
    ? (state.config?.v18_status || "Recorded v18 regression failed acceptance. Offline local rules only; no new model execution.")
    : "Historical local rules. This is not a new model evaluation.";
  invalidate();
}
function switchMethod(method) {
  state.method = method;
  for (const name of ["example", "paste", "pdf"]) $(name + "-pane").hidden = name !== method;
  document.querySelectorAll("[data-method]").forEach(button => {
    const active = button.dataset.method === method;
    button.classList.toggle("selected", active); button.setAttribute("aria-pressed", String(active));
  });
  invalidate(true);
}
async function api(path, options = {}) {
  const response = await fetch(path, {...options, cache: "no-store", credentials: "same-origin"});
  let result;
  try { result = await response.json(); } catch { throw new Error("Unexpected server response. Check deployment status."); }
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Invalid request or unavailable server.");
  return result;
}
async function busy(message, action) {
  state.busy = true; $("progress").textContent = message; error(""); refreshButtons();
  try { await action(); } catch (e) { error(e.message || "Request failed."); }
  finally { state.busy = false; $("progress").textContent = ""; refreshButtons(); }
}
function details(title, className) {
  const d = node("details", undefined, className); d.append(node("summary", title)); return d;
}
function renderReport(report) {
  state.report = report;
  $("report-meta").textContent = report.version + " · " + report.housing_type + " · " + report.mode + " · Selected fragments only. No whole-contract approval.";
  $("report-note").hidden = report.version !== "v18";
  $("report-note").textContent = (report.evaluation_status || "") + ". " + (report.offline_scope || "");
  $("report-stats").replaceChildren();
  for (const [value, title] of [[report.clauses.length, "Fragments processed"], [report.accounting.api_calls, "Model API calls"], ["$" + report.accounting.cost_usd, "Model cost"]]) {
    const item = node("div"); item.append(node("b", String(value)), node("span", title)); $("report-stats").append(item);
  }
  $("results").replaceChildren();
  if (report.stopped) $("results").append(node("p", "Review stopped. Earlier results remain visible; no automatic retry.", "notice"));
  for (const row of report.clauses) {
    const item = node("article", undefined, "result");
    const label = row.result?.label || row.status;
    const [description, style] = labels[label] || ["No conclusion", "unsettled"];
    const heading = node("h3", row.clause_id); heading.append(node("span", description, "label " + style));
    item.append(heading, node("code", label), node("div", row.text, "clause-text"));
    if (row.pages.length) item.append(node("p", "PDF page(s): " + row.pages.join(", "), "muted"));
    if (row.retrieved_sources?.length) {
      const retrieved = details("Retrieved locations — retrieval is not proof of support", "evidence");
      for (const ref of row.retrieved_sources) {
        const r = node("div", undefined, "source-row");
        r.append(node("div", ref.source_id + " · " + ref.section), node("small", ref.source_kind));
        if (ref.url) r.append(officialLink(ref.url, "Open official source"));
        retrieved.append(r);
      }
      item.append(retrieved);
    }
    if (row.result) {
      item.append(node("p", row.result.reason));
      if (row.result.follow_up_question) item.append(node("p", "Ask: " + row.result.follow_up_question, "follow-up"));
      for (const ev of row.result.evidence) {
        const evidence = details(ev.source_id + " · " + ev.source_section, "evidence"); evidence.open = true;
        evidence.append(node("div", ev.quote, "quote"));
        const source = state.config.sources.find(s => s.source_id === ev.source_id);
        if (source) evidence.append(officialLink(source.url, "Open original reference"));
        if (ev.context_quote) {
          const context = details("Full registered context");
          context.append(node("div", ev.context_quote, "quote")); evidence.append(context);
        }
        item.append(evidence);
      }
    } else {
      item.append(node("p", row.status === "model_needed"
        ? "No model ran. This is unfinished analysis, not a pass or a completed risk decision. The local rules cannot settle the clause."
        : "This fragment was not assessed because execution stopped.", "notice"));
    }
    $("results").append(item);
  }
  if (report.not_processed_count) $("results").append(node("p", report.not_processed_count + " selected fragments were not processed.", "notice"));
  $("report-section").hidden = false;
  $("report-section").scrollIntoView({behavior: "smooth", block: "start"});
}
$("review").addEventListener("click", () => busy("Comparing with pinned references…", async () => {
  const revision = state.revision;
  const report = await api("/api/review", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({
    housing_type: $("housing").value, review_version: $("version").value,
    synthetic_confirmed: $("synthetic").checked, extraction_confirmed: $("checked").checked, clauses: selectedClauses()
  })});
  if (revision === state.revision) renderReport(report);
}));
$("extract").addEventListener("click", () => busy("Extracting provisional fragments…", async () => {
  const file = $("pdf").files[0];
  if (!file || !$("synthetic").checked) throw new Error("Select a synthetic PDF and confirm synthetic data first.");
  if (file.size > 2_000_000) throw new Error("PDF exceeds the 2 MB limit.");
  const revision = state.revision;
  const result = await api("/api/extract?housing_type=" + encodeURIComponent($("housing").value), {
    method: "POST", headers: {"Content-Type": "application/pdf", "X-Synthetic-Confirmed": "true"}, body: file
  });
  if (revision !== state.revision) return;
  state.fragments = result.clauses; $("fragments").replaceChildren(node("p", result.scope, "muted"));
  state.fragments.forEach((clause, i) => {
    const wrapper = node("div", undefined, "fragment");
    const check = document.createElement("input"); check.type = "checkbox"; check.id = "fragment-" + i; check.checked = i < 20;
    check.addEventListener("change", () => invalidate(true));
    const label = node("label", undefined, "check"); label.append(check, node("span", clause.clause_id + " · PDF page " + clause.pages.join(", ")));
    wrapper.append(label, node("div", clause.text, "clause-text")); $("fragments").append(wrapper);
  });
  invalidate(true);
}));
$("download").addEventListener("click", () => {
  if (!state.report) return;
  const blob = new Blob([JSON.stringify(state.report, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob); const a = document.createElement("a");
  a.href = url; a.download = "rental_review_report.json"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("clear").addEventListener("click", () => {
  $("clause").value = ""; $("pdf").value = ""; $("synthetic").checked = false; $("checked").checked = false;
  state.fragments = []; $("fragments").replaceChildren(); invalidate(); switchMethod("example");
});
document.querySelectorAll("[data-method]").forEach(button => button.addEventListener("click", () => switchMethod(button.dataset.method)));
$("housing").addEventListener("change", updateHousing);
$("version").addEventListener("change", updateVersion);
$("example").addEventListener("change", () => {showExample(); invalidate(true);});
$("clause").addEventListener("input", () => invalidate(true));
$("pdf").addEventListener("change", () => {state.fragments = []; $("fragments").replaceChildren(); invalidate(true);});
for (const id of ["synthetic", "checked"]) $(id).addEventListener("change", () => invalidate());
async function start() {
  try {
    state.config = await api("/api/config"); updateHousing(); updateVersion();
    for (const source of state.config.sources) {
      const row = node("div", undefined, "source-row");
      row.append(officialLink(source.url, source.title), node("small", source.housing_type + " · " + source.kind)); $("sources").append(row);
    }
    const status = await api("/api/health");
    state.ready = status.status === "ok" && status.live_enabled === false;
    $("health").textContent = "Verified: " + status.template_sections + " CEA + " + status.official_sections + " official sections";
    refreshButtons();
  } catch (e) {
    $("health").textContent = "References unavailable — review disabled";
    error(e.message || "Could not initialize the demonstration.");
  }
}
start();
