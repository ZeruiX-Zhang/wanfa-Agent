const API_BASE = "http://127.0.0.1:8787";

const state = {
  workspace: "prompt",
  knowledgeTab: "dashboard",
  graphTab: "visual",
  settings: null,
  prompt: {
    selectedText: "", goal: "", mode: "auto",
    testInput: "", useKnowledgeOS: false,
    finalPrompt: "", generated: null, test: null, compare: null,
    captureSource: "", captureLoaded: false,
  },
  wiki: {
    skillId: null, skillSource: "", skillOutput: "", skillSaving: false,
    skillsManaging: false, editingSkillId: null,
    personalFileId: null, personalContent: "",
    studyGoal: "", studyPlan: "", studyDays: 30, studyLoading: false,
    importPath: "",
  },
};

const app = document.querySelector("#app");

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.workspace = btn.dataset.workspace;
    document.querySelectorAll(".nav-item").forEach((b) =>
      b.classList.toggle("active", b === btn));
    render();
  });
});

/* ─── api ─────────────────────────────────────────────────── */
async function api(path, options = {}) {
  const r = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await r.text();
  const body = text ? JSON.parse(text) : null;
  if (!r.ok) throw new Error(body?.detail || `HTTP ${r.status}`);
  return body;
}

async function runAction(fn) {
  try { await fn(); }
  catch (e) { alert(e.message); }
}

/* ─── helpers ─────────────────────────────────────────────── */
function h(strings, ...vals) {
  return strings.reduce((a, s, i) => a + s + (vals[i] ?? ""), "");
}
function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}
function pill(text, cls = "") {
  return `<span class="pill ${cls}">${esc(text)}</span>`;
}

async function loadSettings() {
  try { state.settings = await api("/api/settings/model"); }
  catch { state.settings = null; }
}

async function checkCapture() {
  try {
    const c = await api("/api/capture/latest");
    if (c?.selected_text && !state.prompt.captureLoaded) {
      state.prompt.selectedText = c.selected_text;
      state.prompt.captureSource = `来自浏览器扩展 · ${c.url || ""}`;
      state.prompt.captureLoaded = true;
    }
  } catch { /* ignore */ }
}

function topbar(title, sub, right = "") {
  return h`<div class="topbar">
    <div><h1>${title}</h1>${sub ? `<p>${sub}</p>` : ""}</div>
    <div>${right}</div>
  </div>`;
}

/* ─── render router ───────────────────────────────────────── */
function render() {
  if (state.workspace === "knowledge") renderKnowledge();
  else if (state.workspace === "settings") renderSettings();
  else renderPromptLab();
}

/* ══════════════════════════════════════════════════════════════
   PROMPT LAB
══════════════════════════════════════════════════════════════ */
function renderPromptLab() {
  const provider = state.settings?.provider_label || "本地模拟模型";
  const isMock = provider.includes("模拟");
  const gen = state.prompt.generated;
  const capture = state.prompt.captureSource
    ? h`<div class="capture-banner"><span>↑</span><span>${esc(state.prompt.captureSource)}</span></div>`
    : "";

  app.innerHTML = topbar(
    "提示词实验室", "生成、测试、A/B 对比提示词",
    pill(provider, isMock ? "warn" : "ok")
  ) + capture + h`
  <section class="grid-2">
    <div class="card">
      <div class="card-header"><h2>输入</h2><p>填写原始文本和目标，选择优化模式后生成。</p></div>
      <div class="card-body">
        <div class="field"><label>原始文本</label>
          <textarea id="selectedText" placeholder="粘贴需要优化的内容…">${esc(state.prompt.selectedText)}</textarea></div>
        <div class="field"><label>目标 / 补充信息</label>
          <textarea id="goal" style="min-height:72px" placeholder="说明期望结果，可留空…">${esc(state.prompt.goal)}</textarea></div>
        <div class="field"><label>优化模式</label>
          <select id="mode">${[
            ["auto","自动选择"],["prompt_rewrite","提示词优化"],
            ["codex_task","代码任务"],["learning_prompt","学习辅导"],["decision_prompt","决策分析"],
          ].map(([v,l]) => `<option value="${v}" ${state.prompt.mode===v?"selected":""}>${l}</option>`).join("")}
          </select></div>
        <div class="field"><label>测试输入（可选）</label>
          <textarea id="testInput" style="min-height:72px" placeholder="对生成的提示词进行测试…">${esc(state.prompt.testInput)}</textarea></div>
        <div class="switch-line"><span>引用 Knowledge OS</span>
          <input id="useKnowledgeOS" type="checkbox" ${state.prompt.useKnowledgeOS?"checked":""}/>
        </div>
        <div class="section-gap"></div>
        <div class="row">
          <button class="btn primary" id="generateBtn">生成 Prompt</button>
          <button class="btn" id="testBtn">测试</button>
          <button class="btn" id="compareBtn">A/B 对比</button>
        </div>
        <p class="meta" style="margin-top:10px">当前模型：${esc(state.settings?.model || "mock-prompt-model")}</p>
      </div>
    </div>

    <div style="display:grid;gap:16px">
      <div class="card">
        <div class="card-header row-between">
          <div><h2>优化提示词</h2></div>
          <div class="row">
            ${gen ? pill(gen.skill_info?.mode_label || "auto") : ""}
            <button class="btn ghost" id="copyPromptBtn">复制</button>
            ${gen ? `<button class="btn ghost" id="savePromptBtn">存入知识库</button>` : ""}
          </div>
        </div>
        <div class="card-body">
          <div class="output" id="finalPrompt">${esc(state.prompt.finalPrompt || "点击「生成 Prompt」后显示。")}</div>
          ${gen ? h`
          <div class="row" style="margin-top:12px">
            ${pill("Knowledge OS " + (gen.knowledge_os_info?.used ? "已用" : "未用"), gen.knowledge_os_info?.used ? "warn" : "")}
            ${pill("个性化 " + (gen.personalization_info?.used ? "已用" : "未用"), gen.personalization_info?.used ? "accent" : "")}
          </div>` : ""}
        </div>
      </div>

      ${state.prompt.test ? h`
      <div class="card">
        <div class="card-header"><h2>测试结果</h2></div>
        <div class="card-body"><div class="output">${esc(state.prompt.test.output || "")}</div></div>
      </div>` : ""}

      ${state.prompt.compare ? h`
      <div class="card">
        <div class="card-header row-between">
          <h2>A/B 对比</h2>
          ${pill("胜出：" + (state.prompt.compare.comparison?.winner || "—"), "ok")}
        </div>
        <div class="card-body">
          <p style="margin-bottom:10px;font-size:13px;color:var(--sub)">${esc(state.prompt.compare.comparison?.reason||"")}</p>
          <div class="tab-bar"><button class="tab active" data-ab="opt">优化版</button><button class="tab" data-ab="ori">原始版</button></div>
          <div class="output" id="abOutput">${esc(state.prompt.compare.optimized_output || "")}</div>
          <input type="hidden" id="abOri" value="${esc(state.prompt.compare.original_output||"")}"/>
          <input type="hidden" id="abOpt" value="${esc(state.prompt.compare.optimized_output||"")}"/>
        </div>
      </div>` : ""}
    </div>
  </section>`;

  bindPromptLab();
}

