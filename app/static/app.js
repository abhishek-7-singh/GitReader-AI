// GitReader AI Frontend Controller

let activeRepo = "";
let currentTreeData = null;

// DOM Elements
const activeRepoSelect = document.getElementById("activeRepoSelect");
const btnSyncRepo = document.getElementById("btnSyncRepo");
const ollamaStatusBadge = document.getElementById("ollamaStatusBadge");
const ollamaStatusText = document.getElementById("ollamaStatusText");
const lblChatModel = document.getElementById("lblChatModel");
const lblEmbedModel = document.getElementById("lblEmbedModel");

// Modals & Ingestion
const ingestModal = document.getElementById("ingestModal");
const btnOpenIngestModal = document.getElementById("btnOpenIngestModal");
const btnCloseModal = document.getElementById("btnCloseModal");
const btnCancelModal = document.getElementById("btnCancelModal");
const ingestForm = document.getElementById("ingestForm");
const btnSubmitIngest = document.getElementById("btnSubmitIngest");

// Toast
const toast = document.getElementById("toast");

function showToast(message, duration = 3500) {
  toast.textContent = message;
  toast.style.display = "block";
  setTimeout(() => {
    toast.style.display = "none";
  }, duration);
}

// TAB NAVIGATION
document.querySelectorAll(".nav-item").forEach(button => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
    
    button.classList.add("active");
    const targetTab = button.getAttribute("data-tab");
    document.getElementById(targetTab)?.classList.add("active");

    // Load data for active tab
    if (targetTab === "tab-tree") loadFolderTree();
    if (targetTab === "tab-logbook") loadLogbook();
    if (targetTab === "tab-documents") loadDocuments();
  });
});

// INITIALIZATION
document.addEventListener("DOMContentLoaded", () => {
  checkOllamaStatus();
  loadRepositories();

  // Tab view toggles
  document.getElementById("btnTreeAsciiView")?.addEventListener("click", (e) => {
    e.target.classList.add("active");
    document.getElementById("btnTreeVisualView")?.classList.remove("active");
    document.getElementById("asciiTreeOutput").style.display = "block";
    document.getElementById("visualTreeOutput").style.display = "none";
  });

  document.getElementById("btnTreeVisualView")?.addEventListener("click", (e) => {
    e.target.classList.add("active");
    document.getElementById("btnTreeAsciiView")?.classList.remove("active");
    document.getElementById("asciiTreeOutput").style.display = "none";
    document.getElementById("visualTreeOutput").style.display = "block";
  });
});

// 1. OLLAMA STATUS CHECK
async function checkOllamaStatus() {
  try {
    const res = await fetch("/ollama/status");
    const data = await res.json();
    if (data.connected) {
      ollamaStatusBadge.className = "status-badge online";
      ollamaStatusText.textContent = `Ollama Online (${data.active_chat_model})`;
      lblChatModel.textContent = data.active_chat_model;
      lblEmbedModel.textContent = data.active_embed_model;
    } else {
      ollamaStatusBadge.className = "status-badge offline";
      ollamaStatusText.textContent = "Ollama Offline";
    }
  } catch (err) {
    ollamaStatusBadge.className = "status-badge offline";
    ollamaStatusText.textContent = "Ollama Unreachable";
  }
}

// 2. REPOSITORIES MANAGEMENT
async function loadRepositories() {
  try {
    const res = await fetch("/repositories");
    const data = await res.json();
    const repos = data.repositories || [];

    // Update Stats
    document.getElementById("statRepoCount").textContent = repos.length;

    // Populate Selector
    activeRepoSelect.innerHTML = `<option value="">-- Select Repository --</option>`;
    repos.forEach(r => {
      const opt = document.createElement("option");
      opt.value = r.name;
      opt.textContent = `${r.name} (${r.default_branch || 'main'})`;
      activeRepoSelect.appendChild(opt);
    });

    if (repos.length > 0 && !activeRepo) {
      activeRepo = repos[0].name;
      activeRepoSelect.value = activeRepo;
      onRepoChanged();
    }

    renderRepoTable(repos);
  } catch (err) {
    console.error("Failed to load repositories:", err);
  }
}

