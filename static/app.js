const REQUEST_TIMEOUT_MS = 240000;
const ESTIMATED_INTAKE_SECONDS = 28;
const ESTIMATED_INTAKE_RANGE = "预计 20 到 30 秒";
const FONT_STORAGE_KEY = "silvercare-font-size";
const INTAKE_PROGRESS_STEPS = [
  "正在连接本地分诊模型",
  "正在提取症状关键词和危险信号",
  "正在判断建议科室与紧急程度",
  "正在识别当前位置所属城市",
  "正在调用高德地理编码与路线规划",
  "正在筛选同城医院并计算综合评分",
  "正在整理老人易读版推荐结果",
];
const ICONS = {
  timer: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="13" r="7"></circle>
      <path d="M12 9v4l2.8 1.8"></path>
      <path d="M9.5 3h5"></path>
      <path d="M12 3v3"></path>
    </svg>
  `,
  session: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="5" width="16" height="14" rx="3"></rect>
      <path d="M8 10h8"></path>
      <path d="M8 14h5"></path>
    </svg>
  `,
  department: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14"></path>
      <path d="M7 10h10"></path>
      <circle cx="12" cy="12" r="8"></circle>
    </svg>
  `,
  warning: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4 20 19H4Z"></path>
      <path d="M12 9v4"></path>
      <circle cx="12" cy="16.8" r="0.8" fill="currentColor" stroke="none"></circle>
    </svg>
  `,
  hospital: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 20V6.5A1.5 1.5 0 0 1 7.5 5h9A1.5 1.5 0 0 1 18 6.5V20"></path>
      <path d="M10 8h4"></path>
      <path d="M12 6v4"></path>
      <path d="M9 13h2"></path>
      <path d="M13 13h2"></path>
      <path d="M9 17h2"></path>
      <path d="M13 17h2"></path>
    </svg>
  `,
  route: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="7" cy="17" r="2"></circle>
      <circle cx="17" cy="7" r="2"></circle>
      <path d="M8.5 15.5 15.5 8.5"></path>
      <path d="M13 8h3v3"></path>
    </svg>
  `,
  link: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10 14 8 16a3 3 0 0 1-4-4l2-2a3 3 0 0 1 4 0"></path>
      <path d="M14 10 16 8a3 3 0 1 1 4 4l-2 2a3 3 0 0 1-4 0"></path>
      <path d="M9 15 15 9"></path>
    </svg>
  `,
  next: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h12"></path>
      <path d="M13 8l4 4-4 4"></path>
    </svg>
  `,
  location: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 20s-5-4.8-5-9a5 5 0 1 1 10 0c0 4.2-5 9-5 9Z"></path>
      <circle cx="12" cy="11" r="1.8"></circle>
    </svg>
  `,
  score: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4 14.5 9 20 9.7l-4 3.8.9 5.5-4.9-2.6-4.9 2.6.9-5.5-4-3.8 5.5-.7Z"></path>
    </svg>
  `,
  advice: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4a6 6 0 0 1 3.8 10.7c-.9.7-1.3 1.4-1.3 2.3h-5c0-.9-.4-1.6-1.3-2.3A6 6 0 0 1 12 4Z"></path>
      <path d="M10 20h4"></path>
      <path d="M9.5 17.5h5"></path>
    </svg>
  `,
  image: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="5" width="16" height="14" rx="3"></rect>
      <circle cx="9" cy="10" r="1.6"></circle>
      <path d="m20 16-4.5-4.5L8 19"></path>
    </svg>
  `,
};

let intakeResultCollapsed = false;
let bookingResultCollapsed = false;
let latestIntakeSummary = null;
let latestBookingSummary = null;
let latestBookingCandidates = [];