function syncPromptInputs() {
  state.prompt.selectedText = document.querySelector("#selectedText")?.value || "";
  state.prompt.goal         = document.querySelector("#goal")?.value || "";
  state.prompt.mode         = document.querySelector("#mode")?.value || "auto";
  state.prompt.testInput    = document.querySelector("#testInput")?.value || "";
  state.prompt.useKnowledgeOS = document.querySelector("#useKnowledgeOS")?.checked || false;
}

function bindPromptLab() {
  document.querySelector("#generateBtn")?.addEventListener("click", async () => {
    syncPromptInputs();
    await runAction(async () => {
      const body = await api("/api/generate", { method: "POST", body: JSON.stringify({
        selected_text: state.prompt.selectedText || "请生成一个可执行提示词。",
        user_goal: state.prompt.goal, mode: state.prompt.mode,
        use_knowledge_os: state.prompt.useKnowledgeOS,
      })});
      state.prompt.generated   = body;
      state.prompt.finalPrompt = body.final_prompt;
      renderPromptLab();
    });
  });
  document.querySelector("#testBtn")?.addEventListener("click", async () => {
    syncPromptInputs();
    await runAction(async () => {
      state.prompt.test = await api("/api/prompt-lab/test", { method: "POST", body: JSON.stringify({
        prompt: state.prompt.finalPrompt || state.prompt.selectedText,
        test_input: state.prompt.testInput,
      })});
      renderPromptLab();
    });
  });
  document.querySelector("#compareBtn")?.addEventListener("click", async () => {
    syncPromptInputs();
    await runAction(async () => {
      state.prompt.compare = await api("/api/prompt-lab/compare", { method: "POST", body: JSON.stringify({
        original_prompt: state.prompt.selectedText || "请处理输入。",
        optimized_prompt: state.prompt.finalPrompt || state.prompt.selectedText || "请处理输入。",
        test_input: state.prompt.testInput,
      })});
      renderPromptLab();
    });
  });
  document.querySelector("#copyPromptBtn")?.addEventListener("click", () =>
    navigator.clipboard?.writeText(state.prompt.finalPrompt || ""));
  document.querySelector("#savePromptBtn")?.addEventListener("click", async () => {
    const title = state.prompt.goal
      ? `提示词: ${state.prompt.goal.slice(0, 50)}`
      : `优化提示词 ${new Date().toLocaleDateString("zh-CN")}`;
    await runAction(async () => {
      await api("/api/knowledge-os/notes", { method: "POST", body: JSON.stringify({
        title, content: state.prompt.finalPrompt,
        collection: "prompts", tags: ["prompt", state.prompt.mode],
      })});
      alert("已存入知识库 → 资料「笔记」文件夹");
    });
  });
  document.querySelectorAll("[data-ab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-ab]").forEach((b) => b.classList.toggle("active", b === btn));
      const key = btn.dataset.ab;
      const ori = document.querySelector("#abOri")?.value || "";
      const opt = document.querySelector("#abOpt")?.value || "";
      const out = document.querySelector("#abOutput");
      if (out) out.textContent = key === "ori" ? ori : opt;
    });
  });
}

/* ══════════════════════════════════════════════════════════════
   KNOWLEDGE OS
══════════════════════════════════════════════════════════════ */

const WIKI_TABS = [
  { id: "dashboard", label: "概览",   group: "" },
  { id: "sources",   label: "资料",   group: "知识库" },
  { id: "notes",     label: "笔记",   group: "知识库" },
  { id: "review",    label: "审核队列", group: "知识库" },
  { id: "graph",     label: "知识图谱", group: "知识库" },
  { id: "personal",  label: "个人摘要", group: "个人" },
  { id: "skills",    label: "技能工坊", group: "个人" },
  { id: "study",     label: "学习计划", group: "工具" },
  { id: "logs",      label: "日志",   group: "工具" },
];

// Skills are now stored persistently via /api/knowledge-os/skills (JSONL on disk).

function knowledgeSubnav() {
  let html = "";
  let lastGroup = null;
  for (const t of WIKI_TABS) {
    if (t.group !== lastGroup) {
      if (t.group) html += `<div class="subnav-divider"></div><div class="subnav-label">${t.group}</div>`;
      lastGroup = t.group;
    }
    html += `<button class="${state.knowledgeTab===t.id?"active":""}" data-tab="${t.id}">${t.label}</button>`;
  }
  return `<nav class="subnav">${html}</nav>`;
}

async function renderKnowledge() {
  app.innerHTML = topbar("知识系统", "积累、审核、深化你的长期知识") + h`
  <section class="knowledge-layout">
    ${knowledgeSubnav()}
    <div id="knowledgePanel" class="card">
      <div class="card-body" style="color:var(--sub)">加载中…</div>
    </div>
  </section>`;

  document.querySelectorAll("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => { state.knowledgeTab = btn.dataset.tab; renderKnowledge(); });
  });

  try {
    const tab = state.knowledgeTab;
    if      (tab === "dashboard") await renderDashboard();
    else if (tab === "sources")   await renderSources();
    else if (tab === "notes")     await renderNotes();
    else if (tab === "review")    await renderReview();
    else if (tab === "graph")     await renderGraph();
    else if (tab === "personal")  await renderPersonal();
    else if (tab === "skills")    await renderSkills();
    else if (tab === "study")     await renderStudyPlan();
    else if (tab === "logs")      await renderLogs();
  } catch (err) {
    document.querySelector("#knowledgePanel").innerHTML =
      `<div class="card-body error">${esc(err.message)}</div>`;
  }
}

/* ─── dashboard ───────────────────────────────────────────── */
async function renderDashboard() {
  const [sources, notes, nodes, queue] = await Promise.all([
    api("/api/knowledge-os/sources").catch(() => []),
    api("/api/knowledge-os/claims").catch(() => []),
    api("/api/knowledge-os/graph/nodes").catch(() => []),
    api("/api/level-up/review-queue").catch(() => []),
  ]);
  const pending = queue.filter(i => i.status === "pending").length;

  document.querySelector("#knowledgePanel").innerHTML = h`
    <div class="card-header row-between">
      <div><h2>知识库概览</h2><p>Level Up 累计沉淀的长期知识。</p></div>
      <button class="btn" id="goImportBtn">+ 导入文件</button>
    </div>
    <div class="card-body">
      <div class="stat-row">
        <div class="stat-card"><div class="num">${sources.length}</div><div class="lbl">资料条目</div></div>
        <div class="stat-card"><div class="num">${notes.length}</div><div class="lbl">知识笔记</div></div>
        <div class="stat-card"><div class="num">${nodes.length}</div><div class="lbl">图谱节点</div></div>
        <div class="stat-card">
          <div class="num" style="color:${pending>0?"var(--amber)":"var(--green)"}">${pending}</div>
          <div class="lbl">待审核</div>
        </div>
      </div>

      ${pending > 0 ? h`
      <div class="alert-banner warn" style="margin-bottom:16px">
        <div class="row-between">
          <span>${pending} 条 Level Up 等待审核</span>
          <button class="btn" id="goReviewBtn">前往审核 →</button>
        </div>
        <p class="meta" style="margin-top:6px">审核通过后，笔记和图谱节点才会正式写入知识库。</p>
      </div>` : h`
      <div class="alert-banner ok" style="margin-bottom:16px">
        <span>审核队列已清空 — 知识库保持最新</span>
      </div>`}

      ${sources.length > 0 ? h`
      <h3 style="font-size:14px;margin-bottom:10px;color:var(--sub);font-weight:600;text-transform:uppercase;letter-spacing:.05em">最近资料</h3>
      <div class="list">
        ${sources.slice(0,4).map(s => h`
          <article class="item">
            <div class="row-between">
              <h4>${esc(s.title)}</h4>
              ${pill(s.collection || "level-up")}
            </div>
            <p>${esc((s.summary||"").slice(0,120))}${s.summary?.length>120?"…":""}</p>
            <p class="meta">${esc(s.created_at||"")} · ${esc(s.source_domain||"")}</p>
          </article>`).join("")}
      </div>` : h`
      <div style="text-align:center;padding:48px 0;color:var(--sub)">
        <p style="font-size:15px;margin-bottom:8px">知识库还是空的</p>
        <p style="font-size:13px">在浏览器选中文字，右键「Level Up」开始积累</p>
      </div>`}
    </div>`;

  document.querySelector("#goImportBtn")?.addEventListener("click", () => {
    state.knowledgeTab = "sources"; renderKnowledge();
  });
  document.querySelector("#goReviewBtn")?.addEventListener("click", () => {
    state.knowledgeTab = "review"; renderKnowledge();
  });
}

