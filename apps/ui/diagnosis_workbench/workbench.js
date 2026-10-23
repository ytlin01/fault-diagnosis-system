const state = {
  conversations: [],
  activeConversationId: null,
  currentEnvelope: null,
  rating: "",
  renameTarget: null,
  lastSubmittedQuery: "",
  feedbackExpanded: false,
  feedbackDraft: {
    tags: [],
    correctAnswer: "",
    freeText: "",
  },
};

const routeCopy = {
  route_a_structured: {
    source: "结构化诊断记录",
    boundary: "用于定位可能原因，请结合现场确认后执行。",
  },
  route_b_document: {
    source: "文档证据",
    boundary: "当前回答提供的是文档证据，不直接等于诊断结论。",
  },
  route_c_case_governance: {
    source: "相似案例",
    boundary: "当前回答提供的是相似案例线索，采取动作前请人工确认。",
  },
  fallback: {
    source: "上下文不足",
    boundary: "信息还不够，建议补充报警代码、工位、现象或已做过的动作。",
  },
};

const EXAMPLE_QUESTIONS = [
  {
    tag: "报警代码",
    title: "先确认报警含义",
    question: "M03CVMA-02-03 报警是什么意思？",
    hint: "适合展示结构化诊断记录的首轮问答。",
  },
  {
    tag: "SOP 文档",
    title: "查找配置步骤",
    question: "查询 TCP IPv4 IP 地址设置相关的 SOP 文档",
    hint: "适合展示文档证据、锚点和 evidence-only 边界。",
  },
  {
    tag: "相似案例",
    title: "看下类似问题",
    question: "cowling 组装一直 NG，类似案例有哪些？",
    hint: "适合展示相似案例 candidate 提示和人工确认边界。",
  },
  {
    tag: "现场追问",
    title: "继续追问下一步",
    question: "如果已经检查过网线，下一步该怎么排查？",
    hint: "适合录屏时展示多轮追问和历史对话承接。",
  },
];

let progressTimer = null;

document.addEventListener("DOMContentLoaded", init);

async function init() {
  bindEvents();
  await loadConversations();
  if (!state.activeConversationId) {
    await createConversation("新的现场诊断对话");
  } else {
    renderActiveConversation();
  }
}

function bindEvents() {
  qs("#sendQuestion").addEventListener("click", sendQuestion);
  qs("#questionInput").addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      sendQuestion();
    }
  });
  qs("#newConversation").addEventListener("click", () => createConversation("新的现场诊断对话"));
  qs("#confirmRename").addEventListener("click", async (event) => {
    event.preventDefault();
    await confirmRename();
  });
}

async function loadConversations() {
  const payload = await apiGet("/api/conversations");
  state.conversations = payload.conversations || [];
  if (!state.activeConversationId && state.conversations.length) {
    state.activeConversationId = state.conversations[0].conversation_id;
  }
  renderConversations();
}

async function createConversation(title) {
  resetFeedbackDraft();
  const payload = await apiPost("/api/conversations", { title });
  state.activeConversationId = payload.conversation.conversation_id;
  await loadConversations();
  renderActiveConversation();
  toast("已新建对话");
}

async function sendQuestion() {
  const queryText = qs("#questionInput").value.trim();
  if (!queryText) {
    toast("请先输入现场问题");
    return;
  }

  state.lastSubmittedQuery = queryText;
  resetFeedbackDraft();

  try {
    setBusy(true);
    const envelope = await apiPost("/api/ask", {
      query_text: queryText,
      conversation_id: state.activeConversationId,
    });
    state.currentEnvelope = envelope;
    await apiPost("/api/conversations/add-turn", {
      conversation_id: state.activeConversationId,
      envelope,
    });
    await loadConversations();
    qs("#questionInput").value = "";
    renderActiveConversation();
    toast("已生成诊断回答");
  } catch (error) {
    renderError(error.message || "请求失败，请稍后重试");
  } finally {
    setBusy(false);
  }
}

async function submitFeedback() {
  if (!state.currentEnvelope) {
    toast("请先生成回答");
    return;
  }
  if (!state.rating) {
    toast("请先选择点赞或点踩");
    return;
  }
  const answer = state.currentEnvelope.answer || {};
  const meta = state.currentEnvelope.meta || {};
  const feedback = {
    query_id: meta.query_id,
    answer_id: meta.answer_id,
    route_used: answer.decision?.route_family || "",
    rating: state.rating,
    feedback_tags: [...state.feedbackDraft.tags],
    free_text: state.feedbackDraft.freeText,
    correct_answer: state.feedbackDraft.correctAnswer,
    expected_route: "",
    created_by_role: "tester",
    api_version: answer.contract_version || "1.0.0-draft",
    prompt_version: meta.prompt_version,
    kg_or_index_version: meta.kg_or_index_version,
  };
  const response = await apiPost("/api/feedback", feedback);
  toast(response.feedback.bad_case_candidate ? "反馈已标记为 bad-case 候选" : "反馈已保存");
  resetFeedbackDraft();
  renderActiveConversation();
}

