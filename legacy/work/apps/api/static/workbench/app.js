const state = {
  status: null,
  rag: { traceId: null, lastQuestion: null },
  agent: { runId: null, traceId: null },
  data: { runId: null, traceId: null },
  eval: null,
  traces: []
};

const titles = {
  dashboard: ["Enterprise AI Workbench", "企业知识问答、业务流程 Agent、数据分析 Agent 一体化工作台"],
  rag: ["知识库问答", "导入资料、提出问题、查看引用和检索证据"],
  agent: ["Workflow Agent", "查看计划、工具调用、确认动作和业务结果"],
  data: ["数据分析 Agent", "自然语言查数据，自动展示 SQL、表格和图表"],
  eval: ["效果检验", "运行评测并查看指标、失败样例和报告"],
  trace: ["Trace / Debug", "查看最近请求的执行细节，避免黑盒体验"]
};

function $(id) {
  return document.getElementById(id);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = payload.message || payload.detail?.message || payload.detail || "请求失败";
    const suggestion = payload.suggestion || payload.detail?.suggestion || "";
    throw new Error(`${message}${suggestion ? `：${suggestion}` : ""}`);
  }
  return payload;
}

function post(path, body = {}) {
  return api(path, { method: "POST", body: JSON.stringify(body) });
}

function toast(message, type = "info") {
  const el = $("toast");
  el.textContent = message;
  el.className = `toast ${type}`;
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => el.classList.add("hidden"), 4200);
}

function setLoading(button, isLoading, label) {
  if (!button) return;
  if (isLoading) {
    button.dataset.label = button.textContent;
    button.textContent = label || "处理中";
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label || button.textContent;
    button.disabled = false;
  }
}

