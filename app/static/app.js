const el = (id) => document.getElementById(id);

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// 轻量 Markdown 渲染(Agent 处置方案输出是 md 文本,不引外部库):
// 支持 # 标题 / **粗体** / *斜体* / - 列表 / 1. 步骤 / 【】高亮 / 缩进层级
function mdRender(md) {
  var lines = String(md || "").split(/\r?\n/);
  var html = [];
  lines.forEach(function (raw) {
    var line = raw.replace(/\s+$/, "");
    if (!line.trim()) { html.push('<div class="md-gap"></div>'); return; }
    var indent = Math.min(2, Math.floor((raw.match(/^\s*/) || [""])[0].length / 3));
    var pad = indent * 18;
    var t = escapeHtml(line.trim());
    t = t.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    t = t.replace(/\*([^*\s][^*]*)\*/g, "<i>$1</i>");
    t = t.replace(/【([^】]*)】/g, '<span class="md-flag">$1</span>');
    var m;
    if ((m = t.match(/^#{1,6}\s+(.+)$/))) {
      html.push('<div class="md-h" style="padding-left:' + pad + 'px">' + m[1] + "</div>");
    } else if ((m = t.match(/^[-•]\s+(.+)$/))) {
      html.push('<div class="md-li" style="padding-left:' + (pad + 14) + 'px">• ' + m[1] + "</div>");
    } else if ((m = t.match(/^(\d{1,2})[.、)]\s+(.+)$/))) {
      html.push('<div class="md-step" style="padding-left:' + pad + 'px"><span class="md-no">' + m[1] + "</span>" + m[2] + "</div>");
    } else {
      html.push('<div class="md-p" style="padding-left:' + pad + 'px">' + t + "</div>");
    }
  });
  return html.join("");
}

let mode = "upload";
let stream = null;
let liveRunning = false;
let liveLoopToken = 0;
let busy = false;
let filterSource = "";
let filterLabel = "";
let filterWorkOrder = "";
let filterBatchId = "";
let filterStatus = "";
let knownLabels = {};
let currentDetailId = null;
let selected = new Set();
let lastDetections = [];
let lastFrameSize = null;
let liveStats = { fps: 0, lastMs: 0, frames: 0, windowAt: 0 };
let histLimit = 50;
let histLoaded = 0;
let histMore = false;

function toast(msg, type) {
  type = type || "ok";
  const node = el("toast");
  if (!node) return;
  node.textContent = msg;
  node.className = "toast show " + (type === "err" ? "err" : "ok");
  clearTimeout(toast._t);
  toast._t = setTimeout(function () {
    node.classList.remove("show");
  }, 2200);
}

function errText(j) {
  if (!j) return "unknown";
  if (typeof j.detail === "string") return j.detail;
  if (Array.isArray(j.detail)) {
    return j.detail.map(function (x) { return x.msg || JSON.stringify(x); }).join("; ");
  }
  return JSON.stringify(j);
}

function sleep(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

function containRect(cw, ch, vw, vh) {
  if (!cw || !ch || !vw || !vh) return { x: 0, y: 0, w: cw || 0, h: ch || 0, scale: 1 };
  const scale = Math.min(cw / vw, ch / vh);
  const w = vw * scale;
  const h = vh * scale;
  return { x: (cw - w) / 2, y: (ch - h) / 2, w: w, h: h, scale: scale };
}

function fitOverlayToVideo() {
  const video = el("camVideo");
  const canvas = el("overlayCanvas");
  if (!video || !canvas) return { cw: 0, ch: 0, vw: 0, vh: 0 };
  const rect = video.getBoundingClientRect();
  const cw = Math.max(1, Math.round(rect.width));
  const ch = Math.max(1, Math.round(rect.height));
  if (canvas.width !== cw || canvas.height !== ch) {
    canvas.width = cw;
    canvas.height = ch;
  }
  return { cw: cw, ch: ch, vw: video.videoWidth || 0, vh: video.videoHeight || 0 };
}

function clearOverlay() {
  const c = el("overlayCanvas");
  if (!c) return;
  c.getContext("2d").clearRect(0, 0, c.width, c.height);
}

function drawOverlay(detections, srcW, srcH) {
  const canvas = el("overlayCanvas");
  if (!canvas) return;
  const fit = fitOverlayToVideo();
  const cw = fit.cw, ch = fit.ch, vw = fit.vw, vh = fit.vh;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, cw, ch);
  if (!detections || !detections.length) return;

  const contentW = vw || srcW;
  const contentH = vh || srcH;
  if (!contentW || !contentH) return;

  let sx = 1, sy = 1;
  if (srcW && srcH && vw && vh && (srcW !== vw || srcH !== vh)) {
    sx = vw / srcW;
    sy = vh / srcH;
  }

  const layout = containRect(cw, ch, contentW, contentH);
  ctx.lineWidth = 2;
  ctx.font = "12px Segoe UI, sans-serif";

  for (let i = 0; i < detections.length; i++) {
    const d = detections[i];
    let x1 = d.bbox_xyxy[0] * sx;
    let y1 = d.bbox_xyxy[1] * sy;
    let x2 = d.bbox_xyxy[2] * sx;
    let y2 = d.bbox_xyxy[3] * sy;
    const rx = layout.x + x1 * layout.scale;
    const ry = layout.y + y1 * layout.scale;
    const rw = (x2 - x1) * layout.scale;
    const rh = (y2 - y1) * layout.scale;
    ctx.strokeStyle = "#38bdf8";
    ctx.fillStyle = "rgba(56,189,248,0.16)";
    ctx.fillRect(rx, ry, rw, rh);
    ctx.strokeRect(rx, ry, rw, rh);
    const tag = d.label + " " + Math.round(d.confidence * 100) + "%";
    const tw = ctx.measureText(tag).width + 10;
    const ty = Math.max(0, ry - 18);
    ctx.fillStyle = "rgba(15,23,42,0.85)";
    ctx.fillRect(rx, ty, tw, 18);
    ctx.fillStyle = "#86efac";
    ctx.fillText(tag, rx + 5, ty + 13);
  }

  if (liveRunning) {
    const hud = "LIVE  " + liveStats.fps.toFixed(1) + " fps  " + liveStats.lastMs + " ms";
    ctx.fillStyle = "rgba(15,23,42,0.75)";
    ctx.fillRect(10, 10, ctx.measureText(hud).width + 16, 22);
    ctx.fillStyle = "#fde68a";
    ctx.fillText(hud, 18, 25);
  }
}

function setMode(next) {
  mode = next;
  el("modeUpload").classList.toggle("active", mode === "upload");
  el("modeCamera").classList.toggle("active", mode === "camera");
  el("uploadPanel").classList.toggle("hidden", mode !== "upload");
  el("camPanel").classList.toggle("hidden", mode !== "camera");
  el("btnDetect").classList.toggle("hidden", mode !== "upload");
  if (mode === "camera") el("stageWrap").classList.add("cam-on");
  else {
    el("stageWrap").classList.remove("cam-on");
    stopCamera(); // 切回上传模式直接关摄像头流,不再亮灯占用设备
  }
  syncPlaceholders();
}

function syncPlaceholders() {
  const camOn = el("camBox") && el("camBox").classList.contains("active");
  if (el("camPlaceholder")) el("camPlaceholder").style.display = camOn ? "none" : "grid";
  const preview = el("preview");
  const hasPreview = preview && preview.style.display === "block" && !!preview.src;
  if (el("resultPlaceholder")) el("resultPlaceholder").style.display = hasPreview ? "none" : "grid";
}

function setCamUi(on) {
  if (el("camBox")) el("camBox").classList.toggle("active", on);
  if (el("btnCamStart")) el("btnCamStart").disabled = on;
  if (el("btnCamStop")) el("btnCamStop").disabled = !on;
  if (el("btnSnap")) el("btnSnap").disabled = !on;
  if (el("btnLive")) el("btnLive").disabled = !on;
  if (el("liveDot")) el("liveDot").classList.toggle("on", on);
  if (el("camState")) el("camState").textContent = on ? "摄像头已开启" : "摄像头未开启";
  if (on && el("stageWrap")) el("stageWrap").classList.add("cam-on");
  syncPlaceholders();
  if (on) requestAnimationFrame(function () { fitOverlayToVideo(); });
}

async function startCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    toast("浏览器不支持摄像头，请用 Chrome/Edge 打开 http://127.0.0.1:8787/", "err");
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "user",
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 30, max: 30 }
      },
      audio: false
    });
    const video = el("camVideo");
    video.srcObject = stream;
    await video.play().catch(function () {});
    if (!video.videoWidth) {
      await new Promise(function (res) {
        video.onloadedmetadata = function () { res(); };
        setTimeout(res, 800);
      });
    }
    setCamUi(true);
    fitOverlayToVideo();
    toast("摄像头已开启");
  } catch (e) {
    toast("无法打开摄像头：" + e.message, "err");
  }
}