function getActiveConversation() {
  return state.conversations.find((item) => item.conversation_id === state.activeConversationId) || null;
}

function renderActiveConversation() {
  clearTimeout(progressTimer);
  const conversation = getActiveConversation();
  if (!conversation || !(conversation.turns || []).length) {
    state.currentEnvelope = null;
    renderEmptyState();
    return;
  }

  const turns = conversation.turns || [];
  const lastTurn = turns[turns.length - 1];
  state.currentEnvelope = turnToEnvelope(lastTurn);

  qs("#threadView").innerHTML = `
    <div class="chat-thread">
      ${turns.map((turn, index) => renderTurn(turn, index === turns.length - 1)).join("")}
    </div>
  `;
  bindThreadActions();
}

function renderEmptyState() {
  qs("#threadView").innerHTML = `
    <div class="chat-thread">
      <div class="empty-hero">
        <div class="empty-hero-copy">
          <div class="empty-title">把现场问题说清楚，我们一起往前走</div>
          <div class="empty-summary">
            你可以直接问报警代码、操作文档、相似案例，或者在上一轮基础上继续追问。
            系统会自动选择合适的诊断路径，并把依据和边界说明讲清楚。
          </div>
        </div>
        <div class="example-grid">
          ${EXAMPLE_QUESTIONS.map((item) => `
            <button class="example-card" type="button" data-question="${escapeHtml(item.question)}">
              <span class="example-tag">${escapeHtml(item.tag)}</span>
              <span class="example-title">${escapeHtml(item.title)}</span>
              <span>${escapeHtml(item.question)}</span>
              <span class="example-hint">${escapeHtml(item.hint)}</span>
            </button>
          `).join("")}
        </div>
      </div>
    </div>
  `;
  bindThreadActions();
}

function renderTurn(turn, isLatest) {
  const answer = turn.answer || {};
  const warnings = turn.warnings || [];
  const routeFamily = answer.decision?.route_family || "fallback";
  const copy = routeCopy[routeFamily] || routeCopy.fallback;

  return `
    <div class="turn-group">
      <div class="message-row user">
        <div class="user-bubble">${escapeHtml(turn.query_text || "")}</div>
      </div>
      <div class="message-row assistant">
        <div class="assistant-card">
          <div class="answer-meta">
            <span class="context-pill"><strong>依据</strong> ${escapeHtml(copy.source)}</span>
            <span class="context-pill"><strong>边界</strong> ${escapeHtml(copy.boundary)}</span>
          </div>
          <div class="answer-title">${escapeHtml(answer.summary?.headline || "暂无标题")}</div>
          <div class="safe-summary">${escapeHtml(answer.summary?.user_safe_summary || "-")}</div>
          ${renderWarnings(warnings)}
          ${renderRootActions(answer.root_cause_actions || [])}
          ${renderEvidence(answer.diagnosis_results || [])}
          ${isLatest ? renderFeedbackWidget() : ""}
        </div>
      </div>
    </div>
  `;
}

function renderWarnings(warnings) {
  if (!warnings.length) return "";
  return `
    <div class="warning-list">
      ${warnings.map((item) => `<div class="warning-row">${escapeHtml(item)}</div>`).join("")}
    </div>
  `;
}

function renderRootActions(actions) {
  if (!actions.length) return "";
  return `
    <div class="subsection">
      <div class="subsection-title">建议先做</div>
      <div class="action-list">
        ${actions.map((item) => renderActionItem(item)).join("")}
      </div>
    </div>
  `;
}

function renderEvidence(results) {
  if (!results.length) {
    return `<div class="empty-state">本次回答没有可展示的诊断结果，请尝试补充更多上下文。</div>`;
  }
  return `
    <div class="subsection">
      <div class="subsection-title">诊断结果与证据</div>
      <div class="result-list">
        ${results.map((item) => renderResult(item)).join("")}
      </div>
    </div>
  `;
}

