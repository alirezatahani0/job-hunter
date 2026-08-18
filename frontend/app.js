const listEl = document.getElementById("list");
const detailEl = document.getElementById("detail");
const searchEl = document.getElementById("search");
const statusEl = document.getElementById("status");
const countEl = document.getElementById("count");
const refreshBtn = document.getElementById("refresh-btn");

let jobs = [];
let selectedId = null;

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
  const visible = jobs.filter((job) => matches(job, query));
  countEl.textContent = `${visible.length} of ${jobs.length} jobs`;
  listEl.innerHTML = "";

  if (!visible.length) {
    listEl.innerHTML = `<p class="count" style="padding:12px">No jobs match that search.</p>`;
    return;
  }

  visible.forEach((job) => {
    const btn = document.createElement("button");
    btn.className = `job-card${job.id === selectedId ? " active" : ""}`;
    btn.type = "button";
    btn.innerHTML = `
      <h2>${escapeHtml(job.title || "Untitled")}</h2>
      <p>${escapeHtml(job.company || "Unknown")}</p>
      <p class="salary">${escapeHtml(job.salary_text || "Salary not listed")}</p>
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

  detailEl.classList.remove("empty");
  detailEl.innerHTML = `
    <p class="eyebrow">${escapeHtml(job.source || "job")}</p>
    <h1>${escapeHtml(job.title || "")}</h1>
    <p>${escapeHtml(job.company || "")}</p>
    <div class="meta">
      <span class="chip">${escapeHtml(job.location_requirements || job.location || "Remote")}</span>
      <span class="chip">${escapeHtml(job.hiring_timezones || "Timezones n/a")}</span>
      <span class="chip">${escapeHtml(job.salary_text || "Salary not listed")}</span>
    </div>
    <div class="meta">${tags}</div>
    <div class="description">${escapeHtml(job.description || "No description.")}</div>
    <a class="open" href="${escapeAttr(job.url || "#")}" target="_blank" rel="noreferrer">Open job posting</a>
  `;
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

async function loadJobs() {
  setStatus("Loading jobs…");
  const response = await fetch("/api/jobs");
  if (!response.ok) throw new Error("Could not load jobs");
  const data = await response.json();
  jobs = data.jobs || [];
  setStatus(`${jobs.length} saved jobs`);
  if (!selectedId && jobs[0]) selectedId = jobs[0].id;
  renderList();
  if (selectedId) selectJob(selectedId);
}

async function refreshJobs() {
  refreshBtn.disabled = true;
  setStatus("Fetching from Himalayas…");
  try {
    const response = await fetch("/api/fetch", { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Fetch failed");
    jobs = data.jobs || [];
    selectedId = jobs[0]?.id || null;
    setStatus(`Fetched ${jobs.length} jobs`);
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

loadJobs().catch((error) => setStatus(error.message));