function stopCamera() {
  stopLive();
  if (stream) {
    stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null;
  }
  if (el("camVideo")) el("camVideo").srcObject = null;
  clearOverlay();
  setCamUi(false);
}

function stopLive() {
  liveRunning = false;
  liveLoopToken += 1;
  if (el("btnLive")) {
    el("btnLive").textContent = "实时检测";
    el("btnLive").classList.remove("btn-danger");
    el("btnLive").classList.add("btn-secondary");
  }
}

async function liveLoop(token, save) {
  while (liveRunning && token === liveLoopToken) {
    if (!el("camBox") || !el("camBox").classList.contains("active")) break;
    const t0 = performance.now();
    try {
      await runDetect("camera", {
        save: !!save,
        realtime: true,
        skipResultImage: true
      });
    } catch (e) {
      await sleep(250);
    }
    const dt = performance.now() - t0;
    liveStats.lastMs = Math.round(dt);
    liveStats.frames += 1;
    const now = performance.now();
    if (!liveStats.windowAt) liveStats.windowAt = now;
    if (now - liveStats.windowAt >= 1000) {
      liveStats.fps = (liveStats.frames * 1000) / (now - liveStats.windowAt);
      liveStats.frames = 0;
      liveStats.windowAt = now;
    }
    await sleep(20);
  }
}