function renderResult(item) {
  const evidence = item.evidence || [];
  const actions = item.actions || [];
  return `
    <div class="result-row">
      <div class="result-title">
        <span>${escapeHtml(item.rank || "")}. ${escapeHtml(item.title || "")}</span>
        <span class="status-badge status-${escapeHtml(item.status || "unknown")}">${escapeHtml(item.status || "unknown")}</span>
      </div>
      <div class="tiny-meta">${escapeHtml(item.result_type || "")} / ${escapeHtml(item.confidence || "")}</div>
      <div class="result-desc">${escapeHtml(item.description || "")}</div>
      <div class="evidence-list">
        ${evidence.length ? evidence.map((entry) => renderEvidenceItem(entry)).join("") : `<div class="empty-state">暂无证据</div>`}
      </div>
      ${actions.length ? `
        <div class="subsection">
          <div class="subsection-title">相关动作</div>
          <div class="action-list">
            ${actions.map((entry) => renderActionItem(entry)).join("")}
          </div>
        </div>` : ""}
    </div>
  `;
}

function renderEvidenceItem(item) {
  return `
    <div class="evidence-row">
      <strong>${escapeHtml(item.evidence_type || "")}</strong>
      <div>${escapeHtml(item.summary || "")}</div>
      <div class="tiny-meta">${escapeHtml(item.source_type || "")} / ${escapeHtml(item.source_id || "")} / anchor=${escapeHtml(item.anchor || "")}</div>
    </div>
  `;
}

function renderActionItem(item) {
  return `
    <div class="action-row">
      <strong>${escapeHtml(String(item.step || ""))}. ${escapeHtml(item.action || "")}</strong>
      <div class="tiny-meta">${escapeHtml(item.source_status || "")}</div>
    </div>
  `;
}

function renderFeedbackWidget() {
  const expanded = state.feedbackExpanded || !!state.rating || !!state.feedbackDraft.correctAnswer || !!state.feedbackDraft.freeText || state.feedbackDraft.tags.length > 0;
  return `
    <div class="feedback-widget">
      <div class="feedback-top">
        <div>
          <div class="feedback-title">这条回答对你有帮助吗？</div>
          <div class="feedback-note">反馈会进入 bad-case 候选日志，用于后续改进。</div>
        </div>
        <div class="feedback-actions">
          <button class="rating-btn feedback-rating-btn ${state.rating === "thumbs_up" ? "active" : ""}" data-rating="thumbs_up" type="button" title="有帮助">👍</button>
          <button class="rating-btn feedback-rating-btn ${state.rating === "thumbs_down" ? "active" : ""}" data-rating="thumbs_down" type="button" title="需要复核">👎</button>
          <button id="toggleFeedbackDetails" class="ghost-btn" type="button">${expanded ? "收起补充" : "补充建议"}</button>
        </div>
      </div>
      <div class="feedback-detail ${expanded ? "" : "hidden"}">
        <div class="tag-group">
          ${renderFeedbackTag("answer_wrong", "答案不对")}
          ${renderFeedbackTag("evidence_insufficient", "证据不足")}
          ${renderFeedbackTag("route_wrong", "路由不合适")}
          ${renderFeedbackTag("overclaim", "说得太满")}
          ${renderFeedbackTag("not_useful", "暂时没帮上忙")}
        </div>
        <div class="field-grid">
          <label class="field-label">
            正确答案
            <textarea id="feedbackCorrectAnswer" rows="3">${escapeHtml(state.feedbackDraft.correctAnswer)}</textarea>
          </label>
          <label class="field-label">
            补充说明
            <textarea id="feedbackFreeText" rows="3">${escapeHtml(state.feedbackDraft.freeText)}</textarea>
          </label>
        </div>
        <div class="feedback-footer">
          <button id="submitFeedback" class="primary-btn" type="button">保存反馈</button>
        </div>
      </div>
    </div>
  `;
}

function renderFeedbackTag(value, label) {
  const checked = state.feedbackDraft.tags.includes(value) ? "checked" : "";
  return `
    <label class="tag-pill">
      <input class="feedback-tag-input" type="checkbox" value="${escapeHtml(value)}" ${checked}>
      <span>${escapeHtml(label)}</span>
    </label>
  `;
}

