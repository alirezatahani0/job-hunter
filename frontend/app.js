const listEl = document.getElementById("list");
const detailEl = document.getElementById("detail");
const searchEl = document.getElementById("search");
const statusEl = document.getElementById("status");
const countEl = document.getElementById("count");
const refreshBtn = document.getElementById("refresh-btn");
const reportEl = document.getElementById("run-report-text");

let jobs = [];
let selectedId = null;
let applicationsById = new Map();

function applicationStatus(job) {
  if (!job) return "";
  if (job.applied || job.application_status === "submitted") return "submitted";
  const record = applicationsById.get(job.id);
  if (record?.status === "submitted" || record?.submitted === true) return "submitted";
  if (record || job.application_status === "ready") return "ready";
  return "";
}

function setStatus(text) {
  statusEl.textContent = text;
}

function matches(job, query) {
  if (!query) return true;
  const hay = [
    job.title,
    job.company,
    job.location,
    job.hiring_timezones,
    ...(job.tags || []),
  ]
    .join(" ")
    .toLowerCase();
  return hay.includes(query.toLowerCase());
}

function renderList() {
  const query = searchEl.value.trim();
  const visible = jobs
    .filter((job) => matches(job, query))
    .sort((a, b) => (b.score || 0) - (a.score || 0));
  countEl.textContent = `${visible.length} of ${jobs.length} jobs`;
  listEl.innerHTML = "";

  if (!visible.length) {
    listEl.innerHTML = `<p class="count" style="padding:12px">No jobs match that search.</p>`;
    return;
  }

  visible.forEach((job) => {
    const btn = document.createElement("button");
    const state = applicationStatus(job);
    btn.className = `job-card${job.id === selectedId ? " active" : ""}${state ? " applied" : ""}`;
    btn.type = "button";
    const score = typeof job.score === "number" ? Math.round(job.score * 100) : null;
    const applied = applicationStatus(job);
    btn.innerHTML = `
      <div class="card-top">
        <h2>${escapeHtml(job.title || "Untitled")}</h2>
        ${score === null ? "" : `<span class="score">${score}%</span>`}
      </div>
      <p class="company">${escapeHtml(job.company || "Unknown")}</p>
      <p class="salary">${escapeHtml(job.salary_text || "Salary not listed")}</p>
      ${applied === "submitted" ? `<span class="chip applied">Submitted</span>` : ""}
      ${applied === "ready" ? `<span class="chip match">Ready</span>` : ""}
    `;
    btn.addEventListener("click", () => selectJob(job.id));
    listEl.appendChild(btn);
  });
}