function startLive() {
  if (liveRunning) return;
  if (!el("camBox") || !el("camBox").classList.contains("active")) {
    toast("请先开启摄像头", "err");
    return;
  }
  liveRunning = true;
  liveLoopToken += 1;
  const token = liveLoopToken;
  liveStats = { fps: 0, lastMs: 0, frames: 0, windowAt: performance.now() };
  el("btnLive").textContent = "停止实时";
  el("btnLive").classList.remove("btn-secondary");
  el("btnLive").classList.add("btn-danger");
  const saveLive = el("liveSave") && el("liveSave").checked;
  toast(saveLive ? "实时检测已开（写历史，较慢）" : "实时检测已开（仅叠加框）");
  liveLoop(token, saveLive);
}

async function grabFrame(maxSide) {
  const video = el("camVideo");
  if (!video.videoWidth) throw new Error("视频未就绪，请稍等");
  const canvas = el("camCanvas");
  const limit = maxSide || 640;
  let w = video.videoWidth;
  let h = video.videoHeight;
  const longSide = Math.max(w, h);
  if (longSide > limit) {
    const s = limit / longSide;
    w = Math.round(w * s);
    h = Math.round(h * s);
  }
  canvas.width = w;
  canvas.height = h;
  canvas.getContext("2d").drawImage(video, 0, 0, w, h);
  const quality = liveRunning ? 0.7 : 0.85;
  const blob = await new Promise(function (resolve, reject) {
    canvas.toBlob(function (b) {
      if (b) resolve(b);
      else reject(new Error("抓帧失败"));
    }, "image/jpeg", quality);
  });
  return { blob: blob, w: w, h: h, vw: video.videoWidth, vh: video.videoHeight };
}

async function detectBlob(blob, source, save) {
  const fd = new FormData();
  fd.append("file", blob, source === "camera" ? "camera.jpg" : "upload.jpg");
  const note = (el("note") && el("note").value || "").trim();
  if (note) fd.append("note", note);
  const workOrder = (el("workOrder") && el("workOrder").value || "").trim();
  if (workOrder) fd.append("work_order", workOrder);
  const batchId = (el("batchId") && el("batchId").value || "").trim();
  if (batchId) fd.append("batch_id", batchId);
  const wantAnnotated = !(liveRunning && source === "camera");
  fd.append("return_annotated", wantAnnotated ? "true" : "false");
  fd.append("save", save ? "true" : "false");
  fd.append("source", source);
  fd.append("conf", el("conf") ? el("conf").value : "0.4");
  const r = await fetch("/detect/image", { method: "POST", body: fd });
  const j = await r.json().catch(function () { return {}; });
  if (!r.ok) throw new Error(errText(j));
  return j;
}

function showChips(dets, targetId) {
  const box = el(targetId || "labelChips");
  if (!box) return;
  box.innerHTML = "";
  if (!dets || !dets.length) return;
  const map = {};
  for (let i = 0; i < dets.length; i++) {
    const lab = dets[i].label;
    map[lab] = (map[lab] || 0) + 1;
  }
  Object.keys(map).forEach(function (k) {
    const s = document.createElement("span");
    s.className = "chip";
    s.textContent = k + " x" + map[k];
    box.appendChild(s);
  });
}

function showDetectResult(j, frameSize, opts) {
  opts = opts || {};
  lastDetections = j.detections || [];
  lastFrameSize = frameSize;
  const idPart = j.id != null ? ("记录 #" + j.id + " · ") : (liveRunning ? "实时 · " : "未落库 · ");
  const fpsPart = liveRunning ? (" · " + liveStats.fps.toFixed(1) + " fps") : "";
  if (el("lastResult")) {
    el("lastResult").innerHTML =
      idPart + "<b>" + j.num_detections + "</b> 个目标 · <b>" + (j.elapsed_ms != null ? j.elapsed_ms : "?") + "ms</b>" +
      fpsPart + " · conf=" + (j.conf_used != null ? j.conf_used : "-") + " · " + j.model;
  }
  showChips(lastDetections, "labelChips");

  if (!opts.skipResultImage && j.annotated_base64) {
    const img = el("preview");
    if (img) {
      img.style.display = "block";
      img.src = "data:image/jpeg;base64," + j.annotated_base64;
    }
  }

  if (mode === "camera" && el("camBox") && el("camBox").classList.contains("active") && frameSize) {
    drawOverlay(lastDetections, frameSize.w, frameSize.h);
  }
  syncPlaceholders();
}