function renderLoadingState() {
  const conversation = getActiveConversation();
  const turns = conversation?.turns || [];
  qs("#threadView").innerHTML = `
    <div class="chat-thread">
      ${turns.map((turn, index) => renderTurn(turn, index === turns.length - 1)).join("")}
      ${state.lastSubmittedQuery ? `
        <div class="turn-group">
          <div class="message-row user">
            <div class="user-bubble">${escapeHtml(state.lastSubmittedQuery)}</div>
          </div>
          <div class="message-row assistant">
            <div class="loading-shell">
              <div class="loading-title">正在整理这条回答…</div>
              <div class="loading-copy">系统正在识别问题、选择路径，并整理回答与证据。</div>
              <div class="loading-stage">
                <div class="loading-stage-head">
                  <span class="loading-stage-label">步骤 1 解析问题</span>
                  <span class="loading-stage-state">进行中</span>
                </div>
                <div class="loading-bar"></div>
                <div class="loading-lines">
                  <div class="loading-line long"></div>
                  <div class="loading-line medium"></div>
                </div>
              </div>
              <div class="loading-stage">
                <div class="loading-stage-head">
                  <span class="loading-stage-label">步骤 2 选择诊断路径</span>
                  <span class="loading-stage-state">等待结果</span>
                </div>
                <div class="loading-lines">
                  <div class="loading-line short"></div>
                  <div class="loading-line long"></div>
                </div>
              </div>
              <div class="loading-stage">
                <div class="loading-stage-head">
                  <span class="loading-stage-label">步骤 3 整理答案与证据</span>
                  <span class="loading-stage-state">准备中</span>
                </div>
                <div class="loading-lines">
                  <div class="loading-line medium"></div>
                  <div class="loading-line long"></div>
                  <div class="loading-line short"></div>
                </div>
              </div>
              <div class="loading-note">你不用选择 Route A / B / C，系统会自动完成路由并清楚标出依据边界。</div>
            </div>
          </div>
        </div>` : ""}
    </div>
  `;
  progressTimer = setTimeout(() => {
    const note = qs(".loading-note");
    const copy = qs(".loading-copy");
    if (note) {
      note.textContent = "当前响应稍慢，通常是因为系统正在检索文档证据或相似案例。";
    }
    if (copy) {
      copy.textContent = "系统正在识别问题、选择路径，并整理回答与证据，可能需要 10-30 秒。";
    }
  }, 3000);
}

function renderError(message) {
  clearTimeout(progressTimer);
  const conversation = getActiveConversation();
  const turns = conversation?.turns || [];
  const thread = turns.map((turn, index) => renderTurn(turn, index === turns.length - 1)).join("");
  qs("#threadView").innerHTML = `
    <div class="chat-thread">
      ${thread}
      ${state.lastSubmittedQuery ? `
        <div class="turn-group">
          <div class="message-row user">
            <div class="user-bubble">${escapeHtml(state.lastSubmittedQuery)}</div>
          </div>
        </div>` : ""}
      <div class="message-row assistant">
        <div class="error-card">
          <div class="error-header">
            <div class="error-title">这次没有顺利生成回答</div>
            <div class="error-copy">我们可以直接重试当前问题，或者换一种更具体的问法，比如补充报警代码、工位、现象或已做过的动作。</div>
          </div>
          <div class="error-actions">
            <button id="retryQuestion" class="primary-btn" type="button">重新发送当前问题</button>
            <button id="useExampleFallback" class="ghost-btn" type="button">换一个示例问题</button>
          </div>
          <div class="error-reason">错误信息：${escapeHtml(message)}</div>
        </div>
      </div>
    </div>
  `;
  bindThreadActions();
}

function renderConversations() {
  const host = qs("#conversationList");
  if (!state.conversations.length) {
    host.innerHTML = `<div class="empty-state">暂无历史对话</div>`;
    return;
  }

  host.innerHTML = state.conversations.map((conversation) => {
    const active = conversation.conversation_id === state.activeConversationId ? " active" : "";
    const count = (conversation.turns || []).length;
    return `
      <div class="conversation-item${active}" data-id="${escapeHtml(conversation.conversation_id)}">
        <button class="conversation-main" type="button">
          <span class="conversation-title">${escapeHtml(conversation.title)}</span>
          <span class="conversation-meta">${count} 轮对话</span>
        </button>
        <div class="conversation-actions">
          <button class="icon-action-btn rename" type="button" title="重命名">✎</button>
          <button class="icon-action-btn delete" type="button" title="删除">🗑</button>
        </div>
      </div>
    `;
  }).join("");

  qsa(".conversation-item").forEach((item) => {
    item.querySelector(".conversation-main").addEventListener("click", () => selectConversation(item.dataset.id));
    item.querySelector(".rename").addEventListener("click", (event) => {
      event.stopPropagation();
      openRename(item.dataset.id);
    });
    item.querySelector(".delete").addEventListener("click", (event) => {
      event.stopPropagation();
      deleteConversation(item.dataset.id);
    });
  });
}

function selectConversation(conversationId) {
  state.activeConversationId = conversationId;
  resetFeedbackDraft();
  renderConversations();
  renderActiveConversation();
}

