const fileInput = document.querySelector("#fileInput");
const dropZone = document.querySelector("#dropZone");
const fileList = document.querySelector("#fileList");
const processButton = document.querySelector("#processButton");
const confirmUpdateButton = document.querySelector("#confirmUpdateButton");
const progressBar = document.querySelector("#progressBar");
const statusText = document.querySelector("#status");
const downloadBlocklist = document.querySelector("#downloadBlocklist");
const downloadBase = document.querySelector("#downloadBase");
const downloadReport = document.querySelector("#downloadReport");
const themeToggle = document.querySelector("#themeToggle");
const viewWhitelist = document.querySelector("#viewWhitelist");
const whitelistDialog = document.querySelector("#whitelistDialog");
const closeWhitelist = document.querySelector("#closeWhitelist");
const whitelistContent = document.querySelector("#whitelistContent");
const blocklistPreview = document.querySelector("#blocklistPreview");
const whitelistPreview = document.querySelector("#whitelistPreview");
const blocklistMeta = document.querySelector("#blocklistMeta");
const whitelistMeta = document.querySelector("#whitelistMeta");
const blocklistPrev = document.querySelector("#blocklistPrev");
const blocklistNext = document.querySelector("#blocklistNext");
const warningsList = document.querySelector("#warningsList");
const tabButtons = document.querySelectorAll(".tab-button");
const tabPanels = document.querySelectorAll(".tab-panel");
const refreshHistory = document.querySelector("#refreshHistory");
const historyStatus = document.querySelector("#historyStatus");
const historyTableBody = document.querySelector("#historyTableBody");

let selectedFiles = [];
let blocklistItems = [];
let approvedDomains = new Set();
let blocklistPage = 0;
let currentRunId = null;
let historyLoaded = false;
const pageSize = 100;

function setStatus(message, type = "info") {
  statusText.textContent = message;
  statusText.dataset.type = type;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderWarnings(errors) {
  if (!warningsList) return;
  if (!errors || !errors.length) {
    warningsList.style.display = "none";
    warningsList.innerHTML = "";
    return;
  }

  const grouped = new Map();
  errors.forEach((error) => {
    grouped.set(error, (grouped.get(error) || 0) + 1);
  });

  const items = Array.from(grouped.entries())
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([message, count]) => `
      <li>
        <span>${escapeHtml(message)}</span>
        ${count > 1 ? `<strong>${count}x</strong>` : ""}
      </li>
    `)
    .join("");

  warningsList.style.display = "block";
  warningsList.innerHTML = `
    <div class="warnings-header">
      <strong>Avisos do processamento</strong>
      <span>${errors.length} aviso(s)</span>
    </div>
    <details class="warnings-details">
      <summary>Ver detalhes</summary>
      <ul>${items}</ul>
    </details>
  `;
}

function updateDownloadLinks() {
  const query = currentRunId ? `?run_id=${encodeURIComponent(currentRunId)}` : "";
  downloadBlocklist.href = `/download/novos_dominios${query}`;
  downloadReport.href = `/download/relatorio${query}`;
  downloadBase.href = `/download/base_atualizada${query}`;
}

function setActiveTab(targetId) {
  tabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tabTarget === targetId);
  });
  tabPanels.forEach((panel) => {
    const active = panel.id === targetId;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });

  if (targetId === "historyPanel" && !historyLoaded) {
    loadAuditHistory();
  }
}

function formatHistoryList(items, emptyText = "-") {
  if (!items || !items.length) return emptyText;
  return items.join(", ");
}

function setHistoryStatus(message, type = "info") {
  historyStatus.textContent = message;
  historyStatus.dataset.type = type;
}

function appendHistoryCell(row, text, className = "") {
  const cell = document.createElement("td");
  cell.textContent = text;
  if (className) cell.className = className;
  row.appendChild(cell);
}

function renderHistoryRows(runs) {
  historyTableBody.innerHTML = "";
  if (!runs.length) {
    const row = document.createElement("tr");
    appendHistoryCell(row, "Nenhuma execução registrada ainda.");
    row.firstChild.colSpan = 10;
    historyTableBody.appendChild(row);
    return;
  }

  runs.forEach((run) => {
    const row = document.createElement("tr");
    appendHistoryCell(row, run.created_at || "-");
    appendHistoryCell(row, run.run_id || "-", "mono-cell");
    appendHistoryCell(row, formatHistoryList(run.files), "wide-cell");
    appendHistoryCell(row, String(run.domains_extracted ?? 0), "number-cell");
    appendHistoryCell(row, String(run.new_domains ?? 0), "number-cell");
    appendHistoryCell(row, String(run.whitelist_count ?? 0), "number-cell");
    appendHistoryCell(row, String(run.blocklist_count ?? 0), "number-cell");
    appendHistoryCell(row, String(run.duplicates_removed ?? 0), "number-cell");
    appendHistoryCell(row, `${run.elapsed_seconds ?? 0}s`, "number-cell");
    appendHistoryCell(row, formatHistoryList(run.errors, "Nenhum"), "wide-cell");
    historyTableBody.appendChild(row);
  });
}