async function runDetect(source, opts) {
  opts = opts || {};
  const save = opts.save === true;
  const realtime = opts.realtime === true;
  if (busy) return;
  busy = true;
  if (!realtime && el("status")) el("status").textContent = "检测中…";
  try {
    let j;
    let frameSize = null;
    if (source === "camera") {
      const grabbed = await grabFrame(realtime || liveRunning ? 512 : 960);
      frameSize = { w: grabbed.w, h: grabbed.h, vw: grabbed.vw, vh: grabbed.vh };
      j = await detectBlob(grabbed.blob, "camera", save);
    } else {
      const f = el("file") && el("file").files && el("file").files[0];
      if (!f) {
        toast("请先选择图片", "err");
        return;
      }
      j = await detectBlob(f, "upload", true);
    }
    showDetectResult(j, frameSize, opts);
    if (save && j.id != null) {
      await refreshRecords();
      await refreshStats();
      if (!realtime) toast("已保存记录 #" + j.id);
    }
  } catch (e) {
    if (!realtime) {
      if (el("lastResult")) el("lastResult").textContent = "失败: " + e.message;
      toast(e.message, "err");
    }
    throw e;
  } finally {
    busy = false;
    if (!realtime && el("status")) el("status").textContent = "";
  }
}

function updateSelCount() {
  const n = selected.size;
  if (el("selCount")) el("selCount").textContent = n ? ("已选 " + n) : "";
  if (el("btnBatchDelete")) el("btnBatchDelete").disabled = n === 0;
}

async function deleteOne(id) {
  const r = await fetch("/records/" + id, { method: "DELETE" });
  const j = await r.json().catch(function () { return {}; });
  if (!r.ok) throw new Error(errText(j) || "删除失败");
  selected.delete(id);
  if (currentDetailId === id) {
    currentDetailId = null;
    closeDetailModal();
  }
  toast("已删除 #" + id);
}

async function refreshHealth() {
  try {
    const j = await (await fetch("/health")).json();
    if (el("healthBadge")) {
      el("healthBadge").textContent = j.model_loaded
        ? ("OK · " + j.model + " · " + j.device)
        : "服务正常 · 模型待加载";
    }
    if (el("kpiModel")) el("kpiModel").textContent = j.model_loaded ? "READY" : "LOADING";
    if (el("kpiDevice")) el("kpiDevice").textContent = j.model + " / " + j.device;
  } catch (e) {
    if (el("healthBadge")) el("healthBadge").textContent = "服务不可用";
    if (el("kpiModel")) el("kpiModel").textContent = "DOWN";
  }
}

async function refreshStats() {
  try {
    const j = await (await fetch("/stats")).json();
    knownLabels = j.by_label || {};
    renderLabelFilters();
    if (el("kpiRecords")) el("kpiRecords").textContent = j.total_records;
    if (el("kpiBoxes")) el("kpiBoxes").textContent = j.total_detections;
    const src = Object.entries(j.by_source || {}).map(function (kv) { return kv[0] + ":" + kv[1]; }).join(" · ");
    const labs = Object.entries(j.by_label || {}).slice(0, 4).map(function (kv) { return kv[0] + ":" + kv[1]; }).join(" · ");
    if (el("kpiSource")) el("kpiSource").textContent = labs || "-";
    if (el("kpiRecordsFoot")) {
      el("kpiRecordsFoot").textContent =
        (src || "no source") +
        (j.avg_elapsed_ms != null ? (" · avg " + j.avg_elapsed_ms + "ms") : "") +
        (j.alert_records != null ? (" · alert " + j.alert_records) : "");
    }
  } catch (e) {
    if (el("kpiRecords")) el("kpiRecords").textContent = "-";
  }
}

function renderLabelFilters() {
  const bar = el("labelFilterBar");
  if (!bar) return;
  bar.innerHTML = "";
  const all = document.createElement("button");
  all.type = "button";
  all.className = "chip filter chip-filter-all" + (filterLabel ? "" : " active");
  all.textContent = "全部类别";
  all.onclick = function () {
    filterLabel = "";
    renderLabelFilters();
    refreshRecords();
  };
  bar.appendChild(all);
  const entries = Object.entries(knownLabels || {}).slice(0, 12);
  entries.forEach(function (kv) {
    const lab = kv[0];
    const cnt = kv[1];
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip filter" + (filterLabel === lab ? " active" : "");
    b.textContent = lab + " x" + cnt;
    b.onclick = function () {
      filterLabel = filterLabel === lab ? "" : lab;
      renderLabelFilters();
      refreshRecords();
    };
    bar.appendChild(b);
  });
}