function renderRepoTable(repos) {
  const container = document.getElementById("repoListContainer");
  if (!repos || repos.length === 0) {
    container.innerHTML = `<div class="empty-state">No repositories indexed yet. Click "Ingest Repo" above to get started.</div>`;
    return;
  }

  let html = `
    <table class="repo-table">
      <thead>
        <tr>
          <th>Repository</th>
          <th>Location / URL</th>
          <th>Branch</th>
          <th>Latest Commit</th>
          <th>Last Indexed</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
  `;

  repos.forEach(r => {
    const lastIndexed = r.last_indexed_at ? new Date(r.last_indexed_at).toLocaleTimeString() : 'Never';
    const commitShort = r.last_commit_sha ? r.last_commit_sha.substring(0, 8) : 'HEAD';
    html += `
      <tr>
        <td class="repo-name-cell">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
          <strong>${r.name}</strong>
        </td>
        <td style="font-family: var(--font-mono); font-size: 0.78rem;">${r.url || r.path}</td>
        <td><span class="commit-badge">${r.default_branch || 'main'}</span></td>
        <td><span class="commit-badge">${commitShort}</span></td>
        <td style="color: var(--text-dim); font-size: 0.78rem;">${lastIndexed}</td>
        <td>
          <button class="btn-secondary small" onclick="selectAndSwitchRepo('${r.name}')">Select</button>
        </td>
      </tr>
    `;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

window.selectAndSwitchRepo = function(name) {
  activeRepo = name;
  activeRepoSelect.value = name;
  onRepoChanged();
  showToast(`Switched active repository to "${name}"`);
};

activeRepoSelect.addEventListener("change", (e) => {
  activeRepo = e.target.value;
  onRepoChanged();
});

function onRepoChanged() {
  if (!activeRepo) return;
  loadFolderTree();
  loadLogbook();
  loadDocuments();
}

// Sync / Pull Repository
btnSyncRepo.addEventListener("click", async () => {
  if (!activeRepo) {
    showToast("Please select a repository first.");
    return;
  }
  btnSyncRepo.style.transform = "rotate(180deg)";
  showToast(`Syncing Git repository "${activeRepo}"...`);
  try {
    const res = await fetch(`/repositories/${encodeURIComponent(activeRepo)}/sync`, { method: "POST" });
    const data = await res.json();
    btnSyncRepo.style.transform = "none";
    if (res.ok) {
      showToast(`Repository synced! ${data.indexed_chunks || 0} chunks updated.`);
      loadRepositories();
      loadLogbook();
    } else {
      showToast(`Sync failed: ${data.detail}`);
    }
  } catch (err) {
    btnSyncRepo.style.transform = "none";
    showToast(`Sync error: ${err.message}`);
  }
});

// 3. FOLDER STRUCTURE EXPLORER
async function loadFolderTree() {
  if (!activeRepo) return;
  const asciiPre = document.getElementById("asciiTreeOutput");
  const langBar = document.getElementById("treeLangContainer");
  asciiPre.textContent = `Loading folder structure for "${activeRepo}"...`;

  try {
    const res = await fetch(`/repositories/${encodeURIComponent(activeRepo)}/tree`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    currentTreeData = data;
    asciiPre.textContent = data.ascii_tree || "No files indexed in repository.";

    // Render language chips
    langBar.innerHTML = "";
    const extensions = (data.tree_stats && data.tree_stats.extensions) || {};
    Object.entries(extensions).forEach(([ext, count]) => {
      const chip = document.createElement("div");
      chip.className = "lang-chip";
      chip.innerHTML = `<span>${ext || 'misc'}:</span> <strong>${count} files</strong>`;
      langBar.appendChild(chip);
    });

    renderVisualTree(data.nested_tree);
  } catch (err) {
    asciiPre.textContent = `Error loading tree: ${err.message}`;
  }
}

function renderVisualTree(nested) {
  const container = document.getElementById("visualTreeOutput");
  if (!nested) {
    container.innerHTML = `<div class="empty-state">No tree available.</div>`;
    return;
  }

  function renderNode(node) {
    if (node.type === "directory") {
      let childrenHtml = (node.children || []).map(renderNode).join("");
      return `
        <div style="margin-left: 18px; margin-top: 4px;">
          <div style="display:flex; align-items:center; gap:6px; color:#c7d2fe; font-weight:600; font-size:0.86rem;">
            <span>📁</span> ${node.name}
          </div>
          <div style="border-left: 1px dashed rgba(255,255,255,0.1); margin-left: 6px;">
            ${childrenHtml}
          </div>
        </div>
      `;
    } else {
      return `
        <div style="margin-left: 18px; margin-top: 2px; font-size:0.82rem; color: #94a3b8; font-family: var(--font-mono); display:flex; gap:6px;">
          <span>📄</span> ${node.name} <span style="color:#64748b;">(${node.extension || ''})</span>
        </div>
      `;
    }
  }

  container.innerHTML = renderNode(nested);
}

// 4. DEVELOPER PUSH LOGBOOK
async function loadLogbook() {
  if (!activeRepo) return;
  const container = document.getElementById("logbookTimeline");
  try {
    const res = await fetch(`/repositories/${encodeURIComponent(activeRepo)}/logbook?limit=50`);
    const data = await res.json();
    const entries = data.entries || [];

    document.getElementById("statLogbookCount").textContent = entries.length;

    if (entries.length === 0) {
      container.innerHTML = `<div class="empty-state">No push events recorded yet for "${activeRepo}".</div>`;
      return;
    }

    let html = "";
    entries.forEach(entry => {
      const timeStr = entry.created_at ? new Date(entry.created_at).toLocaleString() : 'Recent';
      const shaShort = entry.sha ? entry.sha.substring(0, 8) : 'HEAD';
      html += `
        <div class="log-entry">
          <div class="log-header">
            <div class="log-author">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
              <span>${entry.author || 'Developer'}</span>
              <span class="commit-badge">${shaShort}</span>
            </div>
            <span class="log-time">${timeStr}</span>
          </div>
          <div class="log-summary">${entry.summary}</div>
          <div class="log-tags">
            ${entry.diff_stat ? `<span class="diff-badge">${entry.diff_stat}</span>` : ''}
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load logbook: ${err.message}</div>`;
  }
}

document.getElementById("btnRefreshLogbook")?.addEventListener("click", () => {
  loadLogbook();
  showToast("Logbook refreshed!");
});

// 5. AI RELEASE NOTES GENERATION
const btnGenerateReleaseNotes = document.getElementById("btnGenerateReleaseNotes");
const releaseNotesOutput = document.getElementById("releaseNotesOutput");
const btnCopyReleaseNotes = document.getElementById("btnCopyReleaseNotes");

btnGenerateReleaseNotes?.addEventListener("click", async () => {
  if (!activeRepo) {
    showToast("Please select a repository first.");
    return;
  }

  const version = document.getElementById("relVersionInput").value || "v1.0.0";
  const limit = parseInt(document.getElementById("relLimitInput").value) || 20;

  btnGenerateReleaseNotes.disabled = true;
  btnGenerateReleaseNotes.innerHTML = `<span>Synthesizing with AI...</span>`;
  releaseNotesOutput.innerHTML = `<p class="text-muted">⏳ Reading developer commits and generating release notes with Ollama...</p>`;

  try {
    const res = await fetch(`/repositories/${encodeURIComponent(activeRepo)}/release-notes/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repository: activeRepo, version, limit })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    // Simple markdown renderer for preview
    const formatted = formatMarkdown(data.release_notes);
    releaseNotesOutput.innerHTML = formatted;
    showToast(`Release notes generated successfully!`);
  } catch (err) {
    releaseNotesOutput.innerHTML = `<p style="color:var(--color-rose);">Error generating release notes: ${err.message}</p>`;
  } finally {
    btnGenerateReleaseNotes.disabled = false;
    btnGenerateReleaseNotes.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
      <span>Generate with AI</span>
    `;
  }
});

btnCopyReleaseNotes?.addEventListener("click", () => {
  const text = releaseNotesOutput.innerText;
  navigator.clipboard.writeText(text);
  showToast("Release notes copied to clipboard!");
});

function formatMarkdown(text) {
  if (!text) return "";
  let html = text
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/^- (.*$)/gim, '<li>$1</li>')
    .replace(/\n\n/gim, '<br><br>');
  return html;
}

// 6. DOCUMENT DRAG & DROP & UPLOAD
const dropZone = document.getElementById("dropZone");
const fileUploadInput = document.getElementById("fileUploadInput");
const btnBrowseFile = document.getElementById("btnBrowseFile");

btnBrowseFile?.addEventListener("click", () => fileUploadInput.click());
dropZone?.addEventListener("click", (e) => {
  if (e.target !== btnBrowseFile) fileUploadInput.click();
});

dropZone?.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone?.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone?.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer.files.length > 0) {
    handleFileUpload(e.dataTransfer.files[0]);
  }
});

fileUploadInput?.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    handleFileUpload(e.target.files[0]);
  }
});