async function loadAuditHistory() {
  setHistoryStatus("Carregando histórico...", "info");
  try {
    const response = await fetch("/audit-history");
    const data = await response.json();
    if (!response.ok) {
      setHistoryStatus(data.error || "Falha ao carregar histórico.", "error");
      return;
    }

    const runs = data.runs || [];
    renderHistoryRows(runs);
    historyLoaded = true;
    setHistoryStatus(runs.length ? `${runs.length} execuções carregadas.` : "Nenhuma execução registrada.", "success");
  } catch (_error) {
    setHistoryStatus("Erro de comunicação ao carregar histórico.", "error");
  }
}

function updateFileList() {
  fileList.innerHTML = "";
  if (!selectedFiles.length) {
    fileList.innerHTML = '<li class="empty-state">Nenhum arquivo selecionado.</li>';
    processButton.disabled = true;
    confirmUpdateButton.disabled = true;
    return;
  }

  selectedFiles.forEach((file) => {
    const item = document.createElement("li");
    const extension = file.name.split(".").pop().toUpperCase();
    item.innerHTML = `<span class="file-type">${extension}</span><span class="file-name">${file.name}</span><span class="file-size">${(file.size / 1024 / 1024).toFixed(2)}MB</span>`;
    fileList.appendChild(item);
  });
  processButton.disabled = false;
}

function renderBlocklistPage() {
  const total = blocklistItems.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  blocklistPage = Math.min(blocklistPage, pages - 1);
  const start = blocklistPage * pageSize;
  const pageItems = blocklistItems.slice(start, start + pageSize);
  const approvedCount = blocklistItems.filter((domain) => approvedDomains.has(domain)).length;
  const rejectedCount = total - approvedCount;
  const specificTargetCount = blocklistItems.filter((item) => item.includes("/") || item.includes("?")).length;
  const domainCount = total - specificTargetCount;

  blocklistPreview.innerHTML = "";

  if (!pageItems.length) {
    blocklistPreview.textContent = "Nenhum dominio novo para bloqueio.";
  } else {
    const header = document.createElement("div");
    header.className = "review-list-header";
    header.textContent = `Secao ${blocklistPage + 1} de ${pages} - Mostrando ${start + 1}-${start + pageItems.length} de ${total}`;
    blocklistPreview.appendChild(header);

    pageItems.forEach((domain) => {
      const label = document.createElement("label");
      label.className = "review-domain";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = approvedDomains.has(domain);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          approvedDomains.add(domain);
        } else {
          approvedDomains.delete(domain);
        }
        renderBlocklistPage();
      });

      const text = document.createElement("span");
      text.textContent = domain;

      const type = document.createElement("span");
      type.className = "review-domain-type";
      type.textContent = domain.includes("/") || domain.includes("?") ? "URL especifica" : "Dominio";

      label.appendChild(checkbox);
      label.appendChild(text);
      label.appendChild(type);
      blocklistPreview.appendChild(label);
    });
  }

  blocklistMeta.textContent = total
    ? `${approvedCount} aprovados; ${rejectedCount} rejeitados; ${domainCount} dominios; ${specificTargetCount} URLs especificas`
    : "0 alvos novos";
  blocklistPrev.disabled = blocklistPage === 0 || total === 0;
  blocklistNext.disabled = blocklistPage >= pages - 1 || total === 0;
}

function renderWhitelist(items) {
  whitelistPreview.textContent = items.length
    ? items.map((item) => `${item.domain} (${item.category}) - ${item.reason}`).join("\n")
    : "Nenhum dominio protegido.";
  whitelistMeta.textContent = items.length ? `${items.length} dominios protegidos` : "0 dominios protegidos";
}

function acceptFiles(files) {
  const allowed = [".txt", ".pdf"];
  selectedFiles = Array.from(files).filter((file) => {
    const lower = file.name.toLowerCase();
    return allowed.some((extension) => lower.endsWith(extension));
  });
  updateFileList();
  confirmUpdateButton.disabled = true;
  downloadBase.classList.add("disabled");
  downloadBlocklist.classList.add("disabled");
  downloadReport.classList.add("disabled");
  blocklistItems = [];
  approvedDomains = new Set();
  blocklistPage = 0;
  renderBlocklistPage();
  renderWhitelist([]);
  currentRunId = null;
  updateDownloadLinks();
  if (warningsList) {
    warningsList.style.display = "none";
    warningsList.innerHTML = "";
  }
  setStatus(selectedFiles.length ? "Arquivos prontos para processamento." : "Nenhum arquivo válido selecionado.");
}

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => acceptFiles(fileInput.files));

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("active");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("active");
  });
});