function buildRecordQuery(extra) {
  const q = new URLSearchParams(extra || {});
  if (filterSource) q.set("source", filterSource);
  if (filterLabel) q.set("label", filterLabel);
  if (filterWorkOrder) q.set("work_order", filterWorkOrder);
  if (filterBatchId) q.set("batch_id", filterBatchId);
  if (filterStatus) q.set("status", filterStatus);
  return q;
}

// 单行构建(字段统一转义,用户输入不裸拼 innerHTML)
function buildRecordRow(row) {
  const tr = document.createElement("tr");
  tr.dataset.id = String(row.id);
  if (row.id === currentDetailId) tr.classList.add("active");
  if (selected.has(row.id)) tr.classList.add("selected");

  const checked = selected.has(row.id) ? "checked" : "";
  const thumb = row.image_path
    ? '<img class="thumb" src="/files/' + encodeURIComponent(String(row.image_path).replace(/^\/+/, "")) + '" alt="" loading="lazy" />'
    : '<div class="thumb ph"></div>';
  const timeShort = escapeHtml(String(row.created_at || "").replace("T", " ").slice(5, 19));
  const top = escapeHtml(row.top_label || "-");
  const ms = row.elapsed_ms != null ? (Math.round(row.elapsed_ms) + "ms") : "-";
  const st = row.status
    ? ('<div class="status-pill ' + (row.status === "alert" ? "alert" : "clear") + '">' + escapeHtml(row.status) + "</div>")
    : "";

  tr.innerHTML =
    '<td><input type="checkbox" ' + checked + ' data-sel="' + row.id + '" /></td>' +
    "<td>" + thumb + "</td>" +
    "<td><div>" + row.id + "</div>" + st + "</td>" +
    '<td title="' + escapeHtml(row.created_at || "") + '">' + timeShort + "</td>" +
    '<td><span class="pill">' + escapeHtml(row.source) + "</span></td>" +
    '<td title="' + escapeHtml(row.work_order || "-") + '">' + escapeHtml(row.work_order || "-") + "</td>" +
    '<td title="' + escapeHtml(row.batch_id || "-") + '">' + escapeHtml(row.batch_id || "-") + "</td>" +
    "<td>" + row.num_detections + "</td>" +
    "<td>" + top + "</td>" +
    "<td>" + ms + "</td>" +
    '<td class="ops">' +
    '<button type="button" class="btn btn-secondary btn-xs" data-view="' + row.id + '">查看</button>' +
    '<button type="button" class="btn btn-danger btn-xs" data-del="' + row.id + '">删除</button>' +
    "</td>";

  const sel = tr.querySelector('[data-sel="' + row.id + '"]');
  if (sel) {
    sel.onclick = function (e) {
      e.stopPropagation();
      if (e.target.checked) selected.add(row.id);
      else selected.delete(row.id);
      tr.classList.toggle("selected", e.target.checked);
      updateSelCount();
    };
  }
  const viewBtn = tr.querySelector('[data-view="' + row.id + '"]');
  if (viewBtn) {
    viewBtn.onclick = function (e) {
      e.stopPropagation();
      showDetail(row.id);
    };
  }
  const delBtn = tr.querySelector('[data-del="' + row.id + '"]');
  if (delBtn) {
    delBtn.onclick = async function (e) {
      e.stopPropagation();
      if (!confirm("删除记录 #" + row.id + "？")) return;
      try {
        await deleteOne(row.id);
        await refreshRecords();
        await refreshStats();
        updateSelCount();
      } catch (err) {
        toast(err.message, "err");
      }
    };
  }
  tr.onclick = function () { showDetail(row.id); };
  return tr;
}

// append=false 重置到第一页;append=true 追加下一页
async function refreshRecords(append) {
  append = append === true;
  if (!append) histLoaded = 0;
  const q = buildRecordQuery({ limit: String(histLimit), offset: String(histLoaded) });
  const rows = await (await fetch("/records?" + q.toString())).json();
  const tb = el("tbody");
  if (!tb) return;
  if (!append) tb.innerHTML = "";
  rows.forEach(function (row) { tb.appendChild(buildRecordRow(row)); });
  histLoaded += rows.length;
  histMore = rows.length >= histLimit;
  if (el("emptyRecords")) el("emptyRecords").classList.toggle("hidden", histLoaded > 0);
  if (el("btnLoadMore")) el("btnLoadMore").classList.toggle("hidden", !histMore);
  if (el("histCount")) {
    el("histCount").textContent = histLoaded
      ? ("已加载 " + histLoaded + " 条" + (histMore ? " · 点击加载更多" : ""))
      : "";
  }
  updateSelCount();
}

function closeDetailModal() {
  const m = el("detailModal");
  if (m) m.classList.remove("show");
}