function route() {
  const raw = window.location.hash.replace("#", "") || "dashboard";
  const [name, value] = raw.split("/");
  const page = titles[name] ? name : "dashboard";
  document.querySelectorAll(".page").forEach(el => el.classList.remove("active"));
  $(`${page}Page`).classList.add("active");
  document.querySelectorAll(".nav-list a").forEach(a => a.classList.toggle("active", a.dataset.route === page));
  $("pageTitle").textContent = titles[page][0];
  $("pageSubtitle").textContent = titles[page][1];
  if (page === "trace") {
    loadTraces(value);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fmt(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  return String(value);
}

function statusClass(value) {
  const text = String(value || "").toLowerCase();
  if (["ok", "ready", "success", "completed", "real"].some(item => text.includes(item))) return "status-ok";
  if (["degraded", "mock", "empty", "waiting"].some(item => text.includes(item))) return "status-warn";
  if (["failed", "error", "rejected", "missing"].some(item => text.includes(item))) return "status-bad";
  return "";
}

function renderTable(rows, targetId, preferredColumns = null) {
  const target = $(targetId);
  if (!rows || !rows.length) {
    target.innerHTML = "<p class='muted'>暂无表格结果。</p>";
    return;
  }
  const columns = preferredColumns && preferredColumns.length ? preferredColumns : Object.keys(rows[0]);
  target.innerHTML = `
    <table>
      <thead><tr>${columns.map(col => `<th>${escapeHtml(col)}</th>`).join("")}</tr></thead>
      <tbody>
        ${rows.map(row => `<tr>${columns.map(col => `<td>${escapeHtml(row[col])}</td>`).join("")}</tr>`).join("")}
      </tbody>
    </table>
  `;
}

async function loadStatus() {
  state.status = await api("/api/status");
  $("versionText").textContent = `v${state.status.version}`;
  const llm = state.status.llm || {};
  $("modePill").textContent = `${state.status.mode === "demo" ? "Demo 模式" : "真实模式"} · LLM ${llm.status || "-"}`;
  renderDashboardStatus(state.status);
  renderDatasetStatus(state.status.demo_data.sample_database);
}

function renderDashboardStatus(status) {
  const cards = [
    ["API 状态", status.api_status],
    ["LLM 状态", status.llm.status],
    ["知识库文档", status.knowledge_base.document_count],
    ["向量索引", status.knowledge_base.vector_index_status],
    ["Demo 数据", status.demo_data.initialized ? "ready" : "not initialized"],
    ["最近评测分数", status.evaluation.latest_score ?? "暂无"]
  ];
  $("statusGrid").innerHTML = cards.map(([label, value]) => `
    <article class="status-card">
      <span>${escapeHtml(label)}</span>
      <strong class="${statusClass(value)}">${escapeHtml(fmt(value))}</strong>
    </article>
  `).join("");
}

async function initDemo() {
  const btn = $("initDemoBtn");
  setLoading(btn, true, "正在初始化");
  try {
    const result = await post("/api/demo/init");
    toast(result.message || "演示数据已初始化", "success");
    await Promise.all([loadStatus(), loadDocuments(), loadEvalLatest(), loadDataExamples()]);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setLoading(btn, false);
  }
}

async function loadDocuments() {
  const payload = await api("/api/rag/documents");
  $("docCount").textContent = payload.document_count;
  $("chunkCount").textContent = payload.chunk_count;
  if (!payload.documents.length) {
    $("documentList").innerHTML = "<div class='doc-item'>暂无文档。请先导入示例文档。</div>";
    return;
  }
  $("documentList").innerHTML = payload.documents.map(doc => `
    <div class="doc-item">
      <strong>${escapeHtml(doc.filename)}</strong>
      <div class="doc-meta">
        <span>${escapeHtml(doc.domain)}</span>
        <span>${escapeHtml(doc.status)}</span>
        <span>${doc.chunk_count} chunks</span>
      </div>
    </div>
  `).join("");
}

async function loadRagExamples() {
  const payload = await api("/api/rag/examples");
  $("ragExamples").innerHTML = payload.examples.map(question => `
    <button data-rag-question="${escapeHtml(question)}">${escapeHtml(question)}</button>
  `).join("");
  $("ragExamples").querySelectorAll("button").forEach(button => {
    button.addEventListener("click", () => {
      $("ragQuestion").value = button.dataset.ragQuestion;
      askRag();
    });
  });
}

async function ingestDocs() {
  const btn = $("ingestDocsBtn");
  setLoading(btn, true, "导入中");
  try {
    const result = await post("/api/rag/ingest-samples");
    toast(result.next_step || "示例文档已导入", "success");
    await Promise.all([loadStatus(), loadDocuments()]);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setLoading(btn, false);
  }
}

function addChatMessage(text, kind) {
  const node = document.createElement("div");
  node.className = kind === "user" ? "user-msg" : "assistant-msg";
  node.textContent = text;
  $("chatLog").appendChild(node);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
}

async function askRag() {
  const question = $("ragQuestion").value.trim();
  if (!question) {
    toast("请输入问题或点击示例问题。");
    return;
  }
  addChatMessage(question, "user");
  setLoading($("askRagBtn"), true, "检索中");
  try {
    const payload = await post("/api/rag/ask", {
      question,
      top_k: Number($("ragTopK").value || 5),
      retrieval_mode: $("ragMode").value,
      rerank: $("ragRerank").checked,
      query_rewrite: $("ragRewrite").checked,
      temperature: Number($("ragTemp").value || 0.2),
      model: $("ragModel").value.trim() || null
    });
    state.rag.traceId = payload.trace_id;
    state.rag.lastQuestion = question;
    addChatMessage(payload.answer || payload.message || "没有返回答案。", "assistant");
    renderRagEvidence(payload);
  } catch (error) {
    addChatMessage(`执行失败：${error.message}`, "assistant");
  } finally {
    setLoading($("askRagBtn"), false);
  }
}

function renderRagEvidence(payload) {
  const citations = payload.citations || [];
  const evidence = payload.evidence || [];
  const header = `
    <div class="evidence-item">
      <strong>trace_id</strong>
      <div class="doc-meta">
        <span>${escapeHtml(payload.trace_id)}</span>
        <span>耗时 ${fmt(payload.latency_ms)} ms</span>
        <span>置信 ${fmt(payload.confidence)}</span>
      </div>
    </div>
  `;
  const citationHtml = citations.map(item => `
    <div class="evidence-item">
      <strong>${escapeHtml(item.document || item.filename || item.document_id)}</strong>
      <div class="doc-meta">
        <span>${escapeHtml(item.chunk_id)}</span>
        <span>page ${fmt(item.page)}</span>
        <span>score ${fmt(item.score)}</span>
      </div>
      <p>${escapeHtml(item.snippet || "")}</p>
    </div>
  `).join("");
  const debugHtml = `
    <details class="advanced" open>
      <summary>命中 chunks</summary>
      ${evidence.slice(0, 5).map(item => `
        <div class="evidence-item">
          <strong>${escapeHtml(item.filename || item.document_id)}</strong>
          <div class="doc-meta">
            <span>${escapeHtml(item.chunk_id)}</span>
            <span>score ${fmt(item.score)}</span>
            <span>rerank ${fmt(item.rerank_score)}</span>
          </div>
          <p>${escapeHtml(String(item.text || "").slice(0, 260))}</p>
        </div>
      `).join("")}
    </details>
    <details class="advanced">
      <summary>关键调试信息</summary>
      <pre>${escapeHtml(JSON.stringify(payload.debug || {}, null, 2))}</pre>
    </details>
  `;
  $("ragEvidence").innerHTML = header + (citationHtml || "<div class='evidence-item'>暂无引用。</div>") + debugHtml;
}

async function loadAgentExamples() {
  const payload = await api("/api/agent/examples");
  $("agentExamples").innerHTML = payload.examples.map(item => `
    <button data-example="${escapeHtml(item.id)}" data-task="${escapeHtml(item.task)}" data-scenario="${escapeHtml(item.scenario)}">${escapeHtml(item.task)}</button>
  `).join("");
  $("agentExamples").querySelectorAll("button").forEach(button => {
    button.addEventListener("click", () => {
      $("agentTask").value = button.dataset.task;
      $("agentScenario").value = button.dataset.scenario;
      runAgentExample(button.dataset.example);
    });
  });
}

async function runAgentExample(exampleId) {
  setLoading($("runAgentBtn"), true, "运行中");
  try {
    const payload = await post("/api/agent/run-example", {
      example_id: exampleId,
      scenario: $("agentScenario").value
    });
    renderAgent(payload);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setLoading($("runAgentBtn"), false);
  }
}

async function runAgent() {
  const task = $("agentTask").value.trim();
  if (!task) {
    toast("请输入任务或点击示例任务。");
    return;
  }
  setLoading($("runAgentBtn"), true, "运行中");
  try {
    const payload = await post("/api/agent/run", {
      task,
      scenario: $("agentScenario").value,
      max_steps: 8
    });
    renderAgent(payload);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setLoading($("runAgentBtn"), false);
  }
}

function renderAgent(payload) {
  state.agent.runId = payload.run_id;
  state.agent.traceId = payload.trace_id;
  $("agentResult").textContent = [
    `状态：${payload.status}`,
    `trace_id：${payload.trace_id}`,
    "",
    payload.final_response || ""
  ].join("\n");
  $("agentResult").textContent = [
    `状态：${payload.status}`,
    `答案类型：${payload.answer_type || "-"}`,
    `置信度：${fmt(payload.confidence)}`,
    `trace_id：${payload.trace_id}`,
    "",
    payload.final_response || ""
  ].join("\n");
  $("agentTimeline").innerHTML = (payload.timeline || []).map(item => `
    <div class="timeline-item">
      <div class="timeline-index">${item.step}</div>
      <div class="timeline-body">
        <strong>${escapeHtml(item.name)} <span class="${statusClass(item.status)}">${escapeHtml(item.status)}</span></strong>
        <p>${escapeHtml(item.summary || "")}</p>
      </div>
    </div>
  `).join("");
  $("toolCalls").innerHTML = (payload.tool_calls || []).map(call => `
    <div class="tool-call">
      <strong>${escapeHtml(call.tool_name)}</strong>
      <div class="tool-meta">
        <span>${escapeHtml(call.status)}</span>
        <span>${escapeHtml(call.latency)}</span>
      </div>
      <details>
        <summary>查看输入与输出摘要</summary>
        <pre>${escapeHtml(JSON.stringify({
          tool_input: call.tool_input,
          tool_output: call.tool_output,
          error: call.error
        }, null, 2))}</pre>
      </details>
    </div>
  `).join("") || "<div class='tool-call'>暂无工具调用。</div>";
  const qaBlocks = [];
  if (payload.qa_plan && Object.keys(payload.qa_plan).length) {
    qaBlocks.push(traceBlock("QA 计划", payload.qa_plan));
  }
  if (payload.evidence_report && Object.keys(payload.evidence_report).length) {
    qaBlocks.push(traceBlock("证据报告", payload.evidence_report));
  }
  if (payload.verification && Object.keys(payload.verification).length) {
    qaBlocks.push(traceBlock("验证结果", payload.verification));
  }
  if (qaBlocks.length) {
    $("toolCalls").innerHTML += qaBlocks.join("");
  }
  renderConfirmation(payload.pending_confirmation);
}

function renderConfirmation(action) {
  const box = $("confirmationBox");
  if (!action) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  const displayTool = action.tool === "create_ticket" ? "create_ticket_mock" : action.tool;
  box.classList.remove("hidden");
  box.innerHTML = `
    <h3>高风险操作确认</h3>
    <p>${escapeHtml(action.reason)}</p>
    <p><strong>${escapeHtml(displayTool)}</strong></p>
    <pre>${escapeHtml(JSON.stringify(action.args, null, 2))}</pre>
    <div class="button-row">
      <button id="approveAgentBtn" class="primary">确认创建</button>
      <button id="cancelAgentBtn">取消</button>
    </div>
  `;
  $("approveAgentBtn").addEventListener("click", () => confirmAgent(true));
  $("cancelAgentBtn").addEventListener("click", () => confirmAgent(false));
}

async function confirmAgent(approved) {
  if (!state.agent.runId) return;
  try {
    const payload = await post("/api/agent/confirm", {
      run_id: state.agent.runId,
      approved,
      comment: approved ? "页面确认创建" : "页面取消"
    });
    toast(payload.final_answer || "确认动作已处理", approved ? "success" : "info");
    $("confirmationBox").classList.add("hidden");
    $("agentResult").textContent += `\n\n确认结果：${payload.final_answer || payload.status}`;
  } catch (error) {
    toast(error.message, "error");
  }
}

function renderDatasetStatus(db) {
  if (!db) return;
  $("datasetStatus").innerHTML = `
    <div><strong>${db.initialized ? "已初始化" : "未初始化"}</strong><span>数据库状态</span></div>
    <div><strong>${fmt(db.table_count)}</strong><span>表数量</span></div>
    <div><strong>${fmt(db.row_count)}</strong><span>行数量</span></div>
    <div><strong>${escapeHtml(db.updated_at ? db.updated_at.slice(0, 10) : "-")}</strong><span>最近更新</span></div>
  `;
}

async function loadDataExamples() {
  const payload = await api("/api/data-agent/examples");
  renderDatasetStatus(payload.dataset);
  $("dataExamples").innerHTML = payload.examples.map(item => `
    <button data-question="${escapeHtml(item.question)}">${escapeHtml(item.question)}</button>
  `).join("");
  $("dataExamples").querySelectorAll("button").forEach(button => {
    button.addEventListener("click", () => {
      $("dataQuestion").value = button.dataset.question;
      askData();
    });
  });
}

async function initDb() {
  setLoading($("initDbBtn"), true, "初始化中");
  try {
    const payload = await post("/api/data-agent/init-sample-db");
    toast(`sample database 已初始化，${payload.row_count} 行数据可用。`, "success");
    await Promise.all([loadStatus(), loadDataExamples()]);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setLoading($("initDbBtn"), false);
  }
}

async function askData() {
  const question = $("dataQuestion").value.trim();
  if (!question) {
    toast("请输入问题或点击示例问题。");
    return;
  }
  setLoading($("askDataBtn"), true, "分析中");
  try {
    const payload = await post("/api/data-agent/ask", { question });
    renderData(payload);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setLoading($("askDataBtn"), false);
  }
}

function renderData(payload) {
  state.data.runId = payload.run_id;
  state.data.traceId = payload.trace_id;
  $("dataAnswer").textContent = [
    `状态：${payload.status}`,
    `trace_id：${payload.trace_id}`,
    "",
    payload.answer || ""
  ].join("\n");
  $("metricCards").innerHTML = (payload.metrics || []).map(metric => `
    <article class="metric-card">
      <span>${escapeHtml(metric.label)}</span>
      <strong>${escapeHtml(fmt(metric.value))}</strong>
    </article>
  `).join("");
  if (payload.chart_url) {
    $("chartBox").innerHTML = `<img src="${escapeHtml(payload.chart_url)}" alt="分析图表" />`;
  } else if (payload.chart && payload.chart.chart_error) {
    $("chartBox").innerHTML = `<div class="result-box">图表生成失败：${escapeHtml(payload.chart.chart_error)}。文本分析仍可用。</div>`;
  } else {
    $("chartBox").innerHTML = "";
  }
  renderTable(payload.table_preview || [], "tablePreview", payload.columns || null);
  $("sqlBox").textContent = payload.safe_sql || payload.generated_sql || "暂无 SQL。";
  $("sqlSafetyBox").innerHTML = `
    <div class="result-box">
      <strong>SQL 安全检查：${payload.sql_safety?.is_valid ? "通过" : "拒绝"}</strong>
      <p>${escapeHtml((payload.sql_safety?.reasons || []).join("；"))}</p>
    </div>
  `;
}

async function testSafety() {
  setLoading($("testSafetyBtn"), true, "检测中");
  try {
    const payload = await post("/api/data-agent/test-safety");
    state.data.traceId = payload.trace_id;
    $("dataAnswer").textContent = `${payload.message}\n原因：${(payload.safety_check.reasons || []).join("；")}\n建议：${payload.suggestion}`;
    $("metricCards").innerHTML = "";
    $("chartBox").innerHTML = "";
    $("tablePreview").innerHTML = "";
    $("sqlBox").textContent = payload.dangerous_sql;
    $("sqlSafetyBox").innerHTML = `<div class="result-box"><strong>拒绝原因</strong><p>${escapeHtml((payload.safety_check.reasons || []).join("；"))}</p></div>`;
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setLoading($("testSafetyBtn"), false);
  }
}

async function loadEvalLatest() {
  const payload = await api("/api/eval/latest");
  state.eval = payload.report;
  renderEval(payload.report);
}

async function runEval(target) {
  const button = document.querySelector(`[data-eval="${target}"]`);
  setLoading(button, true, "评测中");
  try {
    const payload = await post("/api/eval/run", { target });
    state.eval = payload;
    renderEval(payload);
    toast("评测完成，报告已刷新。", "success");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setLoading(button, false);
  }
}

function renderEval(report) {
  const results = report.results || {};
  const metricCards = [];
  Object.entries(results).forEach(([target, result]) => {
    Object.entries(result.metrics || {}).forEach(([name, value]) => {
      metricCards.push([`${target} · ${name}`, value]);
    });
  });
  $("evalMetrics").innerHTML = metricCards.slice(0, 8).map(([label, value]) => `
    <article class="metric-card"><span>${escapeHtml(label)}</span><strong>${fmt(value)}</strong></article>
  `).join("");

  const rows = [];
  Object.entries(results).forEach(([target, result]) => {
    (result.cases || []).slice(0, 20).forEach(item => rows.push({
      target,
      question: item.question || item.user_task || "-",
      expected: item.expected_answer || item.expected_outcome || item.expected_sql_pattern || "-",
      actual: item.answer || item.generated_sql || (item.actual_tools || []).join(", ") || "-",
      status: item.passed ? "passed" : "failed",
      score: item.answer_relevancy ?? item.task_success ?? item.execution_success ?? "-",
      failure_reason: item.passed ? "" : "未达到样例期望",
      trace_id: item.trace_id || "-"
    }));
  });
  renderTable(rows, "evalTable", ["target", "question", "expected", "actual", "status", "score", "failure_reason", "trace_id"]);

  const failures = [];
  Object.entries(results).forEach(([target, result]) => {
    (result.failures || []).forEach(item => failures.push({ target, item }));
  });
  $("failureSamples").innerHTML = failures.length ? failures.map(({ target, item }) => `
    <div class="failure-item">
      <strong>${escapeHtml(target)}：${escapeHtml(item.question || item.user_task || "-")}</strong>
      <p>原因：${escapeHtml(item.failure_reason || "样例未通过当前启发式检查")}</p>
      <p>建议：补充知识文档、改进工具路由或强化 SQL 生成约束。</p>
    </div>
  `).join("") : "<div class='failure-item'>当前报告没有失败样例。</div>";
}

async function loadTraces(selectedId = null) {
  const payload = await api("/api/traces?limit=50");
  state.traces = payload.traces || [];
  $("traceList").innerHTML = state.traces.length ? state.traces.map(item => `
    <div class="trace-item" data-trace="${escapeHtml(item.trace_id)}">
      <strong>${escapeHtml(item.trace_id)}</strong>
      <div class="trace-meta">
        <span>${escapeHtml(item.type)}</span>
        <span class="${statusClass(item.status)}">${escapeHtml(item.status)}</span>
        <span>${escapeHtml(fmt(item.latency))} ms</span>
        <span>${escapeHtml(item.created_at || "")}</span>
      </div>
      <p>${escapeHtml(item.user_input || "")}</p>
    </div>
  `).join("") : "<div class='trace-item'>暂无 trace。运行任意示例后会出现在这里。</div>";
  $("traceList").querySelectorAll(".trace-item[data-trace]").forEach(item => {
    item.addEventListener("click", () => loadTraceDetail(item.dataset.trace));
  });
  const target = selectedId || state.rag.traceId || state.agent.traceId || state.data.traceId;
  if (target) loadTraceDetail(target);
}

async function loadTraceDetail(traceId) {
  try {
    const detail = await api(`/api/traces/${encodeURIComponent(traceId)}`);
    $("traceType").textContent = detail.type || "Trace";
    $("traceDetail").innerHTML = renderTraceDetail(detail);
  } catch (error) {
    $("traceDetail").innerHTML = `<div class="trace-block">未找到 trace：${escapeHtml(error.message)}</div>`;
  }
}

function renderTraceDetail(detail) {
  const blocks = [];
  if (detail.rag) {
    blocks.push(traceBlock("RAG 检索", {
      query: detail.rag.query || detail.rag.user_input,
      selected_domain: detail.rag.selected_domain,
      total_latency_ms: detail.rag.total_latency_ms,
      citations: detail.rag.sources
    }));
  }
  (detail.runs || []).forEach(run => {
    blocks.push(traceBlock("Agent 执行", {
      scenario: run.scenario,
      mode: run.mode,
      status: run.status,
      answer_type: run.answer_type,
      confidence: run.confidence,
      final_response: run.final_answer,
      qa_plan: run.qa_plan,
      evidence_report: run.evidence_report,
      verification: run.verification,
      steps: run.tool_steps,
      confirmation: run.pending_action
    }));
  });
  (detail.data_agent || []).forEach(row => {
    blocks.push(traceBlock("Data Agent 分析", {
      question: row.question,
      schema_used: row.schema_used,
      generated_sql: row.sql_plan?.sql,
      safety_check: row.sql_validation,
      result_preview: row.row_count,
      chart: row.chart_result,
      final_answer: row.final_answer
    }));
  });
  (detail.workbench || []).forEach(row => {
    blocks.push(traceBlock(row.type || "Workbench", row));
  });
  if (detail.llm_calls && detail.llm_calls.length) {
    blocks.push(traceBlock("模型调用摘要", detail.llm_calls.slice(0, 5)));
  }
  if (detail.events && detail.events.length) {
    blocks.push(traceBlock("请求事件", detail.events.slice(0, 8)));
  }
  return blocks.join("") || "<div class='trace-block'>没有可展示的详情。</div>";
}

function traceBlock(title, payload) {
  return `
    <div class="trace-block">
      <strong>${escapeHtml(title)}</strong>
      <pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
    </div>
  `;
}

function bindEvents() {
  window.addEventListener("hashchange", route);
  document.querySelectorAll("[data-jump]").forEach(button => {
    button.addEventListener("click", () => {
      window.location.hash = button.dataset.jump;
    });
  });
  $("initDemoBtn").addEventListener("click", initDemo);
  $("quickRagBtn").addEventListener("click", () => { window.location.hash = "rag"; setTimeout(() => $("ragExamples").querySelector("button")?.click(), 100); });
  $("quickAgentBtn").addEventListener("click", () => { window.location.hash = "agent"; setTimeout(() => $("agentExamples").querySelector("button")?.click(), 100); });
  $("quickDataBtn").addEventListener("click", () => { window.location.hash = "data"; setTimeout(() => $("dataExamples").querySelector("button")?.click(), 100); });
  $("ingestDocsBtn").addEventListener("click", ingestDocs);
  $("askRagBtn").addEventListener("click", askRag);
  $("ragQuestion").addEventListener("keydown", event => { if (event.key === "Enter") askRag(); });
  $("ragTraceBtn").addEventListener("click", () => { window.location.hash = state.rag.traceId ? `trace/${state.rag.traceId}` : "trace"; });
  $("runAgentBtn").addEventListener("click", runAgent);
  $("agentTraceBtn").addEventListener("click", () => { window.location.hash = state.agent.traceId ? `trace/${state.agent.traceId}` : "trace"; });
  $("initDbBtn").addEventListener("click", initDb);
  $("askDataBtn").addEventListener("click", askData);
  $("dataQuestion").addEventListener("keydown", event => { if (event.key === "Enter") askData(); });
  $("testSafetyBtn").addEventListener("click", testSafety);
  $("dataTraceBtn").addEventListener("click", () => { window.location.hash = state.data.traceId ? `trace/${state.data.traceId}` : "trace"; });
  document.querySelectorAll("[data-eval]").forEach(button => button.addEventListener("click", () => runEval(button.dataset.eval)));
  $("refreshTraceBtn").addEventListener("click", () => loadTraces());
}

async function bootstrap() {
  bindEvents();
  route();
  try {
    await Promise.all([
      loadStatus(),
      loadDocuments(),
      loadRagExamples(),
      loadAgentExamples(),
      loadDataExamples(),
      loadEvalLatest()
    ]);
  } catch (error) {
    toast(error.message, "error");
  }
}

bootstrap();