function openRename(conversationId) {
  state.renameTarget = conversationId;
  const conversation = state.conversations.find((item) => item.conversation_id === conversationId);
  qs("#renameInput").value = conversation?.title || "";
  qs("#renameDialog").showModal();
}

async function confirmRename() {
  const title = qs("#renameInput").value.trim();
  if (!state.renameTarget || !title) return;
  await apiPost("/api/conversations/rename", { conversation_id: state.renameTarget, title });
  state.renameTarget = null;
  qs("#renameDialog").close();
  await loadConversations();
  renderActiveConversation();
  toast("已重命名对话");
}

async function deleteConversation(conversationId) {
  await apiDelete(`/api/conversations?id=${encodeURIComponent(conversationId)}`);
  if (state.activeConversationId === conversationId) {
    state.activeConversationId = null;
  }
  resetFeedbackDraft();
  await loadConversations();
  if (!state.activeConversationId) {
    await createConversation("新的现场诊断对话");
  } else {
    renderActiveConversation();
    toast("已删除对话");
  }
}

function bindThreadActions() {
  qsa(".example-card").forEach((card) => {
    card.addEventListener("click", () => {
      qs("#questionInput").value = card.dataset.question || "";
      qs("#questionInput").focus();
    });
  });

  qsa(".feedback-rating-btn").forEach((button) => {
    button.addEventListener("click", () => {
      state.rating = button.dataset.rating || "";
      state.feedbackExpanded = true;
      renderActiveConversation();
    });
  });

  const toggleFeedback = qs("#toggleFeedbackDetails");
  if (toggleFeedback) {
    toggleFeedback.addEventListener("click", () => {
      state.feedbackExpanded = !state.feedbackExpanded;
      renderActiveConversation();
    });
  }

  qsa(".feedback-tag-input").forEach((input) => {
    input.addEventListener("change", (event) => {
      const value = event.target.value;
      const next = new Set(state.feedbackDraft.tags);
      if (event.target.checked) next.add(value);
      else next.delete(value);
      state.feedbackDraft.tags = [...next];
    });
  });

  const correctAnswer = qs("#feedbackCorrectAnswer");
  if (correctAnswer) {
    correctAnswer.addEventListener("input", (event) => {
      state.feedbackDraft.correctAnswer = event.target.value;
      state.feedbackExpanded = true;
    });
  }

  const freeText = qs("#feedbackFreeText");
  if (freeText) {
    freeText.addEventListener("input", (event) => {
      state.feedbackDraft.freeText = event.target.value;
      state.feedbackExpanded = true;
    });
  }

  const submit = qs("#submitFeedback");
  if (submit) {
    submit.addEventListener("click", submitFeedback);
  }

  const retry = qs("#retryQuestion");
  if (retry) {
    retry.addEventListener("click", () => {
      if (state.lastSubmittedQuery) {
        qs("#questionInput").value = state.lastSubmittedQuery;
        sendQuestion();
      }
    });
  }

  const useExample = qs("#useExampleFallback");
  if (useExample) {
    useExample.addEventListener("click", () => {
      renderEmptyState();
      qs("#questionInput").focus();
    });
  }
}

function setBusy(isBusy) {
  clearTimeout(progressTimer);
  qs("#sendQuestion").disabled = isBusy;
  qs("#sendQuestion").textContent = isBusy ? "生成中…" : "发送";
  if (isBusy) {
    renderLoadingState();
  }
}

function resetFeedbackDraft() {
  state.rating = "";
  state.feedbackExpanded = false;
  state.feedbackDraft = {
    tags: [],
    correctAnswer: "",
    freeText: "",
  };
}

function turnToEnvelope(turn) {
  return {
    answer: turn.answer,
    meta: {
      answer_id: turn.answer_id,
      query_id: turn.query_id,
      prompt_version: "answer_assembly_v1",
      kg_or_index_version: "route_abc_smoke_v1",
    },
    warnings: turn.warnings || [],
  };
}

async function apiGet(path) {
  return parseResponse(await fetch(path));
}

async function apiPost(path, payload) {
  return parseResponse(await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }));
}

async function apiDelete(path) {
  return parseResponse(await fetch(path, { method: "DELETE" }));
}

async function parseResponse(response) {
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function toast(message) {
  const box = qs("#toast");
  box.textContent = message;
  box.classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => box.classList.remove("visible"), 2400);
}

function qs(selector) {
  return document.querySelector(selector);
}

function qsa(selector) {
  return Array.from(document.querySelectorAll(selector));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