async function showDetail(id) {
  try {
    const r = await fetch("/records/" + id);
    if (!r.ok) {
      toast("加载详情失败", "err");
      return;
    }
    const j = await r.json();
    currentDetailId = j.id;

    document.querySelectorAll("#tbody tr").forEach(function (tr) {
      tr.classList.toggle("active", Number(tr.dataset.id) === j.id);
    });

    if (!el("detailModal")) {
      toast("详情弹窗缺失，请强刷页面", "err");
      return;
    }

    el("modalId").textContent = j.id;
    el("modalSub").innerHTML =
      (j.status
        ? ('<span class="status-pill ' + (j.status === "alert" ? "alert" : "clear") + '">' + escapeHtml(j.status) + "</span> ")
        : "") +
      escapeHtml(j.created_at || "") + " · " + escapeHtml(j.source || "");

    const size = j.image_width && j.image_height ? (j.image_width + " × " + j.image_height) : "-";
    const labels = j.labels || {};
    const labelText = Object.keys(labels).length
      ? Object.keys(labels).map(function (k) { return escapeHtml(k) + " x" + labels[k]; }).join(" · ")
      : "-";

    el("modalKv").innerHTML =
      "<span>模型</span><b>" + escapeHtml(j.model || "-") + "</b>" +
      "<span>检出数</span><b>" + j.num_detections + "</b>" +
      "<span>主类别</span><b>" + escapeHtml(j.top_label || "-") + "</b>" +
      "<span>类别分布</span><b>" + labelText + "</b>" +
      "<span>置信度</span><b>avg " + (j.avg_confidence != null ? j.avg_confidence : "-") +
      " / max " + (j.max_confidence != null ? j.max_confidence : "-") + "</b>" +
      "<span>阈值</span><b>" + (j.conf_used != null ? j.conf_used : "-") + "</b>" +
      "<span>耗时</span><b>" + (j.elapsed_ms != null ? (Math.round(j.elapsed_ms) + " ms") : "-") + "</b>" +
      "<span>分辨率</span><b>" + size + "</b>" +
      "<span>工单号</span><b>" + escapeHtml(j.work_order || "-") + "</b>" +
      "<span>批次号</span><b>" + escapeHtml(j.batch_id || "-") + "</b>" +
      "<span>备注</span><b>" + escapeHtml(j.note || "-") + "</b>";

    const chips = el("modalChips");
    if (chips) {
      chips.innerHTML = "";
      Object.keys(labels).forEach(function (k) {
        const s = document.createElement("span");
        s.className = "chip";
        s.textContent = k + " x" + labels[k];
        chips.appendChild(s);
      });
    }

    const body = el("modalDetBody");
    if (body) {
      body.innerHTML = "";
      (j.detections || []).forEach(function (d, i) {
        const tr = document.createElement("tr");
        const bbox = (d.bbox_xyxy || []).map(function (v) { return Number(v).toFixed(1); }).join(", ");
        tr.innerHTML =
          "<td>" + (i + 1) + "</td>" +
          "<td>" + escapeHtml(d.label) + "</td>" +
          "<td>" + (Number(d.confidence) * 100).toFixed(1) + "%</td>" +
          "<td>[" + bbox + "]</td>";
        body.appendChild(tr);
      });
    }

    if (el("modalJson")) el("modalJson").textContent = JSON.stringify(j.detections || [], null, 2);

    const img = el("modalImg");
    if (img) {
      if (j.image_path) {
        img.style.display = "block";
        img.src = "/files/" + String(j.image_path).replace(/^\/+/, "") + "?t=" + Date.now();
      } else {
        img.removeAttribute("src");
        img.style.display = "none";
      }
    }

    // 重置处置方案区(每次打开新记录清空上次的 Agent 结果)
    if (el("modalDisposeWrap")) el("modalDisposeWrap").style.display = "none";
    if (el("modalDisposeBody")) el("modalDisposeBody").textContent = "";
    if (el("modalDisposeRisk")) el("modalDisposeRisk").innerHTML = "";
    if (el("modalDisposeStatus")) el("modalDisposeStatus").textContent = "";

    el("detailModal").classList.add("show");
  } catch (e) {
    toast("打开详情失败: " + e.message, "err");
  }
}

