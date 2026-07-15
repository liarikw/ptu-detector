const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const LOADING_MESSAGES = [
  "Warming up the sus-o-meter…",
  "Consulting the P图 Detective…",
  "Measuring pixel densities…",
  "Sniffing for Facetune residue…",
  "Cross-checking doorframe geometry…",
  "Calibrating the roast circuits…",
  "Deploying forensic raccoon…",
];

async function resizeImage(file, maxDim = 1600, quality = 0.85) {
  // Skip resize for GIFs (animation would be lost) and tiny files
  if (file.type === "image/gif" || file.size < 500 * 1024) return file;

  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const im = new Image();
      im.onload = () => resolve(im);
      im.onerror = () => reject(new Error("Failed to decode image"));
      im.src = url;
    });

    const { width, height } = img;
    if (width <= maxDim && height <= maxDim) return file;

    const scale = maxDim / Math.max(width, height);
    const w = Math.round(width * scale);
    const h = Math.round(height * scale);

    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    canvas.getContext("2d").drawImage(img, 0, 0, w, h);

    return await new Promise((resolve) => {
      canvas.toBlob(
        (blob) => {
          const newName = file.name.replace(/\.[^.]+$/, "") + ".jpg";
          resolve(new File([blob], newName, { type: "image/jpeg" }));
        },
        "image/jpeg",
        quality
      );
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

let selectedFiles = [];

$$(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    $$(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`#panel-${tab.dataset.tab}`).classList.add("active");
  });
});

const drop = $("#drop");
const fileInput = $("#fileInput");
const thumbs = $("#thumbs");
const goUpload = $("#goUpload");

drop.addEventListener("dragover", (e) => {
  e.preventDefault();
  drop.classList.add("dragover");
});
drop.addEventListener("dragleave", () => drop.classList.remove("dragover"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("dragover");
  handleFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", (e) => handleFiles(e.target.files));

function handleFiles(fileList) {
  selectedFiles = [...fileList].filter((f) => f.type.startsWith("image/")).slice(0, 8);
  thumbs.innerHTML = "";
  selectedFiles.forEach((f) => {
    const img = document.createElement("img");
    img.src = URL.createObjectURL(f);
    thumbs.appendChild(img);
  });
  goUpload.disabled = selectedFiles.length === 0;
}

goUpload.addEventListener("click", async () => {
  if (!selectedFiles.length) return;
  goUpload.disabled = true;
  const original = goUpload.textContent;
  goUpload.textContent = "Shrinking images…";
  try {
    const resized = await Promise.all(selectedFiles.map((f) => resizeImage(f)));
    const fd = new FormData();
    resized.forEach((f) => fd.append("files", f));
    goUpload.textContent = original;
    await runRequest("/api/analyze/upload", fd, resized.map((f) => URL.createObjectURL(f)));
  } finally {
    goUpload.disabled = false;
    goUpload.textContent = original;
  }
});

$("#goUrl").addEventListener("click", async () => {
  const url = $("#urlInput").value.trim();
  if (!url) return;
  const fd = new FormData();
  fd.append("url", url);
  await runRequest("/api/analyze/url", fd);
});

$("#goProfile").addEventListener("click", async () => {
  const username = $("#profileInput").value.trim();
  if (!username) return;
  const fd = new FormData();
  fd.append("username", username);
  await runRequest("/api/analyze/profile", fd);
});

async function runRequest(endpoint, formData, previewUrls = []) {
  const loading = $("#loading");
  const results = $("#results");
  const status = $("#status");

  results.hidden = true;
  loading.hidden = false;
  const messageInterval = setInterval(() => {
    status.textContent = LOADING_MESSAGES[Math.floor(Math.random() * LOADING_MESSAGES.length)];
  }, 1800);
  status.textContent = LOADING_MESSAGES[0];

  try {
    const res = await fetch(endpoint, { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `HTTP ${res.status}`);
    }
    renderResults(data, previewUrls);
  } catch (err) {
    renderError(err.message || String(err));
  } finally {
    clearInterval(messageInterval);
    loading.hidden = true;
  }
}

function renderError(message) {
  const results = $("#results");
  results.innerHTML = `<div class="error">🥲 ${escapeHtml(message)}</div>`;
  results.hidden = false;
}

function scoreColor(score) {
  if (score <= 30) return "var(--good)";
  if (score <= 60) return "var(--meh)";
  return "var(--bad)";
}

function renderResults(data, previewUrls) {
  const results = $("#results");
  results.hidden = false;
  results.innerHTML = "";

  const score = data.aggregate_score ?? 0;
  const verdict = data.aggregate_verdict ?? "Inconclusive";

  const scoreCard = document.createElement("div");
  scoreCard.className = "score-card";
  scoreCard.innerHTML = `
    <div class="score-ring">
      <svg viewBox="0 0 120 120">
        <circle class="ring-bg" cx="60" cy="60" r="52"></circle>
        <circle class="ring-fg" id="ringFg" cx="60" cy="60" r="52" transform="rotate(-90 60 60)"></circle>
      </svg>
      <div class="score-num" id="scoreNum">${data.aggregate_score ?? "?"}</div>
      <div class="score-label">SUS SCORE</div>
    </div>
    <div class="verdict-box">
      <div class="verdict-label">Verdict</div>
      <div class="verdict">${escapeHtml(verdict)}</div>
      <div class="meta">${data.image_count ?? data.images?.length ?? 0} image(s) analyzed
        ${data.username ? ` · @${escapeHtml(data.username)}` : ""}
      </div>
    </div>
  `;
  results.appendChild(scoreCard);

  requestAnimationFrame(() => {
    const ring = document.getElementById("ringFg");
    if (ring) {
      const circ = 327;
      ring.style.strokeDashoffset = String(circ - (circ * score) / 100);
      ring.style.stroke = scoreColor(score);
    }
  });

  const imagesEl = document.createElement("div");
  imagesEl.className = "images";
  (data.images || []).forEach((img, i) => {
    const card = document.createElement("div");
    card.className = "image-card";
    if (img.error) {
      card.innerHTML = `<div class="error">Image ${i + 1}: ${escapeHtml(img.error)}</div>`;
    } else {
      const previewSrc = previewUrls[i] || "";
      card.innerHTML = `
        ${previewSrc ? `<img src="${previewSrc}" alt="image ${i + 1}">` : ""}
        <div class="image-body">
          <span class="image-score" style="background: ${scoreColor(img.sus_score)}">${img.sus_score}/100</span>
          <div class="image-verdict">${escapeHtml(img.verdict)}</div>
          <div class="image-roast">${escapeHtml(img.roast)}</div>
          <ul class="findings">
            ${(img.findings || []).map((f) => `<li>${escapeHtml(f)}</li>`).join("")}
          </ul>
        </div>
      `;
    }
    imagesEl.appendChild(card);
  });
  results.appendChild(imagesEl);

  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