async function handleFileUpload(file) {
  if (!activeRepo) {
    showToast("Please select a repository first.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("repository", activeRepo);

  showToast(`Parsing and indexing "${file.name}"...`);

  try {
    const res = await fetch("/documents/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    showToast(`Successfully indexed ${file.name} (${data.indexed_chunks} chunks)!`);
    loadDocuments();
  } catch (err) {
    showToast(`Upload failed: ${err.message}`);
  }
}

async function loadDocuments() {
  const container = document.getElementById("docsListContainer");
  try {
    const res = await fetch(`/documents?repository=${encodeURIComponent(activeRepo || '')}`);
    const data = await res.json();
    const docs = data.documents || [];

    document.getElementById("statDocsCount").textContent = docs.length;

    if (docs.length === 0) {
      container.innerHTML = `<div class="empty-state">No documents indexed for this repository.</div>`;
      return;
    }

    let html = `
      <table class="repo-table">
        <thead>
          <tr>
            <th>Filename</th>
            <th>Type</th>
            <th>Chunks</th>
            <th>Uploaded At</th>
          </tr>
        </thead>
        <tbody>
    `;

    docs.forEach(d => {
      html += `
        <tr>
          <td><strong>📄 ${d.filename}</strong></td>
          <td><span class="commit-badge">${d.file_type || 'doc'}</span></td>
          <td>${d.chunk_count} vectors</td>
          <td style="color:var(--text-dim); font-size:0.78rem;">${new Date(d.uploaded_at).toLocaleString()}</td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error: ${err.message}</div>`;
  }
}

// 7. RAG CHATBOT
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

chatForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = chatInput.value.trim();
  if (!q) return;

  appendUserMessage(q);
  chatInput.value = "";

  const botPlaceholder = appendBotPlaceholder();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, repository: activeRepo || null })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    updateBotMessage(botPlaceholder, data.answer, data.sources);
  } catch (err) {
    updateBotMessage(botPlaceholder, `Error answering question: ${err.message}`, []);
  }
});