function bindUi() {
  if (el("conf")) {
    el("conf").oninput = function () {
      if (el("confVal")) el("confVal").textContent = Number(el("conf").value).toFixed(2);
    };
  }
  if (el("modeUpload")) el("modeUpload").onclick = function () { setMode("upload"); };
  if (el("modeCamera")) el("modeCamera").onclick = function () { setMode("camera"); };
  if (el("btnCamStart")) el("btnCamStart").onclick = startCamera;
  if (el("btnCamStop")) el("btnCamStop").onclick = stopCamera;
  if (el("btnSnap")) el("btnSnap").onclick = function () { runDetect("camera", { save: true }); };
  if (el("btnLive")) {
    el("btnLive").onclick = function () {
      if (liveRunning) {
        stopLive();
        toast("已停止实时检测");
        return;
      }
      startLive();
    };
  }
  if (el("btnDetect")) el("btnDetect").onclick = function () { runDetect("upload", { save: true }); };
  if (el("btnRefresh")) {
    el("btnRefresh").onclick = async function () {
      await Promise.all([refreshRecords(), refreshStats(), refreshHealth()]);
      toast("已刷新");
    };
  }
  if (el("btnReloadHist")) el("btnReloadHist").onclick = function () { refreshRecords(); };

  function applyMetaFilters() {
    filterWorkOrder = (el("filterWorkOrder") && el("filterWorkOrder").value || "").trim();
    filterBatchId = (el("filterBatchId") && el("filterBatchId").value || "").trim();
    refreshRecords();
  }
  if (el("btnApplyFilter")) el("btnApplyFilter").onclick = applyMetaFilters;
  if (el("btnAlertOnly")) {
    el("btnAlertOnly").onclick = function () {
      filterStatus = filterStatus === "alert" ? "" : "alert";
      el("btnAlertOnly").classList.toggle("active", filterStatus === "alert");
      refreshRecords();
    };
  }
  if (el("btnLoadMore")) {
    el("btnLoadMore").onclick = async function () {
      el("btnLoadMore").disabled = true;
      try { await refreshRecords(true); } finally { el("btnLoadMore").disabled = false; }
    };
  }
  if (el("btnClearFilter")) {
    el("btnClearFilter").onclick = function () {
      if (el("filterWorkOrder")) el("filterWorkOrder").value = "";
      if (el("filterBatchId")) el("filterBatchId").value = "";
      filterWorkOrder = "";
      filterBatchId = "";
      filterLabel = "";
      filterSource = "";
      filterStatus = "";
      // 复位来源按钮与告警开关的高亮态
      document.querySelectorAll("[data-filter]").forEach(function (b) {
        b.classList.toggle("active", !b.getAttribute("data-filter"));
      });
      if (el("btnAlertOnly")) el("btnAlertOnly").classList.remove("active");
      renderLabelFilters();
      refreshRecords();
    };
  }
  ["filterWorkOrder", "filterBatchId"].forEach(function (id) {
    if (!el(id)) return;
    el(id).addEventListener("keydown", function (e) {
      if (e.key === "Enter") applyMetaFilters();
    });
  });
  if (el("btnExportCsv")) {
    el("btnExportCsv").onclick = function () {
      const q = buildRecordQuery({ limit: "1000" });
      window.open("/records/export.csv?" + q.toString(), "_blank");
    };
  }

  document.querySelectorAll("[data-filter]").forEach(function (btn) {
    btn.onclick = function () {
      document.querySelectorAll("[data-filter]").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      filterSource = btn.getAttribute("data-filter") || "";
      selected.clear();
      updateSelCount();
      refreshRecords();
    };
  });

  document.querySelectorAll(".nav [data-page]").forEach(function (btn) {
    btn.onclick = function () {
      document.querySelectorAll(".nav [data-page]").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      const page = btn.getAttribute("data-page");
      const showDetect = page === "detect" || page === "history";
      if (el("pageDetect")) el("pageDetect").classList.toggle("hidden", !showDetect);
      if (el("pageAbout")) el("pageAbout").classList.toggle("hidden", page !== "about");
      if (el("pageTitle")) {
        el("pageTitle").textContent =
          page === "about" ? "说明" : page === "history" ? "历史记录" : "检测工作台";
      }
      if (page === "history" && el("historyCard")) {
        el("historyCard").scrollIntoView({ behavior: "smooth", block: "start" });
      }
    };
  });

  if (el("btnBatchDelete")) {
    el("btnBatchDelete").onclick = async function () {
      const ids = Array.from(selected);
      if (!ids.length) return;
      if (!confirm("确定删除选中的 " + ids.length + " 条记录？")) return;
      try {
        const r = await fetch("/records/delete-batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: ids })
        });
        const j = await r.json().catch(function () { return {}; });
        if (!r.ok) throw new Error(errText(j) || "批量删除失败");
        if (ids.indexOf(currentDetailId) >= 0) {
          currentDetailId = null;
          closeDetailModal();
        }
        selected.clear();
        updateSelCount();
        await refreshRecords();
        await refreshStats();
        toast("已删除 " + (j.deleted != null ? j.deleted : ids.length) + " 条");
      } catch (e) {
        toast(e.message, "err");
      }
    };
  }

  if (el("btnClearAll")) {
    el("btnClearAll").onclick = async function () {
      if (!confirm("清空全部历史记录？此操作不可恢复。")) return;
      if (!confirm("再次确认：真的清空全部吗？")) return;
      try {
        const r = await fetch("/records?confirm=YES", { method: "DELETE" });
        const j = await r.json().catch(function () { return {}; });
        if (!r.ok) throw new Error(errText(j) || "清空失败");
        selected.clear();
        currentDetailId = null;
        closeDetailModal();
        updateSelCount();
        await refreshRecords();
        await refreshStats();
        toast("已清空 " + (j.deleted != null ? j.deleted : 0) + " 条");
      } catch (e) {
        toast(e.message, "err");
      }
    };
  }

  if (el("checkAll")) {
    el("checkAll").onchange = function (e) {
      const rows = Array.from(document.querySelectorAll("#tbody tr[data-id]"));
      rows.forEach(function (tr) {
        const id = Number(tr.dataset.id);
        const cb = tr.querySelector('input[type="checkbox"]');
        if (e.target.checked) selected.add(id);
        else selected.delete(id);
        if (cb) cb.checked = e.target.checked;
        tr.classList.toggle("selected", e.target.checked);
      });
      updateSelCount();
    };
  }

  // === rag_agent 处置方案接入(最小侵入,新增逻辑不动既有代码)===
  async function loadDispose(rid) {
    var wrap = el("modalDisposeWrap");
    var status = el("modalDisposeStatus");
    var riskBox = el("modalDisposeRisk");
    var body = el("modalDisposeBody");
    if (!wrap) return;
    wrap.style.display = "block";
    status.textContent = "Agent 编排中(查 SOP + 查历史,约 10-20 秒)…";
    riskBox.innerHTML = "";
    body.textContent = "";
    try {
      var j = await fetch("/agent/dispose?record_id=" + rid + "&use_agent=true").then(function (r) { return r.json(); });
      if (j.detail) { status.textContent = "失败"; body.textContent = String(j.detail); return; }
      status.textContent = "缺陷: " + (j.top_label || "-") + " · 状态: " + (j.status || "-");
      if (j.found === false) {
        body.textContent = j.dispose || "未找到处置方案";
        return;
      }
      // 高危动作确认按钮
      if (j.needs_confirmation && Array.isArray(j.high_risk_actions) && j.high_risk_actions.length) {
        riskBox.innerHTML = j.high_risk_actions.map(function (a) {
          return '<div style="display:flex;align-items:center;gap:6px;padding:6px 8px;background:#fff7ed;border:1px solid #fed7aa;border-radius:6px;margin-bottom:4px">' +
            '<span style="color:#92400e;font-size:12px">⚠ ' + a + '</span>' +
            '<button type="button" class="btn btn-secondary btn-xs" data-cf="' + a + '" data-ok="1">批准</button>' +
            '<button type="button" class="btn btn-secondary btn-xs" data-cf="' + a + '" data-ok="0">拒绝</button>' +
            '<span data-cfret="' + a + '" style="font-size:11px;color:#9ca3af"></span></div>';
        }).join("");
        riskBox.querySelectorAll("[data-cf]").forEach(function (btn) {
          btn.onclick = async function () {
            var ret = riskBox.querySelector('[data-cfret="' + btn.dataset.cf + '"]');
            ret.textContent = "提交中…";
            try {
              await fetch("/agent/dispose/confirm", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ record_id: rid, action: btn.dataset.cf, approved: btn.dataset.ok === "1", operator: "看板" })
              });
              ret.innerHTML = btn.dataset.ok === "1" ? '<span style="color:#166534">✓ 已批准</span>' : '<span style="color:#b91c1c">✗ 已拒绝</span>';
            } catch (e) { ret.textContent = "失败"; }
          };
        });
      } else {
        riskBox.innerHTML = '<span style="color:#166534;font-size:12px">✓ 无高危动作,可按方案处置</span>';
      }
      body.innerHTML = mdRender(j.dispose || "");
    } catch (e) {
      status.textContent = "请求失败";
      body.textContent = String(e);
    }
  }
  if (el("modalDispose")) {
    el("modalDispose").onclick = function () {
      if (currentDetailId == null) { toast("无当前记录", "err"); return; }
      loadDispose(currentDetailId);
    };
  }

  if (el("modalClose")) el("modalClose").onclick = closeDetailModal;
  if (el("detailModal")) {
    el("detailModal").onclick = function (e) {
      if (e.target.id === "detailModal") closeDetailModal();
    };
  }
  if (el("modalDelete")) {
    el("modalDelete").onclick = async function () {
      if (currentDetailId == null) return;
      if (!confirm("确定删除记录 #" + currentDetailId + "？")) return;
      try {
        await deleteOne(currentDetailId);
        closeDetailModal();
        await refreshRecords();
        await refreshStats();
        updateSelCount();
      } catch (err) {
        toast(err.message, "err");
      }
    };
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDetailModal();
  });

  window.addEventListener("beforeunload", stopCamera);
  window.addEventListener("resize", function () {
    if (el("camBox") && el("camBox").classList.contains("active")) {
      fitOverlayToVideo();
      if (lastDetections.length && lastFrameSize) {
        drawOverlay(lastDetections, lastFrameSize.w, lastFrameSize.h);
      }
    }
  });
}

function boot() {
  try {
    bindUi();
    setMode("upload");
    refreshHealth();
    refreshStats();
    refreshRecords();
  } catch (e) {
    console.error(e);
    toast("页面初始化失败: " + e.message, "err");
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