/* ─── sources ─────────────────────────────────────────────── */
async function renderSources() {
  const sources = await api("/api/knowledge-os/sources");
  document.querySelector("#knowledgePanel").innerHTML = h`
    <div class="card-header row-between">
      <div><h2>资料</h2><p>Level Up 及导入的知识文档。</p></div>
      <div class="row">
        <button class="btn" id="openKosBtn">打开文件夹</button>
        <button class="btn primary" id="importToggleBtn">+ 从磁盘导入</button>
      </div>
    </div>
    <div class="card-body">
      <div id="importPanel" style="display:none;margin-bottom:16px;padding:14px;background:var(--bg);border-radius:var(--r-md)">
        <p style="font-size:13px;margin-bottom:8px;color:var(--sub)">
          输入本地文件路径（支持 .txt / .md），桌面端将读取并提取知识存入资料库。
        </p>
        <div class="row" style="gap:8px">
          <input id="importPathInput" placeholder="C:\\Users\\...\\file.md" style="flex:1"/>
          <select id="importCollectionSel">
            <option value="import">import</option>
            <option value="reading">reading</option>
            <option value="research">research</option>
          </select>
          <button class="btn primary" id="importSubmitBtn">读取并存入</button>
        </div>
        <p id="importStatus" class="meta" style="margin-top:8px"></p>
      </div>
      <div class="toolbar">
        <input id="sourceSearch" placeholder="搜索标题、摘要、标签…" />
        <button class="btn" id="sourceSearchBtn">搜索</button>
      </div>
      <div class="list" id="sourcesList">${sourceItems(sources)}</div>
    </div>`;

  document.querySelector("#importToggleBtn").addEventListener("click", () => {
    const p = document.querySelector("#importPanel");
    p.style.display = p.style.display === "none" ? "block" : "none";
  });
  document.querySelector("#importSubmitBtn").addEventListener("click", async () => {
    const path = document.querySelector("#importPathInput").value.trim();
    const collection = document.querySelector("#importCollectionSel").value;
    const status = document.querySelector("#importStatus");
    if (!path) { status.textContent = "请输入文件路径"; return; }
    status.textContent = "读取中…";
    try {
      const res = await api("/api/knowledge-os/import", { method: "POST",
        body: JSON.stringify({ path, collection, tags: [collection, "import"] }) });
      status.textContent = `已存入审核队列 — 标题：${res.source_page || ""}`;
      state.knowledgeTab = "review"; setTimeout(() => renderKnowledge(), 1500);
    } catch (e) { status.textContent = "错误：" + e.message; }
  });
  document.querySelector("#sourceSearchBtn").addEventListener("click", async () => {
    const q = document.querySelector("#sourceSearch").value;
    document.querySelector("#sourcesList").innerHTML =
      sourceItems(await api(`/api/knowledge-os/sources?query=${encodeURIComponent(q)}`));
    bindSourceBtns();
  });
  document.querySelector("#openKosBtn").addEventListener("click", () =>
    api("/api/knowledge-os/open-folder", { method: "POST" }));
  bindSourceBtns();
}

function sourceItems(sources) {
  if (!sources.length) return `<p class="muted" style="padding:24px 0;text-align:center">暂无资料</p>`;
  return sources.map(s => h`
    <article class="item">
      <div class="row-between">
        <h4>${esc(s.title)}</h4>
        <div class="row">${pill(s.collection||"level-up")}
          ${(s.tags||[]).slice(0,2).map(t => `<span class="tag">${esc(t)}</span>`).join("")}
        </div>
      </div>
      <p>${esc((s.summary||"").slice(0,140))}${(s.summary||"").length>140?"…":""}</p>
      <p class="meta">${esc(s.filename)} · ${esc(s.created_at||"")}</p>
      <div class="row" style="margin-top:10px">
        <button class="btn" data-src-open="${s.id}">打开文件</button>
        <button class="btn" data-src-skill="${s.id}" data-src-title="${esc(s.title)}">技能分析 →</button>
        <button class="btn danger" data-src-del="${s.id}">删除</button>
      </div>
    </article>`).join("");
}

function bindSourceBtns() {
  document.querySelectorAll("[data-src-open]").forEach(b =>
    b.addEventListener("click", () =>
      api(`/api/knowledge-os/sources/${b.dataset.srcOpen}/open`, { method: "POST" })));
  document.querySelectorAll("[data-src-del]").forEach(b =>
    b.addEventListener("click", async () => {
      if (!confirm("确认删除？")) return;
      await api(`/api/knowledge-os/sources/${b.dataset.srcDel}`, { method: "DELETE" });
      renderKnowledge();
    }));
  document.querySelectorAll("[data-src-skill]").forEach(b =>
    b.addEventListener("click", () => {
      state.wiki.skillSource = b.dataset.srcSkill;
      state.knowledgeTab = "skills";
      renderKnowledge();
    }));
}

/* ─── notes (was claims) ──────────────────────────────────── */
const NOTE_STATUS_CLS = {
  supported: "ok", contradicted: "danger", outdated: "warn",
  disputed: "warn", needs_review: "",
};
const NOTE_STATUS_ZH = {
  supported: "已验证", contradicted: "已反驳", outdated: "已过时",
  disputed: "有争议", needs_review: "待审核",
};

async function renderNotes() {
  const notes = await api("/api/knowledge-os/claims");
  document.querySelector("#knowledgePanel").innerHTML = h`
    <div class="card-header row-between">
      <div><h2>笔记</h2><p>从 Level Up 和资料中提取的知识笔记。</p></div>
      <button class="btn primary" id="newNoteBtn">+ 新建笔记</button>
    </div>
    <div class="card-body">
      <div class="toolbar">
        <input id="noteSearch" placeholder="搜索笔记内容…" />
        <select id="noteStatus">
          <option value="">全部状态</option>
          ${Object.entries(NOTE_STATUS_ZH).map(([v,l]) => `<option value="${v}">${l}</option>`).join("")}
        </select>
        <button class="btn" id="noteFilterBtn">过滤</button>
      </div>
      <div class="list" id="notesList">${noteItems(notes)}</div>
    </div>`;

  document.querySelector("#newNoteBtn").addEventListener("click", async () => {
    const text = prompt("新笔记内容");
    if (!text?.trim()) return;
    const title = text.slice(0, 60);
    await runAction(async () => {
      await api("/api/knowledge-os/notes", { method: "POST", body: JSON.stringify({
        title, content: text, collection: "notes", tags: ["note"],
      })});
      renderKnowledge();
    });
  });
  document.querySelector("#noteFilterBtn").addEventListener("click", async () => {
    const q = document.querySelector("#noteSearch").value;
    const s = document.querySelector("#noteStatus").value;
    document.querySelector("#notesList").innerHTML =
      noteItems(await api(`/api/knowledge-os/claims?query=${encodeURIComponent(q)}&status=${encodeURIComponent(s)}`));
    bindNoteBtns();
  });
  bindNoteBtns();
}