function escapeHtml(value) {
  const safeValue = value === null || value === undefined ? "" : String(value);
  return safeValue
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function parseResponse(response) {
  const raw = await response.text();
  return raw ? JSON.parse(raw) : {};
}

async function postJson(url, payload) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(function () {
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const data = await parseResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || "请求失败");
    }
    return data;
  } catch (error) {
    if (error && error.name === "AbortError") {
      throw new Error("请求超时，请确认本地服务已启动后重试。");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function postForm(url, formData) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(function () {
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    const data = await parseResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || "请求失败");
    }
    return data;
  } catch (error) {
    if (error && error.name === "AbortError") {
      throw new Error("上传超时，请确认图片大小合适后重试。");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function setText(id, text) {
  const el = document.getElementById(id);
  el.classList.remove("muted");
  el.classList.remove("loading");
  el.textContent = text;
}

function setHtml(id, html) {
  const el = document.getElementById(id);
  el.classList.remove("muted");
  el.classList.remove("loading");
  el.innerHTML = html;
}

function setPending(form, pendingText) {
  const button = form.querySelector('button[type="submit"]');
  if (!button) {
    return function () {};
  }

  const defaultText = button.dataset.defaultText || button.textContent;
  button.dataset.defaultText = defaultText;
  button.textContent = pendingText;
  button.disabled = true;
  form.dataset.pending = "true";

  return function () {
    button.textContent = defaultText;
    button.disabled = false;
    form.dataset.pending = "false";
  };
}

function setLoadingMessage(id, text) {
  const el = document.getElementById(id);
  el.classList.remove("muted");
  el.classList.add("loading");
  el.textContent = text;
}

function renderIconLabel(iconName, label, tone) {
  const safeTone = tone || "";
  return [
    '<span class="info-label ' + safeTone + '">',
    '<span class="info-icon" aria-hidden="true">' + (ICONS[iconName] || "") + "</span>",
    "<span>" + escapeHtml(label) + "</span>",
    "</span>",
  ].join("");
}

function renderSummaryRow(iconName, label, valueHtml, options) {
  const opts = options || {};
  const toneClass = opts.tone ? "summary-row-" + opts.tone : "";
  return [
    '<div class="summary-row ' + toneClass + '">',
    '<div class="summary-label-wrap">' + renderIconLabel(iconName, label, opts.tone || "") + "</div>",
    '<div class="summary-value">' + valueHtml + "</div>",
    "</div>",
  ].join("");
}

function renderSummaryHighlight(iconName, label, value, tone) {
  const toneClass = tone ? "summary-highlight-" + tone : "";
  return [
    '<div class="summary-highlight ' + toneClass + '">',
    renderIconLabel(iconName, label, tone || ""),
    '<div class="summary-highlight-value"><strong>' + escapeHtml(value) + "</strong></div>",
    "</div>",
  ].join("");
}

function renderHospitalLink(url) {
  if (!url) {
    return "暂未配置官网入口";
  }

  const isSearchLink = /baidu\.com\/s\?/i.test(url);
  const label = isSearchLink ? "在浏览器搜索医院官网" : "打开医院官网";
  return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noreferrer">' + label + "</a>";
}

function renderRouteStepList(steps, toneClass, fallbackText) {
  const safeToneClass = toneClass || "";
  const routeSteps = steps && steps.length ? steps : [fallbackText || "路线正在整理中。"];
  return routeSteps
    .map(function (step) {
      return '<li class="route-step-item ' + safeToneClass + '"><span class="route-step-icon">' + ICONS.route + "</span><span><strong>" + escapeHtml(step) + "</strong></span></li>";
    })
    .join("");
}

function renderLocationStepList(steps) {
  const routeSteps = steps && steps.length ? steps : ["请到导医台确认具体位置。"];
  return routeSteps
    .map(function (step) {
      return '<li class="route-step-item route-step-item-soft"><span class="route-step-icon">' + ICONS.location + "</span><span><strong>" + escapeHtml(step) + "</strong></span></li>";
    })
    .join("");
}

function renderCollapsedSummary(summary) {
  if (!summary) {
    return "展开后可查看完整推荐结果。";
  }

  return [
    '<span class="collapsed-summary-chip"><strong>建议科室：</strong>' + escapeHtml(summary.department) + "</span>",
    '<span class="collapsed-summary-chip"><strong>首推医院：</strong>' + escapeHtml(summary.hospitalName) + "</span>",
    '<span class="collapsed-summary-chip"><strong>路线：</strong>' + escapeHtml(summary.route) + "</span>",
  ].join("");
}

function renderBookingCollapsedSummary(summary) {
  if (!summary) {
    return "展开后可查看完整挂号结果。";
  }

  return [
    '<span class="collapsed-summary-chip"><strong>医院：</strong>' + escapeHtml(summary.hospitalName) + "</span>",
    '<span class="collapsed-summary-chip"><strong>时间：</strong>' + escapeHtml(summary.scheduledAt) + "</span>",
    '<span class="collapsed-summary-chip"><strong>地点：</strong>' + escapeHtml(summary.location) + "</span>",
  ].join("");
}

function getCollapseElements(kind) {
  return {
    buttons: document.querySelectorAll('[data-collapse-target="' + kind + '"]'),
    wrap: document.getElementById(kind + "-result-wrap"),
    summary: document.getElementById(kind + "-result-summary"),
  };
}

function getIntakeCollapseElements() {
  return getCollapseElements("intake");
}

function getBookingCollapseElements() {
  return getCollapseElements("booking");
}

function syncCollapseButtons(buttons, collapsed, expandLabel, collapseLabel) {
  buttons.forEach(function (button) {
    button.textContent = collapsed ? expandLabel : collapseLabel;
    button.setAttribute("aria-expanded", collapsed ? "false" : "true");
  });
}

function syncResultWrap(elements, collapsed) {
  elements.wrap.classList.toggle("collapsed", collapsed);
  elements.summary.classList.toggle("visible", collapsed);
}

function syncIntakeResultCollapse() {
  const elements = getIntakeCollapseElements();
  if (!elements.wrap || !elements.summary || !elements.buttons.length) {
    return;
  }

  syncCollapseButtons(elements.buttons, intakeResultCollapsed, "展开详细结果", "收起详细结果");
  syncResultWrap(elements, intakeResultCollapsed);
  elements.summary.classList.toggle("muted", !latestIntakeSummary);
  elements.summary.innerHTML = renderCollapsedSummary(latestIntakeSummary);
}

function syncBookingResultCollapse() {
  const elements = getBookingCollapseElements();
  if (!elements.wrap || !elements.summary || !elements.buttons.length) {
    return;
  }

  syncCollapseButtons(elements.buttons, bookingResultCollapsed, "展开挂号结果", "收起挂号结果");
  syncResultWrap(elements, bookingResultCollapsed);
  elements.summary.classList.toggle("muted", !latestBookingSummary);
  elements.summary.innerHTML = renderBookingCollapsedSummary(latestBookingSummary);
}

function setBookingResultCollapsed(nextCollapsed) {
  bookingResultCollapsed = Boolean(nextCollapsed);
  syncBookingResultCollapse();
}

function setIntakeResultCollapsed(nextCollapsed) {
  intakeResultCollapsed = Boolean(nextCollapsed);
  syncIntakeResultCollapse();
}

function updateLatestBookingSummary(data) {
  if (!data || !data.appointment) {
    latestBookingSummary = null;
  } else {
    latestBookingSummary = {
      hospitalName: data.appointment.hospital_name,
      scheduledAt: data.appointment.scheduled_at,
      location: data.appointment.location,
    };
  }
  syncBookingResultCollapse();
}

function scrollToModule(targetId) {
  const target = document.getElementById(targetId);
  if (!target) {
    return;
  }
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

function initQuickNav() {
  document.querySelectorAll("[data-scroll-target]").forEach(function (button) {
    button.addEventListener("click", function () {
      scrollToModule(button.dataset.scrollTarget);
    });
  });
}

function renderProgressHtml(steps, activeIndex, elapsedSeconds) {
  let elapsedText = "已开始推荐，" + ESTIMATED_INTAKE_RANGE + " 完成。";
  let countdownText = "系统已经开始整理结果，请稍候。";
  if (elapsedSeconds > 0 && elapsedSeconds < ESTIMATED_INTAKE_SECONDS) {
    elapsedText = "已开始推荐，已等待 " + elapsedSeconds + " 秒，预计还需 " + (ESTIMATED_INTAKE_SECONDS - elapsedSeconds) + " 秒左右。";
    countdownText = "已经思考 " + elapsedSeconds + " 秒";
  } else if (elapsedSeconds >= ESTIMATED_INTAKE_SECONDS) {
    elapsedText = "已开始推荐，已等待 " + elapsedSeconds + " 秒，正在输出最终结果。";
    countdownText = "已经思考 " + elapsedSeconds + " 秒";
  }

  const items = steps
    .map(function (step, index) {
      let stateClass = "progress-pending";
      let stateIcon = "○";
      if (index < activeIndex) {
        stateClass = "progress-done";
        stateIcon = "✓";
      } else if (index === activeIndex) {
        stateClass = "progress-active";
        stateIcon = "…";
      }
      return '<div class="progress-item ' + stateClass + '"><span class="progress-icon">' + stateIcon + "</span><span>" + escapeHtml(step) + "</span></div>";
    })
    .join("");

  return [
    '<div class="progress-card">',
    '<div class="progress-banner">',
    '<div class="progress-badge">' + ICONS.timer + "<span>已开始推荐</span></div>",
    '<div class="progress-counter">',
    '<div class="progress-counter-label">当前状态</div>',
    '<div class="progress-counter-value">' + escapeHtml(countdownText) + "</div>",
    '<div class="progress-counter-tip">' + escapeHtml(elapsedText) + "</div>",
    "</div>",
    "</div>",
    '<div class="progress-subtitle">系统正在思考并整理推荐，生成完成后会自动替换成最终结果。</div>',
    '<div class="progress-list">' + items + "</div>",
    "</div>",
  ].join("");
}

function startIntakeProgress(id) {
  const startedAt = Date.now();
  let activeIndex = 0;
  let timerId = null;

  function render() {
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
    setHtml(id, renderProgressHtml(INTAKE_PROGRESS_STEPS, activeIndex, elapsedSeconds));
  }

  render();
  timerId = window.setInterval(function () {
    if (activeIndex < INTAKE_PROGRESS_STEPS.length - 1) {
      activeIndex += 1;
    }
    render();
  }, 3500);

  return function () {
    if (timerId !== null) {
      window.clearInterval(timerId);
    }
  };
}

function setSelectedHospital(hospitalId, hospitalName) {
  const input = document.querySelector('#booking-form input[name="hospital_id"]');
  const hint = document.getElementById("booking-selection-tip");
  if (!input || !hint) {
    return;
  }

  input.value = hospitalId || "";
  hint.textContent = hospitalId
    ? "已选择：" + hospitalName + "，第 2 步会按这家医院生成挂号与导航。"
    : "上一步选择候选医院后，这里会自动填入医院 ID。";
  syncBookingCandidateSelection();
}

function renderCandidateCard(candidate, index) {
  const reasons = (candidate.reasons || [])
    .map(function (reason) {
      return "<li><strong>" + escapeHtml(reason) + "</strong></li>";
    })
    .join("");
  const officialLink = renderHospitalLink(candidate.booking_url);
  const actionLabel = index === 0 ? "已作为默认挂号医院" : "用这家医院去挂号";
  const actionDisabled = index === 0 ? "disabled" : "";
  const scoreBreakdown = candidate.score_breakdown || {};
  const scoreValue = Number(scoreBreakdown.final_score || 0).toFixed(1);
  const candidateLevel = candidate.hospital_level ? escapeHtml(candidate.hospital_level) : "未定级";
  const routeStepList = renderRouteStepList(
    candidate.route_steps,
    "route-step-item-compact",
    candidate.route || "路线信息待补充。"
  );

  return [
    '<article class="candidate-card ' + (index === 0 ? "candidate-primary" : "") + '">',
    '<div class="candidate-topline"><div class="candidate-rank">候选 ' + (index + 1) + '</div><div class="candidate-score">' + renderIconLabel("score", "综合评分") + "<strong>" + escapeHtml(scoreValue) + "</strong></div></div>",
    "<h3>" + renderIconLabel("hospital", "医院") + "<strong>" + escapeHtml(candidate.hospital_name) + '</strong><span class="candidate-level-tag">评级：' + candidateLevel + "</span></h3>",
    '<div class="candidate-meta-row">' + renderIconLabel("location", "地址") + '<div class="candidate-meta-text"><strong>' + escapeHtml(candidate.address) + "</strong></div></div>",
    '<div class="candidate-meta-row">' + renderIconLabel("route", "路线总览") + '<div class="candidate-meta-text"><strong>' + escapeHtml(candidate.route) + "</strong></div></div>",
    '<div class="candidate-meta-row">' + renderIconLabel("route", "到院路线") + '<div class="candidate-meta-text"><ul class="route-step-list route-step-list-compact">' + routeStepList + "</ul></div></div>",
    '<ul class="candidate-reasons">' + reasons + "</ul>",
    '<div class="candidate-actions">',
    '<span class="candidate-link">' + renderIconLabel("link", "官网入口") + officialLink + "</span>",
    '<button type="button" class="ghost-button" data-hospital-id="' + escapeHtml(candidate.hospital_id) + '" data-hospital-name="' + escapeHtml(candidate.hospital_name) + '" ' + actionDisabled + ">" + actionLabel + "</button>",
    "</div>",
    "</article>",
  ].join("");
}

function renderBookingCandidateOption(candidate, index) {
  const level = candidate.hospital_level ? escapeHtml(candidate.hospital_level) : "未定级";
  const scoreBreakdown = candidate.score_breakdown || {};
  const travelMinutes = scoreBreakdown.travel_minutes ? escapeHtml(scoreBreakdown.travel_minutes) + " 分钟" : "时间待确认";

  return [
    '<button type="button" class="booking-candidate-option" data-hospital-id="' + escapeHtml(candidate.hospital_id) + '" data-hospital-name="' + escapeHtml(candidate.hospital_name) + '">',
    '<span class="booking-candidate-rank">候选 ' + (index + 1) + "</span>",
    '<span class="booking-candidate-name"><strong>' + escapeHtml(candidate.hospital_name) + "</strong></span>",
    '<span class="booking-candidate-tags">',
    '<span class="booking-candidate-tag booking-candidate-tag-level">评级：' + level + "</span>",
    '<span class="booking-candidate-tag booking-candidate-tag-time">' + travelMinutes + "</span>",
    "</span>",
    "</button>",
  ].join("");
}

function renderIntakeResult(data) {
  const candidates = data.candidates || [];
  const candidateCards = candidates.map(function (candidate, index) {
    return renderCandidateCard(candidate, index);
  }).join("");
  const warningText = (data.triage.warnings || []).join("；") || "无";
  const urgencyLabel = data.triage.urgency === "urgent" ? "尽快就医" : data.triage.urgency === "soon" ? "建议尽快" : "常规就诊";
  const officialLink = renderHospitalLink(data.recommended_hospital.booking_url);
  const recommendedRouteStepList = renderRouteStepList(
    data.recommended_hospital.route_steps,
    "",
    data.recommended_hospital.route || "路线信息待补充。"
  );

  return [
    '<div class="result-stack">',
    '<section class="summary-card">',
    '<div class="summary-header">',
    '<div class="summary-title">本次推荐结果</div>',
    '<div class="summary-subtitle">已经完成分诊和附近医院筛选，重要信息已加粗展示。</div>',
    "</div>",
    '<div class="summary-highlights">',
    renderSummaryHighlight("department", "建议科室", data.triage.department, "safe"),
    renderSummaryHighlight("warning", "风险等级", urgencyLabel, data.triage.urgency === "urgent" ? "warning" : "safe"),
    renderSummaryHighlight("hospital", "首推医院", data.recommended_hospital.hospital_name, "primary"),
    "</div>",
    renderSummaryRow("session", "会话 ID", "<strong>" + escapeHtml(data.session_id) + "</strong>"),
    renderSummaryRow("advice", "分诊提示", "<strong>" + escapeHtml(data.triage.advice) + "</strong>", { tone: "safe" }),
    renderSummaryRow("warning", "安全提醒", "<strong>" + escapeHtml(warningText) + "</strong>", { tone: "warning" }),
    renderSummaryRow("route", "路线总览", "<strong>" + escapeHtml(data.recommended_hospital.route) + "</strong>"),
    '<div class="result-card-row">' + renderIconLabel("route", "详细到院路线", "primary") + '<div class="result-card-value"><ul class="route-step-list">' + recommendedRouteStepList + "</ul></div></div>",
    renderSummaryRow("link", "官网入口", officialLink),
    renderSummaryRow("next", "下一步", "<strong>" + escapeHtml(data.suggested_next_action) + "</strong>", { tone: "primary" }),
    "</section>",
    '<section class="candidate-section">',
    '<div class="candidate-header">',
    '<div class="candidate-title">附近真实医院候选</div>',
    '<div class="candidate-subtitle">当前展示更适合您的前 ' + escapeHtml(candidates.length) + ' 家候选医院，可直接选择用于第 2 步挂号。</div>',
    "</div>",
    '<div class="candidate-list">' + candidateCards + "</div>",
    "</section>",
    "</div>",
  ].join("");
}

function renderBookingCandidateList(candidates) {
  if (!candidates || !candidates.length) {
    return "生成推荐后，这里会显示可点击的候选医院。";
  }

  return candidates.map(function (candidate, index) {
    return renderBookingCandidateOption(candidate, index);
  }).join("");
}

function syncBookingCandidateSelection() {
  const selectedInput = document.querySelector('#booking-form input[name="hospital_id"]');
  const list = document.getElementById("booking-candidate-list");
  if (!selectedInput || !list) {
    return;
  }

  const selectedId = selectedInput.value;
  list.querySelectorAll("[data-hospital-id]").forEach(function (button) {
    button.classList.toggle("selected", button.dataset.hospitalId === selectedId);
  });
}

function updateLatestIntakeSummary(data) {
  if (!data || !data.recommended_hospital || !data.triage) {
    latestIntakeSummary = null;
  } else {
    latestIntakeSummary = {
      department: data.triage.department,
      hospitalName: data.recommended_hospital.hospital_name,
      route: data.recommended_hospital.route,
    };
  }
  syncIntakeResultCollapse();
}

function updateBookingCandidates(candidates) {
  latestBookingCandidates = candidates || [];
  const list = document.getElementById("booking-candidate-list");
  if (!list) {
    return;
  }

  list.classList.remove("muted");
  list.innerHTML = renderBookingCandidateList(latestBookingCandidates);
  syncBookingCandidateSelection();
}

function renderBookingResult(data) {
  const navigationSteps = data.navigation && data.navigation.steps ? data.navigation.steps : [];
  const routeSteps = data.appointment && data.appointment.route_steps ? data.appointment.route_steps : [];
  const routeStepList = renderRouteStepList(routeSteps, "", data.appointment.route);
  const navigationStepList = renderLocationStepList(navigationSteps);
  return [
    '<div class="booking-result-card">',
    '<div class="result-card-header">',
    '<div class="result-card-title">挂号与到院提醒</div>',
    '<div class="result-card-subtitle">已经整理好时间、候诊位置和到院步骤，方便老人和家属一起查看。</div>',
    "</div>",
    renderSummaryRow("hospital", "医院", "<strong>" + escapeHtml(data.appointment.hospital_name) + "</strong>", { tone: "primary" }),
    renderSummaryRow("department", "科室", "<strong>" + escapeHtml(data.appointment.department) + "</strong>"),
    renderSummaryRow("timer", "挂号时间", "<strong>" + escapeHtml(data.appointment.scheduled_at) + "</strong>", { tone: "safe" }),
    renderSummaryRow("location", "候诊地点", "<strong>" + escapeHtml(data.appointment.location) + "</strong>"),
    renderSummaryRow("route", "路线总览", "<strong>" + escapeHtml(data.appointment.route) + "</strong>"),
    renderSummaryRow("link", "官网入口", renderHospitalLink(data.appointment.booking_url)),
    renderSummaryRow("next", "签到提醒", "<strong>" + escapeHtml(data.appointment.check_in_before) + "</strong>", { tone: "warning" }),
    '<div class="result-card-row">' + renderIconLabel("route", "到院路线", "primary") + '<div class="result-card-value"><ul class="route-step-list">' + routeStepList + "</ul></div></div>",
    '<div class="result-card-row">' + renderIconLabel("advice", "到院后怎么走", "safe") + '<div class="result-card-value"><ul class="route-step-list route-step-list-soft">' + navigationStepList + "</ul></div></div>",
    "</div>",
  ].join("");
}

function renderDocumentResult(data) {
  const keyPoints = data.archived_document.key_points || [];
  const instructions = data.care_instructions.instructions || [];
  const imageLink = data.archived_document.source_image_url
    ? '<a class="document-image-link" href="' + escapeHtml(data.archived_document.source_image_url) + '" target="_blank" rel="noreferrer">' + ICONS.image + "<span>查看已上传图片</span></a>"
    : "";
  const noteLink = data.archived_document.note_file_url
    ? '<a class="document-image-link" href="' + escapeHtml(data.archived_document.note_file_url) + '" target="_blank" rel="noreferrer">' + ICONS.session + "<span>查看文字说明文件</span></a>"
    : "";

  return [
    '<div class="document-result-card">',
    '<div class="result-card-header">',
    '<div class="result-card-title">检查资料已整理</div>',
    '<div class="result-card-subtitle">系统已经把文档类型、重点内容和后续提醒整理好了。</div>',
    "</div>",
    data.archived_document.source_filename
      ? '<div class="document-source-chip">' + ICONS.image + "<span>已上传图片：" + escapeHtml(data.archived_document.source_filename) + "</span></div>"
      : "",
    '<div class="document-source-chip">' + ICONS.warning + "<span>分类：" + escapeHtml(data.archived_document.issue_status || "有问题") + "</span></div>",
    imageLink,
    noteLink,
    renderSummaryRow("image", "文档类型", "<strong>" + escapeHtml(data.archived_document.doc_type) + "</strong>", { tone: "primary" }),
    renderSummaryRow("advice", "摘要", "<strong>" + escapeHtml(data.archived_document.summary) + "</strong>", { tone: "safe" }),
    renderSummaryRow("location", "保存目录", "<strong>" + escapeHtml(data.archived_document.storage_directory || "暂未生成目录") + "</strong>"),
    '<div class="result-card-row">' + renderIconLabel("session", "关键内容", "primary") + '<div class="result-card-value"><strong>' + escapeHtml(keyPoints.join("；")) + "</strong></div></div>",
    '<div class="result-card-row">' + renderIconLabel("next", "后续提醒", "warning") + '<div class="result-card-value"><strong>' + escapeHtml(instructions.join("；")) + "</strong></div></div>",
    renderSummaryRow("timer", "复诊建议", "<strong>" + escapeHtml(data.care_instructions.follow_up_window || "按医生建议") + "</strong>", { tone: "warning" }),
    "</div>",
  ].join("");
}

function updateDocumentImagePreview() {
  const input = document.querySelector('#document-form input[name="document_image"]');
  const preview = document.getElementById("document-image-preview");
  if (!input || !preview) {
    return;
  }

  const file = input.files && input.files[0];
  if (!file) {
    preview.classList.remove("ready");
    preview.classList.add("muted");
    preview.innerHTML = "还没有选择图片。";
    return;
  }

  const reader = new FileReader();
  reader.onload = function (event) {
    preview.classList.add("ready");
    preview.classList.remove("muted");
    preview.innerHTML = [
      '<div class="image-preview-name">已选择图片：' + escapeHtml(file.name) + "</div>",
      '<img src="' + escapeHtml(event.target.result) + '" alt="检查图片预览" />',
    ].join("");
  };
  reader.readAsDataURL(file);
}

function syncIssueToggle() {
  document.querySelectorAll(".issue-option").forEach(function (label) {
    const input = label.querySelector('input[type="radio"]');
    label.classList.toggle("active", Boolean(input && input.checked));
  });
}

function initIssueToggle() {
  document.querySelectorAll('input[name="issue_status"]').forEach(function (input) {
    input.addEventListener("change", syncIssueToggle);
  });
  syncIssueToggle();
}

function applyFontSize(size) {
  const safeSize = size === "small" || size === "large" ? size : "medium";
  document.body.classList.remove("font-small", "font-medium", "font-large");
  document.body.classList.add("font-" + safeSize);

  document.querySelectorAll(".font-size-button").forEach(function (button) {
    button.classList.toggle("is-active", button.dataset.fontSize === safeSize);
  });
  window.localStorage.setItem(FONT_STORAGE_KEY, safeSize);
}

function initFontControls() {
  const saved = window.localStorage.getItem(FONT_STORAGE_KEY) || "medium";
  applyFontSize(saved);
  document.querySelectorAll(".font-size-button").forEach(function (button) {
    button.addEventListener("click", function () {
      applyFontSize(button.dataset.fontSize);
    });
  });
}

document.getElementById("intake-result").addEventListener("click", function (event) {
  const button = event.target.closest("[data-hospital-id]");
  if (!button || button.disabled) {
    return;
  }
  setSelectedHospital(button.dataset.hospitalId, button.dataset.hospitalName);
});

document.getElementById("booking-candidate-list").addEventListener("click", function (event) {
  const button = event.target.closest("[data-hospital-id]");
  if (!button || button.disabled) {
    return;
  }
  setSelectedHospital(button.dataset.hospitalId, button.dataset.hospitalName);
});

document.getElementById("intake-form").addEventListener("submit", async function (event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (form.dataset.pending === "true") {
    return;
  }

  setIntakeResultCollapsed(false);
  const restore = setPending(form, "正在生成，请稍候...");
  const stopProgress = startIntakeProgress("intake-result");

  try {
    const formData = new FormData(form);
    const payload = {
      current_location: formData.get("current_location"),
      transport_mode: formData.get("transport_mode"),
      preferred_time: formData.get("preferred_time"),
      symptom_text: formData.get("symptom_text"),
    };
    const data = await postJson("/api/intake", payload);
    stopProgress();
    setHtml("intake-result", renderIntakeResult(data));
    updateLatestIntakeSummary(data);
    updateBookingCandidates(data.candidates);

    document.querySelector('#booking-form input[name="session_id"]').value = data.session_id;
    setSelectedHospital(data.recommended_hospital.hospital_id, data.recommended_hospital.hospital_name);
    document.querySelector('#document-form input[name="session_id"]').value = data.session_id;
  } catch (error) {
    stopProgress();
    updateLatestIntakeSummary(null);
    updateBookingCandidates([]);
    setText("intake-result", error.message);
  } finally {
    stopProgress();
    restore();
  }
});

document.getElementById("booking-form").addEventListener("submit", async function (event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (form.dataset.pending === "true") {
    return;
  }

  const restore = setPending(form, "正在挂号，请稍候...");
  setBookingResultCollapsed(false);
  setLoadingMessage("booking-result", "正在生成挂号说明和到院导航。");

  try {
    const formData = new FormData(form);
    const payload = {
      session_id: formData.get("session_id"),
      hospital_id: formData.get("hospital_id") || null,
      preferred_time: formData.get("preferred_time") || null,
    };
    const data = await postJson("/api/appointments/book", payload);
    setHtml("booking-result", renderBookingResult(data));
    updateLatestBookingSummary(data);
  } catch (error) {
    updateLatestBookingSummary(null);
    setText("booking-result", error.message);
  } finally {
    restore();
  }
});

document.getElementById("document-form").addEventListener("submit", async function (event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (form.dataset.pending === "true") {
    return;
  }

  const restore = setPending(form, "正在归档，请稍候...");
  setLoadingMessage("document-result", "正在整理文档并生成注意事项。");

  try {
    const formData = new FormData(form);
    const selectedImage = formData.get("document_image");
    let data;

    if (selectedImage && selectedImage.size) {
      formData.set("uploaded_from", "image_upload");
      data = await postForm("/api/documents/archive-image", formData);
    } else {
      const payload = {
        session_id: formData.get("session_id"),
        document_title: formData.get("document_title"),
        document_text: formData.get("document_text"),
        issue_status: formData.get("issue_status"),
      };
      data = await postJson("/api/documents/archive", payload);
    }

    setHtml("document-result", renderDocumentResult(data));
  } catch (error) {
    setText("document-result", error.message);
  } finally {
    restore();
  }
});

document.querySelectorAll('[data-collapse-target="intake"]').forEach(function (button) {
  button.addEventListener("click", function () {
    setIntakeResultCollapsed(!intakeResultCollapsed);
  });
});

document.querySelectorAll('[data-collapse-target="booking"]').forEach(function (button) {
  button.addEventListener("click", function () {
    setBookingResultCollapsed(!bookingResultCollapsed);
  });
});

document.querySelector('#document-form input[name="document_image"]').addEventListener("change", function () {
  updateDocumentImagePreview();
});

initFontControls();
initIssueToggle();
initQuickNav();
syncIntakeResultCollapse();
syncBookingResultCollapse();
updateBookingCandidates([]);
updateDocumentImagePreview();