dropZone.addEventListener("drop", (event) => acceptFiles(event.dataTransfer.files));

processButton.addEventListener("click", () => {
  if (!selectedFiles.length) return;

  const formData = new FormData();
  selectedFiles.forEach((file) => formData.append("files", file));

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/process");
  processButton.disabled = true;
  progressBar.style.width = "0%";
  downloadBase.classList.add("disabled");
  confirmUpdateButton.disabled = true;
  setStatus("Enviando e processando arquivos...");

  xhr.upload.addEventListener("progress", (event) => {
    if (event.lengthComputable) {
      progressBar.style.width = `${Math.round((event.loaded / event.total) * 100)}%`;
    }
  });

  xhr.addEventListener("load", () => {
    progressBar.style.width = "100%";
    let response = {};
    try {
      response = JSON.parse(xhr.responseText || "{}");
    } catch (_error) {
      processButton.disabled = false;
      setStatus("O servidor retornou uma resposta inesperada. Verifique a janela do servidor.", "error");
      return;
    }

    if (xhr.status >= 400) {
      processButton.disabled = false;
      setStatus(response.error || "Falha no processamento.", "error");
      return;
    }

    processButton.disabled = true;
    currentRunId = response.run_id || null;
    document.querySelector("#domainsExtracted").textContent = response.domains_extracted;
    document.querySelector("#newDomains").textContent = response.new_domains;
    document.querySelector("#whitelistCount").textContent = response.whitelist_count;
    document.querySelector("#blocklistCount").textContent = response.blocklist_count;
    blocklistItems = response.blocklist || response.preview_blocklist || [];
    approvedDomains = new Set(blocklistItems);
    blocklistPage = 0;
    renderBlocklistPage();
    renderWhitelist(response.whitelist || response.preview_whitelist || []);
    updateDownloadLinks();

    downloadBlocklist.classList.remove("disabled");
    downloadReport.classList.remove("disabled");
    confirmUpdateButton.disabled = !response.pending_update_available;

    renderWarnings(response.errors || []);

    setStatus(`Extração concluída em ${response.elapsed_seconds}s. Descartados: ${response.existing_discarded_count}. Revise e confirme para atualizar a base.`, "success");
  });

  xhr.addEventListener("error", () => {
    processButton.disabled = false;
    setStatus("Erro de comunicacao com o servidor local.", "error");
  });

  xhr.send(formData);
});

confirmUpdateButton.addEventListener("click", async () => {
  confirmUpdateButton.disabled = true;
  setStatus("Atualizando base...", "info");

  try {
    const response = await fetch("/confirm-update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_id: currentRunId,
        approved_domains: blocklistItems.filter((domain) => approvedDomains.has(domain)),
        rejected_domains: blocklistItems.filter((domain) => !approvedDomains.has(domain)),
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      setStatus(data.error || "Falha ao atualizar a base.", "error");
      confirmUpdateButton.disabled = false;
      return;
    }

    downloadBase.classList.remove("disabled");
    setStatus(`Base atualizada. Adicionados: ${data.added_count}. Rejeitados: ${data.rejected_count || 0}. Já existentes ignorados: ${data.ignored_existing_count}. Arquivo: ${data.updated_base_file}`, "success");
  } catch (_error) {
    setStatus("Erro de comunicação ao atualizar a base.", "error");
    confirmUpdateButton.disabled = false;
  }
});

themeToggle.addEventListener("click", () => {
  document.body.classList.toggle("dark");
  themeToggle.textContent = document.body.classList.contains("dark") ? "Modo claro" : "Modo escuro";
});

blocklistPrev.addEventListener("click", () => {
  blocklistPage -= 1;
  renderBlocklistPage();
});

blocklistNext.addEventListener("click", () => {
  blocklistPage += 1;
  renderBlocklistPage();
});

viewWhitelist.addEventListener("click", async () => {
  whitelistContent.textContent = "Carregando...";
  whitelistDialog.showModal();
  const query = currentRunId ? `?run_id=${encodeURIComponent(currentRunId)}` : "";
  const response = await fetch(`/whitelist${query}`);
  const data = await response.json();
  whitelistContent.textContent = data.content || "Whitelist ainda nao gerada.";
});

closeWhitelist.addEventListener("click", () => whitelistDialog.close());

tabButtons.forEach((button) => {
  button.addEventListener("click", () => setActiveTab(button.dataset.tabTarget));
});

refreshHistory.addEventListener("click", () => {
  historyLoaded = false;
  loadAuditHistory();
});

updateDownloadLinks();