function noteItems(notes) {
  if (!notes.length) return `<p class="muted" style="padding:24px 0;text-align:center">暂无笔记</p>`;
  return notes.map(n => h`
    <article class="item">
      <div class="row-between">
        <p style="flex:1;margin-right:12px;line-height:1.5">${esc(n.text)}</p>
        ${pill(NOTE_STATUS_ZH[n.status] || n.status, NOTE_STATUS_CLS[n.status] || "")}
      </div>
      <p class="meta">置信度 ${Math.round((n.confidence||0)*100)}% · ${esc(n.source_page||"")}</p>
      <div class="row" style="margin-top:8px">
        <button class="btn" data-note-edit="${n.id}">编辑</button>
        <button class="btn danger" data-note-del="${n.id}">删除</button>
      </div>
    </article>`).join("");
}

function bindNoteBtns() {
  document.querySelectorAll("[data-note-del]").forEach(b =>
    b.addEventListener("click", async () => {
      if (!confirm("确认删除？")) return;
      await api(`/api/knowledge-os/claims/${b.dataset.noteDel}`, { method: "DELETE" });
      renderKnowledge();
    }));
  document.querySelectorAll("[data-note-edit]").forEach(b =>
    b.addEventListener("click", async () => {
      const text = prompt("编辑笔记");
      if (text) {
        await api(`/api/knowledge-os/claims/${b.dataset.noteEdit}`, {
          method: "PUT", body: JSON.stringify({ text }) });
        renderKnowledge();
      }
    }));
}

/* ─── review queue ────────────────────────────────────────── */
async function renderReview() {
  const queue = await api("/api/level-up/review-queue");
  const pending = queue.filter(i => i.status === "pending");
  document.querySelector("#knowledgePanel").innerHTML = h`
    <div class="card-header row-between">
      <div><h2>审核队列</h2><p>Approve 后正式写入知识图谱。</p></div>
      ${pending.length ? pill(`${pending.length} 待审核`, "warn") : pill("队列已清空", "ok")}
    </div>
    <div class="card-body">
      ${!queue.length ? `<p class="muted" style="text-align:center;padding:30px 0">暂无待审核条目</p>` :
        `<div class="list">${queue.map(item => h`
          <article class="item">
            <div class="row-between">
              <h4>${esc(item.source_title)}</h4>
              ${pill(item.status==="approved"?"已通过":item.status==="rejected"?"已拒绝":"待审核",
                     item.status==="approved"?"ok":item.status==="rejected"?"danger":"warn")}
            </div>
            <p>${esc((item.summary||"").slice(0,160))}</p>
            <p class="meta">笔记 ${item.claims_count} · 节点 ${item.nodes_count} · 边 ${item.edges_count} · ${esc(item.created_at||"")}</p>
            <div class="row" style="margin-top:10px">
              <button class="btn" data-rv-detail="${item.id}">查看详情</button>
              ${item.status==="pending" ? `
                <button class="btn primary" data-rv-approve="${item.id}">通过 ✓</button>
                <button class="btn danger"  data-rv-reject="${item.id}">拒绝</button>` : ""}
            </div>
          </article>`).join("")}
        </div>`}
      <div id="reviewDetail" style="margin-top:16px"></div>
    </div>`;

  document.querySelectorAll("[data-rv-detail]").forEach(b =>
    b.addEventListener("click", async () => {
      const d = await api(`/api/level-up/review/${b.dataset.rvDetail}`);
      document.querySelector("#reviewDetail").innerHTML =
        `<div class="output" style="font-size:12px;font-family:monospace">${esc(JSON.stringify(d, null, 2))}</div>`;
    }));
  document.querySelectorAll("[data-rv-approve]").forEach(b =>
    b.addEventListener("click", async () => {
      await api(`/api/level-up/review/${b.dataset.rvApprove}/approve`, { method: "POST" });
      renderKnowledge();
    }));
  document.querySelectorAll("[data-rv-reject]").forEach(b =>
    b.addEventListener("click", async () => {
      await api(`/api/level-up/review/${b.dataset.rvReject}/reject`, { method: "POST" });
      renderKnowledge();
    }));
}

/* ─── graph ───────────────────────────────────────────────── */
async function renderGraph() {
  const [nodes, edges] = await Promise.all([
    api("/api/knowledge-os/graph/nodes"),
    api("/api/knowledge-os/graph/edges"),
  ]);

  document.querySelector("#knowledgePanel").innerHTML = h`
    <div class="card-header row-between">
      <div><h2>知识图谱</h2><p>概念、来源及其关系的可视化。</p></div>
      <div class="row">
        <div class="tab-bar" style="margin:0">
          <button class="tab ${state.graphTab==="visual"?"active":""}" data-gt="visual">图形</button>
          <button class="tab ${state.graphTab==="nodes"?"active":""}" data-gt="nodes">节点列表</button>
          <button class="tab ${state.graphTab==="edges"?"active":""}" data-gt="edges">边列表</button>
        </div>
        <button class="btn" id="openGraphBtn">打开文件夹</button>
      </div>
    </div>
    <div class="card-body" id="graphBody">
      ${state.graphTab==="visual" ? graphSVG(nodes, edges)
        : state.graphTab==="nodes" ? nodeTable(nodes) : edgeTable(edges)}
    </div>`;

  document.querySelectorAll("[data-gt]").forEach(b =>
    b.addEventListener("click", () => { state.graphTab = b.dataset.gt; renderKnowledge(); }));
  document.querySelector("#openGraphBtn").addEventListener("click", () =>
    api("/api/knowledge-os/graph/open-folder", { method: "POST" }));
}