// Quick suggestion chips
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("suggestion-chip")) {
    chatInput.value = e.target.textContent;
    chatForm.dispatchEvent(new Event("submit"));
  }
});

function appendUserMessage(text) {
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble user";
  bubble.innerHTML = `
    <div class="bubble-header"><span class="bot-name" style="color:white;">You</span></div>
    <div class="bubble-content">${escapeHtml(text)}</div>
  `;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendBotPlaceholder() {
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble bot";
  bubble.innerHTML = `
    <div class="bubble-header"><span class="bot-name">🤖 GitReader AI</span></div>
    <div class="bubble-content"><em>Thinking and retrieving relevant repository context...</em></div>
  `;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return bubble;
}

function updateBotMessage(element, answer, sources = []) {
  let sourcesHtml = "";
  if (sources && sources.length > 0) {
    sourcesHtml = `
      <div class="source-citations">
        <strong>Retrieved Sources:</strong><br>
        ${sources.map(s => `
          <span class="citation-badge" title="${escapeHtml(s.snippet || '')}">
            ${escapeHtml(s.file)} [${escapeHtml(s.commit || 'head').substring(0, 7)}]
          </span>
        `).join("")}
      </div>
    `;
  }

  element.innerHTML = `
    <div class="bubble-header"><span class="bot-name">🤖 GitReader AI</span></div>
    <div class="bubble-content">${formatMarkdown(answer)}</div>
    ${sourcesHtml}
  `;
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
  if (!text) return "";
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// 8. PUSH WEBHOOK SIMULATOR
const btnSendSimulatedPush = document.getElementById("btnSendSimulatedPush");
const simResult = document.getElementById("simResult");

btnSendSimulatedPush?.addEventListener("click", async () => {
  if (!activeRepo) {
    showToast("Please select a repository first.");
    return;
  }

  const author = document.getElementById("simAuthor").value || "Developer";
  const message = document.getElementById("simMessage").value || "feat: update components";
  const added = document.getElementById("simAdded").value.split(",").map(s => s.trim()).filter(Boolean);
  const modified = document.getElementById("simModified").value.split(",").map(s => s.trim()).filter(Boolean);

  const mockPayload = {
    repository: { name: activeRepo, full_name: `org/${activeRepo}` },
    commits: [
      {
        id: "sim" + Math.random().toString(16).substring(2, 10),
        author: { name: author, email: "dev@example.com" },
        message: message,
        timestamp: new Date().toISOString(),
        added: added,
        modified: modified,
        removed: []
      }
    ]
  };

  btnSendSimulatedPush.disabled = true;
  try {
    const res = await fetch("/webhooks/github", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-GitHub-Event": "push"
      },
      body: JSON.stringify(mockPayload)
    });
    const data = await res.json();
    simResult.style.display = "block";
    simResult.textContent = JSON.stringify(data, null, 2);
    showToast("Push webhook triggered! Logbook updated.");
    loadLogbook();
  } catch (err) {
    simResult.style.display = "block";
    simResult.textContent = `Error: ${err.message}`;
  } finally {
    btnSendSimulatedPush.disabled = false;
  }
});

// 9. INGEST MODAL
btnOpenIngestModal?.addEventListener("click", () => {
  ingestModal.style.display = "flex";
});

btnCloseModal?.addEventListener("click", () => {
  ingestModal.style.display = "none";
});

btnCancelModal?.addEventListener("click", () => {
  ingestModal.style.display = "none";
});

ingestForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("ingestName").value.trim();
  const path = document.getElementById("ingestPath").value.trim();
  const branch = document.getElementById("ingestBranch").value.trim() || null;

  btnSubmitIngest.disabled = true;
  btnSubmitIngest.innerHTML = `<span>Ingesting & Indexing...</span>`;

  try {
    const res = await fetch("/repositories/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, path, branch })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    showToast(`Successfully ingested "${name}"! (${data.indexed_chunks} code chunks indexed)`);
    ingestModal.style.display = "none";
    ingestForm.reset();
    await loadRepositories();
    selectAndSwitchRepo(name);
  } catch (err) {
    showToast(`Ingestion error: ${err.message}`);
  } finally {
    btnSubmitIngest.disabled = false;
    btnSubmitIngest.innerHTML = `<span>Ingest & Index</span>`;
  }
});