function selectJob(id) {
  selectedId = id;
  const job = jobs.find((item) => item.id === id);
  renderList();
  if (!job) return;

  const tags = (job.tags || [])
    .slice(0, 10)
    .map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`)
    .join("");

  const matched = (job.matched_skills || [])
    .map((tag) => `<span class="chip match">${escapeHtml(tag)}</span>`)
    .join("");
  const reasons = (job.score_breakdown?.reasons || [])
    .map((note) => `<li>${escapeHtml(note)}</li>`)
    .join("");
  const applied = applicationStatus(job);
  const score = typeof job.score === "number" ? `${Math.round(job.score * 100)}% CV match` : "Unranked";

  detailEl.classList.remove("empty");
  detailEl.innerHTML = `
    <p class="eyebrow">${escapeHtml(job.source || "job")}</p>
    <h1>${escapeHtml(job.title || "")}</h1>
    <p class="detail-company">${escapeHtml(job.company || "")}</p>
    <div class="meta">
      <span class="chip match">${escapeHtml(score)}</span>
      <span class="chip">${escapeHtml(job.location_requirements || job.location || "Remote")}</span>
      <span class="chip">${escapeHtml(job.hiring_timezones || "Timezones n/a")}</span>
      <span class="chip">${escapeHtml(job.salary_text || "Salary not listed")}</span>
      ${applied === "submitted" ? `<span class="chip applied">Submitted</span>` : ""}
      ${applied === "ready" ? `<span class="chip match">Ready</span>` : ""}
    </div>
    <div class="meta">${matched || tags}</div>
    ${reasons ? `<div class="block"><h2>Match notes</h2><ul class="notes">${reasons}</ul></div>` : ""}
    <div class="block">
      <h2>Actions</h2>
      <div class="actions detail-actions">
        <button id="optimize-btn" type="button">Tailor resume to this JD</button>
        <button id="ats-btn" type="button">Check ATS</button>
        <button id="cover-btn" type="button">Write cover letter</button>
        <button id="apply-btn" type="button">${applied === "submitted" ? "Submitted" : applied === "ready" ? "Update packet" : "Apply"}</button>
        <a class="button secondary" href="/api/resume/original">Download original Word</a>
        <a class="button secondary" id="download-optimized" href="/api/resume/optimized" aria-disabled="true" title="Tailor this JD first to download an optimized resume">Download optimized Word</a>
      </div>
    </div>
    <div id="ats-panel"></div>
    <div id="apply-panel"></div>
    <div id="optimized-panel"></div>
    <div class="jd">
      <h2>Job description</h2>
      <div class="description">${escapeHtml(job.description || "No description.")}</div>
      <a class="open" href="${escapeAttr(job.url || "#")}" target="_blank" rel="noreferrer">Open job posting</a>
    </div>
  `;
  document.getElementById("optimize-btn")?.addEventListener("click", () => tailorResume(job.id));
  document.getElementById("ats-btn")?.addEventListener("click", () => checkAts(job.id));
  document.getElementById("cover-btn")?.addEventListener("click", () => writeCoverLetter(job.id));
  document.getElementById("apply-btn")?.addEventListener("click", () => applyToJob(job.id));
  document.getElementById("download-optimized")?.addEventListener("click", (event) => {
    if (event.currentTarget.getAttribute("aria-disabled") === "true") {
      event.preventDefault();
    }
  });
  loadOptimizedFor(job.id);
  loadAtsFor(job.id);
  loadCoverFor(job.id);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

function setOptimizedDownloadEnabled(enabled) {
  const link = document.getElementById("download-optimized");
  if (!link) return;
  link.setAttribute("aria-disabled", enabled ? "false" : "true");
  link.title = enabled
    ? "Download the tailored Word resume"
    : "Tailor this JD first to download an optimized resume";
}

function optimizedMatchesJob(data, jobId) {
  return Boolean(data?.updated_cv) && data.job?.id === jobId;
}

function renderOptimized(data) {
  const panel = document.getElementById("optimized-panel");
  if (!panel || !data?.updated_cv) return;
  const changes = (data.changes_made || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  panel.innerHTML = `
    <div class="block">
      <h2>Tailored resume</h2>
      ${changes ? `<ul class="notes">${changes}</ul>` : ""}
      <pre class="resume">${escapeHtml(data.updated_cv)}</pre>
    </div>
  `;
}

async function loadOptimizedFor(jobId) {
  try {
    const response = await fetch("/api/optimized");
    if (!response.ok) return;
    const data = await response.json();
    if (selectedId !== jobId) return;
    if (optimizedMatchesJob(data, jobId)) {
      renderOptimized(data);
      setOptimizedDownloadEnabled(true);
    } else {
      setOptimizedDownloadEnabled(false);
    }
  } catch {
    setOptimizedDownloadEnabled(false);
  }
}

function renderAts(data) {
  const panel = document.getElementById("ats-panel");
  const evaluation = data?.evaluation;
  if (!panel || !evaluation) return;
  const passed = Boolean(evaluation.ats_pass);
  const source = data.cv_source === "optimized" ? "tailored resume" : "original resume";
  const missing = (evaluation.missing_skills || [])
    .map((skill) => `<span class="chip">${escapeHtml(skill)}</span>`)
    .join("");
  const notes = (evaluation.feedback || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  panel.innerHTML = `
    <div class="ats-card ${passed ? "pass" : "fail"}">
      <div class="ats-top">
        <h2>ATS ${passed ? "PASS" : "FAIL"}</h2>
        <span class="chip ${passed ? "match" : "fail"}">${Math.round(evaluation.ats_score || 0)}/100</span>
      </div>
      <p class="count">Checked ${escapeHtml(source)} against this JD.</p>
      <div class="meta">
        <span class="chip">Keywords ${Math.round(evaluation.jd_relevance || 0)}</span>
        <span class="chip">Format ${Math.round(evaluation.format_quality || 0)}</span>
        <span class="chip">Readability ${Math.round(evaluation.human_readability || 0)}</span>
        <span class="chip ${evaluation.ai_detected ? "fail" : "match"}">AI flag ${evaluation.ai_detected ? "yes" : "no"}</span>
      </div>
      ${missing ? `<p class="count">Missing JD skills</p><div class="meta">${missing}</div>` : ""}
      ${notes ? `<ul class="notes">${notes}</ul>` : ""}
    </div>
  `;
}

async function loadAtsFor(jobId) {
  try {
    const response = await fetch("/api/ats");
    if (!response.ok) return;
    const data = await response.json();
    if (selectedId !== jobId) return;
    if (data?.evaluation && data.job?.id === jobId) renderAts(data);
  } catch {
    /* no saved ATS result yet */
  }
}

async function checkAts(jobId) {
  const button = document.getElementById("ats-btn");
  if (button) button.disabled = true;
  setStatus("Checking ATS parse and keyword match…");
  try {
    const response = await fetch("/api/ats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "ATS check failed");
    renderAts(data);
    const passed = data.evaluation?.ats_pass;
    setStatus(
      `ATS ${passed ? "PASS" : "FAIL"} (${Math.round(data.evaluation?.ats_score || 0)}/100) on ${
        data.cv_source === "optimized" ? "tailored" : "original"
      } resume`
    );
  } catch (error) {
    setStatus(error.message);
  } finally {
    if (button) button.disabled = false;
  }
}

function renderApply(data) {
  const panel = document.getElementById("apply-panel");
  if (!panel || !data?.cover_letter) return;
  const jobId = data.job?.id || selectedId;
  const submitted = data.status === "submitted" || data.submitted === true;
  const points = (data.points_used || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  panel.innerHTML = `
    <div class="ats-card ${submitted ? "pass" : ""}">
      <div class="ats-top">
        <h2>${submitted ? "Application submitted" : "Remote application packet"}</h2>
        <span class="chip ${submitted ? "applied" : "match"}">${submitted ? "Submitted" : "Ready"}</span>
      </div>
      <p class="count">${
        submitted
          ? "This application was submitted."
          : "Cover letter and resume are saved. The employer form is not submitted. Remote roles only."
      }</p>
      ${points ? `<ul class="notes">${points}</ul>` : ""}
      <div class="actions detail-actions">
        <a class="button secondary" href="/api/cover/letter?job_id=${encodeURIComponent(jobId)}">Download cover letter</a>
        <a class="button secondary" href="${escapeAttr(data.apply_url || data.url || "#")}" target="_blank" rel="noreferrer">Open posting</a>
      </div>
      <pre class="resume">${escapeHtml(data.cover_letter)}</pre>
    </div>
  `;
}

async function loadCoverFor(jobId) {
  try {
    const [coverRes, appsRes] = await Promise.all([
      fetch(`/api/cover?job_id=${encodeURIComponent(jobId)}`),
      fetch("/api/applications"),
    ]);
    let applications = [];
    if (appsRes.ok) {
      applications = (await appsRes.json()).applications || [];
      applicationsById = new Map(applications.filter((item) => item.job_id).map((item) => [item.job_id, item]));
    }
    if (selectedId !== jobId) return;
    if (coverRes.ok) {
      renderApply(await coverRes.json());
      return;
    }
    const record = applications.find((item) => item.job_id === jobId);
    if (record) renderApply({ ...record, job: { id: jobId } });
  } catch {
    /* none yet */
  }
}

async function writeCoverLetter(jobId) {
  const button = document.getElementById("cover-btn");
  if (button) button.disabled = true;
  setStatus("Writing cover letter with Claude…");
  try {
    const response = await fetch("/api/cover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Cover letter failed");
    renderApply(data);
    setStatus(`Cover letter ready for ${data.job?.title || "this job"}`);
  } catch (error) {
    setStatus(error.message);
  } finally {
    if (button) button.disabled = false;
  }
}

async function applyToJob(jobId) {
  const button = document.getElementById("apply-btn");
  if (button) button.disabled = true;
  setStatus("Preparing the remote application…");
  try {
    const response = await fetch("/api/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Apply failed");
    applicationsById.set(jobId, data);
    const job = jobs.find((item) => item.id === jobId);
    if (job) job.application_status = data.submitted ? "submitted" : "ready";
    renderApply(data);
    renderList();
    setStatus(
      data.submitted
        ? `Submitted ${data.job?.title || "this job"}`
        : `Packet ready for ${data.job?.title || "this remote job"}. Employer form is not submitted.`
    );
  } catch (error) {
    setStatus(error.message);
  } finally {
    if (button) button.disabled = false;
  }
}

async function tailorResume(jobId) {
  const button = document.getElementById("optimize-btn");
  if (button) button.disabled = true;
  setStatus("Tailoring resume to this JD…");
  try {
    const response = await fetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Optimize failed");
    renderOptimized(data);
    setOptimizedDownloadEnabled(true);
    setStatus(`Tailored resume for ${data.job?.title || "this job"}`);
  } catch (error) {
    setStatus(error.message);
  } finally {
    if (button) button.disabled = false;
  }
}
async function loadVersion() {
  const versionEl = document.getElementById("app-version");
  if (!versionEl) return;
  try {
    const response = await fetch("/api/version");
    if (!response.ok) return;
    const data = await response.json();
    if (data.version) versionEl.textContent = `v${data.version}`;
  } catch {
    /* The page already shows the version baked into the HTML. */
  }
}

async function loadReport() {
  if (!reportEl) return;
  try {
    const response = await fetch("/api/report");
    if (!response.ok) return;
    const data = await response.json();
    reportEl.textContent = (data.text || "").trim() || "No run report yet.";
  } catch {
    reportEl.textContent = "No run report yet.";
  }
}

async function loadJobs() {
  setStatus("Loading jobs…");
  const [jobsRes, appsRes] = await Promise.all([
    fetch("/api/jobs"),
    fetch("/api/applications"),
  ]);
  if (!jobsRes.ok) throw new Error("Could not load jobs");
  const data = await jobsRes.json();
  jobs = data.jobs || [];
  if (appsRes.ok) {
    const apps = await appsRes.json();
    applicationsById = new Map(
      (apps.applications || []).filter((item) => item.job_id).map((item) => [item.job_id, item])
    );
  }
  setStatus(`${jobs.length} saved jobs`);
  if (!selectedId && jobs[0]) selectedId = jobs[0].id;
  renderList();
  if (selectedId) selectJob(selectedId);
}

async function refreshJobs() {
  refreshBtn.disabled = true;
  setStatus("Fetching and ranking against your CV…");
  try {
    const response = await fetch("/api/fetch", { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Fetch failed");
    jobs = data.jobs || [];
    selectedId = jobs[0]?.id || null;
    setStatus(`Ranked ${jobs.length} jobs against your CV`);
    renderList();
    if (selectedId) selectJob(selectedId);
  } catch (error) {
    setStatus(error.message);
  } finally {
    refreshBtn.disabled = false;
  }
}

searchEl.addEventListener("input", renderList);
refreshBtn.addEventListener("click", refreshJobs);

loadVersion();
loadReport();
loadJobs().catch((error) => setStatus(error.message));