function graphSVG(nodes, edges) {
  if (!nodes.length) {
    return `<div style="text-align:center;padding:60px 0;color:var(--sub)">
      <p style="font-size:15px;margin-bottom:6px">图谱尚无节点</p>
      <p style="font-size:13px">通过 Level Up 积累知识后自动生成</p>
    </div>`;
  }
  const W = 740, H = 440, cx = W / 2, cy = H / 2;
  const n = nodes.length;
  const r = Math.min(170, Math.max(80, n * 22));
  const nodeColors = { Concept: "#0071e3", Source: "#28a745", Person: "#ff9500", Event: "#ff3b30" };
  const pos = nodes.map((nd, i) => {
    const angle = (2 * Math.PI * i / n) - Math.PI / 2;
    return { ...nd, px: cx + r * Math.cos(angle), py: cy + r * Math.sin(angle) };
  });
  const byName = Object.fromEntries(pos.map(p => [p.name, p]));

  const edgeSVG = edges.map(e => {
    const f = byName[e.from], t = byName[e.to];
    if (!f || !t) return "";
    const mx = (f.px + t.px) / 2, my = (f.py + t.py) / 2;
    return `<line x1="${f.px}" y1="${f.py}" x2="${t.px}" y2="${t.py}" stroke="#d1d1d6" stroke-width="1.5" stroke-dasharray="4 3"/>
            <text x="${mx}" y="${my}" fill="#aeaeb2" font-size="9" text-anchor="middle" dy="-3">${esc(e.type||"")}</text>`;
  }).join("");

  const nodeSVG = pos.map(p => {
    const color = nodeColors[p.type] || "#6e6e73";
    const label = (p.name || "").slice(0, 12);
    return `<g>
      <circle cx="${p.px}" cy="${p.py}" r="24" fill="${color}20" stroke="${color}" stroke-width="2"/>
      <text x="${p.px}" y="${p.py + 4}" text-anchor="middle" font-size="10" fill="${color}" font-weight="600">${esc(label)}</text>
      <text x="${p.px}" y="${p.py + 38}" text-anchor="middle" font-size="9" fill="#aeaeb2">${esc(p.type||"")}</text>
    </g>`;
  }).join("");

  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;min-height:${H}px;background:var(--bg);border-radius:var(--r-md)">
    <defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L6,3 z" fill="#d1d1d6"/>
    </marker></defs>
    ${edgeSVG}${nodeSVG}
  </svg>`;
}

function nodeTable(rows) {
  if (!rows.length) return `<p class="muted" style="padding:24px 0;text-align:center">暂无节点</p>`;
  return `<table class="table"><thead><tr><th>名称</th><th>类型</th><th>别名</th><th>来源</th></tr></thead>
    <tbody>${rows.map(r => `<tr>
      <td><strong>${esc(r.name)}</strong></td>
      <td>${pill(r.type||"")}</td>
      <td><span class="muted small">${esc((r.aliases||[]).join(", "))}</span></td>
      <td><span class="small muted">${esc(r.source)}</span></td>
    </tr>`).join("")}</tbody></table>`;
}

function edgeTable(rows) {
  if (!rows.length) return `<p class="muted" style="padding:24px 0;text-align:center">暂无边</p>`;
  return `<table class="table"><thead><tr><th>起点</th><th>关系</th><th>终点</th><th>置信度</th></tr></thead>
    <tbody>${rows.map(r => `<tr>
      <td>${esc(r.from)}</td><td>${pill(r.type||"")}</td><td>${esc(r.to)}</td>
      <td>${pill(Math.round((r.confidence||0)*100)+"%", r.confidence>=0.7?"ok":r.confidence>=0.4?"warn":"danger")}</td>
    </tr>`).join("")}</tbody></table>`;
}

/* ─── personal ────────────────────────────────────────────── */
async function renderPersonal() {
  const files = await api("/api/knowledge-os/personal/files");
  if (!state.wiki.personalFileId && files.length) {
    state.wiki.personalFileId = files[0].id;
  }
  const activeFile = files.find(f => f.id === state.wiki.personalFileId) || files[0];
  let activeContent = "";
  if (activeFile) {
    const fc = await api(`/api/knowledge-os/personal/files/${activeFile.id}`);
    activeContent = fc.content || "";
    if (state.wiki.personalFileId === activeFile.id) {
      state.wiki.personalContent = activeContent;
    }
  }

  document.querySelector("#knowledgePanel").innerHTML = h`
    <div class="card-header row-between">
      <div><h2>个人摘要</h2><p>学习风格、目标、偏好 — 驱动 Prompt 个性化的数据来源。</p></div>
      <div class="row">
        <button class="btn primary" id="savePersonalBtn">💾 保存</button>
        <button class="btn" id="openPersonalBtn">打开文件夹</button>
      </div>
    </div>
    <div class="card-body" style="padding:0">
      <div style="display:grid;grid-template-columns:200px 1fr;min-height:420px">

        <!-- dimension list -->
        <div style="border-right:1px solid var(--line);overflow-y:auto">
          ${files.map(f => `
            <button class="dim-row ${f.id===state.wiki.personalFileId?"active":""}" data-file-id="${esc(f.id)}">
              <span class="dim-icon">📄</span>
              <div>
                <div class="dim-name">${esc(f.filename.replace(/\.md$/i,""))}</div>
                <div class="dim-sub">${esc((f.title||"").slice(0,30))}</div>
              </div>
            </button>`).join("")}
        </div>

        <!-- editor -->
        <div style="display:flex;flex-direction:column;padding:16px;gap:12px">
          ${activeFile ? `
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
            <span style="font-size:13px;color:var(--sub)">编辑中：</span>
            <strong style="font-size:13px">${esc(activeFile.filename)}</strong>
          </div>
          <textarea id="personalContent" style="flex:1;min-height:320px;font-family:monospace;font-size:13px;resize:vertical">${esc(activeContent)}</textarea>` :
          `<p class="muted" style="padding:40px;text-align:center">暂无个人摘要文件</p>`}
        </div>
      </div>
    </div>`;

  document.querySelectorAll("[data-file-id]").forEach(b => {
    b.addEventListener("click", () => {
      state.wiki.personalFileId = b.dataset.fileId;
      renderKnowledge();
    });
  });
  document.querySelector("#savePersonalBtn")?.addEventListener("click", async () => {
    if (!activeFile) return;
    const content = document.querySelector("#personalContent")?.value || "";
    await runAction(async () => {
      await api(`/api/knowledge-os/personal/files/${activeFile.id}`, {
        method: "PUT", body: JSON.stringify({ content }) });
      const btn = document.querySelector("#savePersonalBtn");
      if (btn) { btn.textContent = "已保存 ✓"; btn.style.background = "var(--green)";
        setTimeout(() => { btn.textContent = "💾 保存"; btn.style.background = ""; }, 2000); }
    });
  });
  document.querySelector("#openPersonalBtn")?.addEventListener("click", () =>
    api("/api/knowledge-os/personal/open-folder", { method: "POST" }));
}

/* ─── skills ──────────────────────────────────────────────── */
async function renderSkills() {
  const [sources, skills] = await Promise.all([
    api("/api/knowledge-os/sources").catch(() => []),
    api("/api/knowledge-os/skills").catch(() => []),
  ]);
  const managing = state.wiki.skillsManaging;
  const editId   = state.wiki.editingSkillId;

  const skillRowHtml = (sk) => {
    if (managing) {
      const isEditing = editId === sk.id;
      return `<div class="skill-row" data-skill-row="${esc(sk.id)}">
        <div class="skill-row-header">
          <div>
            <div class="skill-row-title">${esc(sk.title)}</div>
            <div class="skill-row-desc">${esc(sk.desc)}</div>
          </div>
          <div class="row" style="gap:6px">
            <button class="btn ghost" data-skill-edit="${esc(sk.id)}">${isEditing ? "收起" : "编辑"}</button>
            <button class="btn danger" data-skill-del="${esc(sk.id)}">删除</button>
          </div>
        </div>
        ${isEditing ? `<div class="skill-edit-form" style="margin-top:12px">
          <div class="field"><label>标题</label>
            <input id="seTitle" value="${esc(sk.title)}"></div>
          <div class="field"><label>简介</label>
            <input id="seDesc" value="${esc(sk.desc)}"></div>
          <div class="field"><label>系统提示词</label>
            <textarea id="seSystem" rows="2">${esc(sk.system)}</textarea></div>
          <div class="field"><label>用户提示词模板（用 {{title}} 和 {{content}} 插入资料）</label>
            <textarea id="seTemplate" rows="5">${esc(sk.user_template || "")}</textarea></div>
          <div class="row" style="margin-top:8px">
            <button class="btn primary" data-skill-save-edit="${esc(sk.id)}">保存修改</button>
            <button class="btn ghost" data-skill-cancel-edit>取消</button>
          </div>
        </div>` : ""}
      </div>`;
    }
    return `<div class="skill-row" data-skill-row="${esc(sk.id)}">
      <div class="skill-row-header">
        <div>
          <div class="skill-row-title">${esc(sk.title)}</div>
          <div class="skill-row-desc">${esc(sk.desc)}</div>
        </div>
        <button class="btn" data-skill-run="${esc(sk.id)}">运行</button>
      </div>
    </div>`;
  };

  const newSkillForm = editId === "__new__" ? `
    <div class="skill-edit-form" style="margin-top:16px;padding:12px;border:1px solid var(--border);border-radius:8px">
      <div style="font-weight:600;margin-bottom:10px;font-size:14px">新建技能</div>
      <div class="field"><label>标题</label><input id="seTitle" placeholder="技能名称"></div>
      <div class="field"><label>简介</label><input id="seDesc" placeholder="一句话描述这个技能的作用"></div>
      <div class="field"><label>系统提示词</label>
        <textarea id="seSystem" rows="2" placeholder="你是…专家，擅长…"></textarea></div>
      <div class="field"><label>用户提示词模板（用 {{title}} 和 {{content}} 插入资料）</label>
        <textarea id="seTemplate" rows="5" placeholder="对以下材料做…分析。来源：{{title}}\n\n{{content}}\n\n输出：…"></textarea></div>
      <div class="row" style="margin-top:8px">
        <button class="btn primary" id="seCreateBtn">创建技能</button>
        <button class="btn ghost" data-skill-cancel-edit>取消</button>
      </div>
    </div>` : "";

  document.querySelector("#knowledgePanel").innerHTML = h`
    <div class="card-header row-between">
      <div>
        <h2>技能工坊</h2>
        <p>${managing ? "管理技能：编辑提示词、删除或新建技能" : "选择资料，用 AI 技能深化学习"}</p>
      </div>
      <button class="btn ${managing ? "primary" : "ghost"}" id="skillManageToggle">
        ${managing ? "完成管理" : "管理技能"}
      </button>
    </div>
    <div class="card-body">
      ${!managing ? `<div class="field" style="margin-bottom:20px">
        <label>选择资料</label>
        <select id="skillSourceSel">
          <option value="">— 选择一条资料 —</option>
          ${sources.map(s =>
            `<option value="${esc(s.id)}" ${state.wiki.skillSource===s.id?"selected":""}>${esc(s.title.slice(0,60))}</option>`
          ).join("")}
        </select>
      </div>` : ""}

      <div id="skillList" style="display:grid;gap:8px">
        ${skills.length ? skills.map(skillRowHtml).join("") :
          `<div style="color:var(--sub);text-align:center;padding:40px 0">暂无技能，点击「管理技能」→「新建技能」添加</div>`}
      </div>

      ${managing ? `<div style="margin-top:12px">
        <button class="btn" id="addSkillBtn" ${editId === "__new__" ? "disabled" : ""}>+ 新建技能</button>
        ${newSkillForm}
      </div>` : ""}
    </div>`;

  /* ── run mode events ── */
  document.querySelector("#skillSourceSel")?.addEventListener("change", (e) => {
    state.wiki.skillSource = e.target.value;
  });

  document.querySelectorAll("[data-skill-run]").forEach(b => {
    b.addEventListener("click", async () => {
      const skillId = b.dataset.skillRun;
      const skill   = skills.find(s => s.id === skillId);
      if (!skill) return;
      if (!state.wiki.skillSource) { alert("请先选择一条资料"); return; }

      state.wiki.skillId = skillId;
      b.disabled = true;
      b.textContent = "分析中…";

      const rowEl = document.querySelector(`[data-skill-row="${skillId}"]`);
      rowEl?.querySelector(".skill-row-output")?.remove();
      rowEl?.insertAdjacentHTML("beforeend", `
        <div class="skill-row-output">
          <div class="row" style="gap:8px;color:var(--sub)">
            <div class="spinner-sm"></div> AI 分析中，请稍候…
          </div>
        </div>`);

      await runSkill(skill, sources);

      b.disabled = false;
      b.textContent = "重新运行";
    });
  });

  /* ── manage mode events ── */
  document.querySelector("#skillManageToggle")?.addEventListener("click", () => {
    state.wiki.skillsManaging = !state.wiki.skillsManaging;
    state.wiki.editingSkillId = null;
    renderKnowledge();
  });

  document.querySelectorAll("[data-skill-edit]").forEach(b => {
    b.addEventListener("click", () => {
      const id = b.dataset.skillEdit;
      state.wiki.editingSkillId = state.wiki.editingSkillId === id ? null : id;
      renderKnowledge();
    });
  });

  document.querySelectorAll("[data-skill-save-edit]").forEach(b => {
    b.addEventListener("click", async () => {
      const id = b.dataset.skillSaveEdit;
      const form = b.closest(".skill-edit-form");
      const updates = {
        title:         form.querySelector("#seTitle")?.value.trim(),
        desc:          form.querySelector("#seDesc")?.value.trim(),
        system:        form.querySelector("#seSystem")?.value.trim(),
        user_template: form.querySelector("#seTemplate")?.value.trim(),
      };
      await runAction(async () => {
        await api(`/api/knowledge-os/skills/${id}`, { method: "PUT", body: JSON.stringify(updates) });
        state.wiki.editingSkillId = null;
        renderKnowledge();
      });
    });
  });

  document.querySelectorAll("[data-skill-del]").forEach(b => {
    b.addEventListener("click", async () => {
      const id    = b.dataset.skillDel;
      const skill = skills.find(s => s.id === id);
      if (!confirm(`确定删除技能「${skill?.title || id}」？此操作不可恢复。`)) return;
      await runAction(async () => {
        await api(`/api/knowledge-os/skills/${id}`, { method: "DELETE" });
        renderKnowledge();
      });
    });
  });

  document.querySelectorAll("[data-skill-cancel-edit]").forEach(b => {
    b.addEventListener("click", () => {
      state.wiki.editingSkillId = null;
      renderKnowledge();
    });
  });

  document.querySelector("#addSkillBtn")?.addEventListener("click", () => {
    state.wiki.editingSkillId = "__new__";
    renderKnowledge();
  });

  document.querySelector("#seCreateBtn")?.addEventListener("click", async () => {
    const form = document.querySelector(".skill-edit-form");
    const title = form?.querySelector("#seTitle")?.value.trim();
    if (!title) { alert("请填写技能标题"); return; }
    await runAction(async () => {
      await api("/api/knowledge-os/skills", { method: "POST", body: JSON.stringify({
        title,
        desc:          form.querySelector("#seDesc")?.value.trim() || "",
        system:        form.querySelector("#seSystem")?.value.trim() || "",
        user_template: form.querySelector("#seTemplate")?.value.trim() || "",
      })});
      state.wiki.editingSkillId = null;
      renderKnowledge();
    });
  });
}

async function runSkill(skill, sources) {
  const rowEl = document.querySelector(`[data-skill-row="${skill.id}"]`);
  try {
    const source  = await api(`/api/knowledge-os/sources/${state.wiki.skillSource}`);
    const title   = source.title   || state.wiki.skillSource;
    const content = source.content || source.summary || source.title || "";
    const userMsg = (skill.user_template || "{{title}}\n\n{{content}}")
      .replace(/\{\{title\}\}/g,   title)
      .replace(/\{\{content\}\}/g, content.slice(0, 3000));
    const res = await api("/api/llm/run", { method: "POST", body: JSON.stringify({
      system:     skill.system || "You are a helpful assistant.",
      user:       userMsg,
      max_tokens: 2000,
    })});
    state.wiki.skillOutput = res.output || "(空响应)";
  } catch (err) {
    state.wiki.skillOutput = "错误：" + (err.detail || err.message || String(err));
  }

  if (!rowEl) return;
  rowEl.querySelector(".skill-row-output")?.remove();
  const outputHtml = `
    <div class="skill-row-output">
      <div class="output" style="max-height:280px;overflow-y:auto;margin-bottom:10px;font-size:13px;white-space:pre-wrap">
        ${esc(state.wiki.skillOutput)}
      </div>
      <div class="row">
        <button class="btn primary" data-skill-save-result="${esc(skill.id)}">存入知识库</button>
        <button class="btn ghost"   data-skill-copy-result="${esc(skill.id)}">复制</button>
      </div>
    </div>`;
  rowEl.insertAdjacentHTML("beforeend", outputHtml);

  rowEl.querySelector(`[data-skill-save-result]`)?.addEventListener("click", async () => {
    if (!state.wiki.skillOutput) return;
    const srcTitle = (sources || []).find(s => s.id === state.wiki.skillSource)?.title?.slice(0,40) || state.wiki.skillSource;
    const noteTitle = `${skill.title} — ${srcTitle}`;
    await runAction(async () => {
      await api("/api/knowledge-os/notes", { method: "POST", body: JSON.stringify({
        title: noteTitle, content: state.wiki.skillOutput,
        collection: "skills", tags: ["skill", skill.id],
      })});
      alert("已存入知识库 → 「skills」文件夹");
    });
  });

  rowEl.querySelector(`[data-skill-copy-result]`)?.addEventListener("click", () =>
    navigator.clipboard?.writeText(state.wiki.skillOutput || ""));
}

/* ─── study plan ──────────────────────────────────────────── */
async function renderStudyPlan() {
  document.querySelector("#knowledgePanel").innerHTML = h`
    <div class="card-header row-between">
      <div><h2>学习计划</h2><p>根据你的知识库和目标，由 AI 生成个性化学习路径。</p></div>
      ${state.wiki.studyPlan ? `<button class="btn primary" id="saveStudyBtn">存入个人摘要</button>` : ""}
    </div>
    <div class="card-body">
      <div style="display:grid;grid-template-columns:1fr auto auto;gap:8px;margin-bottom:16px;align-items:end">
        <div class="field" style="margin:0">
          <label>学习目标</label>
          <input id="studyGoalInput" placeholder="例如：掌握 Transformer 架构，深入理解注意力机制"
            value="${esc(state.wiki.studyGoal)}"/>
        </div>
        <div class="field" style="margin:0">
          <label>周期</label>
          <select id="studyDaysSel">
            ${[14,30,60,90].map(d =>
              `<option value="${d}" ${state.wiki.studyDays===d?"selected":""}>${d} 天</option>`
            ).join("")}
          </select>
        </div>
        <button class="btn primary" id="genStudyBtn" ${state.wiki.studyLoading?"disabled":""}>
          ${state.wiki.studyLoading ? "生成中…" : "生成计划"}
        </button>
      </div>

      <div id="studyOutput" style="min-height:320px">
        ${state.wiki.studyPlan
          ? `<div class="output" style="white-space:pre-wrap;line-height:1.7;font-size:13px">${esc(state.wiki.studyPlan)}</div>`
          : `<div style="text-align:center;padding:60px 0;color:var(--sub)">
               <p style="font-size:15px;margin-bottom:8px">填写目标，生成专属学习计划</p>
               <p style="font-size:13px">AI 会结合你的知识库、个人档案和专业技能提示词来制定计划</p>
             </div>`}
      </div>
    </div>`;

  document.querySelector("#studyGoalInput").addEventListener("input", (e) => {
    state.wiki.studyGoal = e.target.value;
  });
  document.querySelector("#studyDaysSel").addEventListener("change", (e) => {
    state.wiki.studyDays = parseInt(e.target.value, 10);
  });
  document.querySelector("#genStudyBtn").addEventListener("click", async () => {
    const goal = document.querySelector("#studyGoalInput").value.trim();
    if (!goal) { alert("请填写学习目标"); return; }
    state.wiki.studyGoal = goal;
    state.wiki.studyDays = parseInt(document.querySelector("#studyDaysSel").value, 10);
    state.wiki.studyLoading = true;
    state.wiki.studyPlan = "";
    renderKnowledge();
    try {
      const res = await api("/api/learning-plan/generate", { method: "POST",
        body: JSON.stringify({ goal, days: state.wiki.studyDays }) });
      state.wiki.studyPlan = res.plan || "(空响应)";
    } catch (e) {
      state.wiki.studyPlan = "错误：" + e.message;
    } finally {
      state.wiki.studyLoading = false;
      renderKnowledge();
    }
  });

  document.querySelector("#saveStudyBtn")?.addEventListener("click", async () => {
    if (!state.wiki.studyPlan) return;
    const title = `学习计划：${state.wiki.studyGoal.slice(0, 50)}`;
    await runAction(async () => {
      await api("/api/knowledge-os/notes", { method: "POST", body: JSON.stringify({
        title, content: state.wiki.studyPlan,
        collection: "plans", tags: ["learning-plan"],
      })});
      alert("计划已存入知识库 → 资料「plans」文件夹");
    });
  });
}

/* ─── logs ────────────────────────────────────────────────── */
const LOG_ACTIONS = {
  level_up:             (d) => `📥 新增知识  ${d.source_page ? "「" + d.source_page.split("/").pop().replace(".md","") + "」" : ""}${d.llm_enhanced ? "  · AI 提取" : "  · 规则提取"}`,
  approve_review_item:  (d) => `✅ 审核通过  写入节点 ${d.nodes||0} 个、边 ${d.edges||0} 条`,
  reject_review_item:   ()  => `❌ 审核拒绝  条目未通过`,
  create_note:          (d) => `📝 新建笔记  「${d.title||""}」→ ${d.collection||""}`,
  create_source:        (d) => `📄 新建资料  「${d.title||""}」→ ${d.collection||""}`,
  update_source:        (d) => `✏️ 更新资料  ${d.filename||""}`,
  delete_source:        (d) => `🗑 删除资料  ${d.filename||d.id||""}`,
  update_claim:         ()  => `✏️ 修改笔记`,
  delete_claim:         ()  => `🗑 删除笔记`,
  update_review_item:   ()  => `✏️ 编辑审核条目`,
};

function parseLogEntries(entries) {
  return entries.map(line => {
    const m = line.match(/^-\s+([\d\-T:.+]+)\s+`([^`]+)`\s+(.*)$/);
    if (!m) return { time: "", label: line, raw: line };
    const [, time, action, jsonStr] = m;
    let details = {};
    try { details = JSON.parse(jsonStr); } catch { /* ignore */ }
    const fn = LOG_ACTIONS[action];
    const label = fn ? fn(details) : `${action}`;
    const dateStr = time.slice(0, 16).replace("T", " ");
    return { time: dateStr, label, raw: line };
  }).reverse();
}

async function renderLogs() {
  const logs = await api("/api/knowledge-os/logs");
  const entries = parseLogEntries(logs.entries || []);

  document.querySelector("#knowledgePanel").innerHTML = h`
    <div class="card-header row-between">
      <div><h2>学习日志</h2><p>记录你学了什么、总结了什么、审核了什么。</p></div>
      <button class="btn" id="openLogBtn">打开日志文件</button>
    </div>
    <div class="card-body">
      ${entries.length ? `
      <div class="list" style="gap:0">
        ${entries.slice(0, 100).map(e => `
          <div class="log-entry">
            <span class="log-time">${esc(e.time)}</span>
            <span class="log-label">${esc(e.label)}</span>
          </div>`).join("")}
      </div>` : `<p class="muted" style="text-align:center;padding:40px 0">暂无日志记录</p>`}
    </div>`;

  document.querySelector("#openLogBtn").addEventListener("click", () =>
    api("/api/knowledge-os/logs/open", { method: "POST" }));
}

/* ══════════════════════════════════════════════════════════════
   SETTINGS
══════════════════════════════════════════════════════════════ */
async function renderSettings() {
  await loadSettings();
  const s = state.settings || {};
  app.innerHTML = topbar("设置", "模型、个性化、Level Up 策略、浏览器扩展") + h`
  <section class="settings-grid">

    <div class="card">
      <div class="card-header"><h2>模型配置</h2><p>选择 Provider 和模型。</p></div>
      <div class="card-body">
        <div class="field"><label>Provider</label>
          <select id="provider">
            ${[
              ["mock",             "Mock — 本地模拟（无需 API Key）"],
              ["deepseek",         "DeepSeek"],
              ["openai_compatible","OpenAI-compatible"],
              ["ollama",           "Ollama — 本地模型"],
              ["anthropic",        "Claude (Anthropic)"],
            ].map(([v,l]) => `<option value="${v}" ${s.provider===v?"selected":""}>${l}</option>`).join("")}
          </select></div>
        <div class="field"><label>Base URL</label>
          <input id="baseUrl" value="${esc(s.base_url||"")}" placeholder="https://api.example.com/v1"/></div>
        <div class="field"><label>Model</label>
          <input id="modelName" value="${esc(s.model||"mock-prompt-model")}"/></div>
        <div class="field"><label>API Key</label>
          <input id="apiKey" type="password" placeholder="${s.has_api_key?"已配置（输入新值以覆盖）":"留空则不更改"}"/></div>
        <div class="field"><label>API Key 环境变量</label>
          <input id="apiKeyEnv" value="${esc(s.api_key_env||"OPENAI_API_KEY")}"/></div>
        <div style="margin:12px 0">
          <div class="switch-line"><span>仅本地（不发送到云端）</span>
            <input id="localOnly" type="checkbox" ${s.local_only!==false?"checked":""}/>
          </div>
          <div class="switch-line"><span>允许云端模型</span>
            <input id="allowCloud" type="checkbox" ${s.allow_cloud_model?"checked":""}/>
          </div>
        </div>
        <button class="btn primary" id="saveModelBtn">保存配置</button>
        <p class="meta" style="margin-top:8px">API Key 只存本地，不通过 API 返回。</p>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><h2>个性化</h2><p>控制 Prompt 是否引用个人知识。</p></div>
      <div class="card-body">
        <div class="switch-line"><span>启用个性化</span>
          <input id="personalEnabled" type="checkbox" ${s.personal_wiki_enabled!==false?"checked":""}/>
        </div>
        <div class="switch-line"><span>允许云端使用个人摘要</span>
          <input id="allowCloudSummary" type="checkbox" ${s.allow_cloud_personal_summary?"checked":""}/>
        </div>
        <div class="switch-line"><span>允许云端使用敏感信息</span>
          <input id="allowCloudSensitive" type="checkbox" ${s.allow_cloud_sensitive_personal?"checked":""}/>
        </div>
        <div style="margin-top:16px">
          <button class="btn" id="savePersonalSettingsBtn">保存个性化设置</button>
        </div>
        <p class="meta" style="margin-top:10px">
          个人摘要文件存放于 knowledge_os/wiki/personal/，在「个人摘要」中直接编辑。
        </p>
      </div>
    </div>

    ${[
      ["知识系统说明",
       "资料：Level Up 或从磁盘导入的文档，进入审核队列后可 Approve 写入图谱。\n笔记：从资料中提取的知识片段，也可在「笔记」页面手动新建。\n技能工坊：对资料运行 AI 深度分析（精读/闪卡/提问/蒸馏），结果可存入知识库。\n学习计划：根据个人摘要和知识库由 AI 生成专属学习路径。"],
      ["浏览器扩展",
       "在 chrome://extensions 开启开发者模式，加载 browser-extension/ 文件夹。\n右键菜单：\n• Prompt → 优化选中文字，自动回填（可撤销）\n• Level Up → 将选中内容存入知识库审核队列"],
      ["关于",
       "PromptAgent v0.7 · 本地优先的桌面端 AI 知识操作层\nProvider：Mock / DeepSeek / OpenAI-compatible / Ollama / Claude\n知识系统：资料 + 笔记 + 图谱 + 个人摘要 + 技能工坊 + 学习计划"],
    ].map(([title, text]) => `
      <div class="card">
        <div class="card-header"><h2>${title}</h2></div>
        <div class="card-body">
          <p class="muted" style="font-size:13px;white-space:pre-line;line-height:1.6">${esc(text)}</p>
        </div>
      </div>`).join("")}

  </section>`;

  document.querySelector("#saveModelBtn").addEventListener("click", saveSettings);
  document.querySelector("#savePersonalSettingsBtn").addEventListener("click", saveSettings);
}

async function saveSettings() {
  await runAction(async () => {
    const pv = document.querySelector("#provider").value;
    const vendorMap = { anthropic:"anthropic", deepseek:"deepseek",
                        ollama:"ollama", openai_compatible:"custom", mock:"mock" };
    state.settings = await api("/api/settings/model", { method: "POST",
      body: JSON.stringify({
        vendor: vendorMap[pv] || pv, provider: pv,
        base_url: document.querySelector("#baseUrl").value,
        model: document.querySelector("#modelName").value,
        api_key: document.querySelector("#apiKey").value || null,
        api_key_env: document.querySelector("#apiKeyEnv").value,
        local_only: document.querySelector("#localOnly").checked,
        allow_cloud_model: document.querySelector("#allowCloud").checked,
        redact_sensitive_info: true,
        personal_wiki_enabled: document.querySelector("#personalEnabled")?.checked ?? true,
        allow_cloud_personal_summary: document.querySelector("#allowCloudSummary")?.checked ?? false,
        allow_cloud_sensitive_personal: document.querySelector("#allowCloudSensitive")?.checked ?? false,
      }),
    });
    renderSettings();
  });
}

/* ─── boot ────────────────────────────────────────────────── */
await loadSettings();
await checkCapture();
render();
