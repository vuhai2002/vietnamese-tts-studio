// Omnivoice Tiếng Việt - điều khiển giao diện web. Gọi API backend (web_server.py).
"use strict";
const $ = (id) => document.getElementById(id);
let currentFile = null;     // File/Blob giọng mẫu vừa tải lên hoặc thu âm
let recorder = null;        // WavRecorder khi đang thu âm
let pollTimer = null;

/* ---------- Theme sáng/tối (lưu localStorage, không tải lại trang) ---------- */
function initTheme() {
  const forced = new URLSearchParams(location.search).get("theme");  // ?theme=light|dark ép tay
  const saved = localStorage.getItem("ov-theme");
  const dark = forced ? forced === "dark"
    : saved ? saved === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}
$("themeBtn").onclick = () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("ov-theme", next);
};

/* ---------- Tabs ---------- */
document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    tab.classList.add("active");
    $("view-" + tab.dataset.view).classList.add("active");
    if (tab.dataset.view === "history") loadHistory();
  };
});

/* ---------- Toast ---------- */
function toast(msg, isErr = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isErr ? " err" : "");
  el.textContent = msg;
  $("toasts").appendChild(el);
  setTimeout(() => el.remove(), 3600);
}

/* ---------- Composer phụ trợ ---------- */
$("text").addEventListener("input", (e) => {
  $("counter").textContent = `${e.target.value.length} ký tự`;
});
$("steps").addEventListener("input", (e) => { $("stepsVal").textContent = e.target.value; });

/* ---------- Giọng mẫu: dropdown + tải lên + kéo thả + thu âm ---------- */
async function loadRefs() {
  try {
    const { refs } = await (await fetch("/api/refs")).json();
    const sel = $("refSelect");
    sel.innerHTML = '<option value="">- Không dùng -</option>' +
      refs.map((r) => `<option value="${r}">${r}</option>`).join("");
  } catch { /* offline / chưa sẵn sàng - bỏ qua */ }
}
$("refreshRefs").onclick = loadRefs;

$("deleteRef").onclick = async () => {
  const name = $("refSelect").value;
  if (!name) { toast("Hãy chọn một giọng mẫu trong danh sách trước.", true); return; }
  if (!confirm(`Xóa giọng mẫu "${name}"? Không khôi phục được.`)) return;
  try {
    const r = await fetch("/api/refs/" + encodeURIComponent(name), { method: "DELETE" });
    if (!r.ok) throw new Error();
    await loadRefs();
    $("refSelect").value = "";
    toast("Đã xóa giọng mẫu: " + name);
  } catch { toast("Không xóa được giọng mẫu.", true); }
};

function setRefFile(file, label) {
  currentFile = file;
  const dz = $("dropzone");
  dz.classList.add("has-file");
  $("dzTitle").textContent = label;
  $("dzSub").textContent = "Bấm để chọn file khác";
  $("saveRef").hidden = false;
  $("clearRef").hidden = false;
  $("refSelect").value = "";  // file tải lên ưu tiên hơn dropdown
}

function clearRef() {
  currentFile = null;
  const dz = $("dropzone");
  dz.classList.remove("has-file");
  $("dzTitle").textContent = "Kéo thả file âm thanh vào đây";
  $("dzSub").textContent = "hoặc bấm để chọn file (.wav, .mp3, .flac)";
  $("saveRef").hidden = true;
  $("clearRef").hidden = true;
  $("fileInput").value = "";
}
$("clearRef").onclick = clearRef;
$("dropzone").onclick = () => $("fileInput").click();
$("fileInput").onchange = (e) => { if (e.target.files[0]) setRefFile(e.target.files[0], e.target.files[0].name); };
["dragover", "dragleave", "drop"].forEach((ev) =>
  $("dropzone").addEventListener(ev, (e) => {
    e.preventDefault();
    $("dropzone").classList.toggle("drag", ev === "dragover");
    if (ev === "drop" && e.dataTransfer.files[0]) {
      const f = e.dataTransfer.files[0];
      setRefFile(f, f.name);
    }
  }));

$("recordBtn").onclick = async () => {
  if (recorder) {
    const blob = recorder.stop();
    recorder = null;
    $("recordLabel").textContent = "Thu âm bằng micro";
    $("recordBtn").classList.remove("btn-danger");
    setRefFile(blob, "Giọng vừa thu âm (.wav)");
    return;
  }
  try {
    recorder = new WavRecorder();
    await recorder.start();
    $("recordLabel").textContent = "Dừng thu âm";
    $("recordBtn").classList.add("btn-danger");
  } catch {
    recorder = null;
    toast("Không truy cập được micro. Hãy cho phép quyền micro.", true);
  }
};

$("saveRef").onclick = async () => {
  if (!currentFile) return;
  const fd = new FormData();
  fd.append("ref_file", currentFile, currentFile.name || "ref.wav");
  $("saveRef").disabled = true;       // chặn bấm liên tục trong lúc đang lưu
  try {
    const r = await fetch("/api/save-ref", { method: "POST", body: fd });
    const data = await r.json();
    await loadRefs();
    $("refSelect").value = data.name;
    $("saveRef").hidden = true;       // đã lưu file này rồi -> không cho lưu lại
    toast("Đã lưu giọng mẫu: " + data.name);
  } catch {
    toast("Không lưu được giọng mẫu.", true);
  } finally {
    $("saveRef").disabled = false;
  }
};

/* ---------- Sinh giọng nói ---------- */
function pollProgress() {
  pollTimer = setInterval(async () => {
    try {
      const p = await (await fetch("/api/progress")).json();
      if (p.running) {
        $("progFill").style.width = Math.round(p.frac * 100) + "%";
        $("progDesc").textContent = p.desc || "Đang sinh âm thanh...";
      }
    } catch { /* bỏ qua nhịp lỗi */ }
  }, 400);
}
function stopPoll() { clearInterval(pollTimer); pollTimer = null; }

$("goBtn").onclick = async () => {
  const text = $("text").value.trim();
  if (!text) { toast("Hãy nhập văn bản cần đọc.", true); return; }

  const fd = new FormData();
  fd.append("text", text);
  fd.append("ref_text", $("refText").value);
  fd.append("steps", $("steps").value);
  fd.append("speed", $("speedSel").value);
  fd.append("use_cpu", $("useCpu").checked);
  if (currentFile) fd.append("ref_file", currentFile, currentFile.name || "ref.wav");
  else fd.append("ref_name", $("refSelect").value);

  $("goBtn").disabled = true;
  $("result").classList.remove("show");
  $("progFill").style.width = "0%";
  $("progDesc").textContent = "Đang chuẩn bị... (lần đầu phải tải model, mất 30-60 giây)";
  $("progress").classList.add("show");
  pollProgress();

  try {
    const r = await fetch("/api/generate", { method: "POST", body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "Lỗi không rõ.");
    showResult(data);
  } catch (err) {
    toast(err.message || "Sinh âm thanh thất bại.", true);
  } finally {
    stopPoll();
    $("progress").classList.remove("show");
    $("goBtn").disabled = false;
  }
};

function showResult(data) {
  const url = data.url + "?t=" + Date.now();   // tránh cache
  $("player").src = url;
  $("downloadBtn").href = url;
  $("downloadBtn").setAttribute("download", data.wav);
  $("resultName").textContent = data.wav;
  const banner = $("resultBanner");
  if (data.partial) {
    banner.hidden = false;
    banner.textContent = `Dừng ở đoạn ${data.failed_at}/${data.n_chunks} (hết VRAM?). ` +
      "Đã lưu phần hoàn thành. Thử bật 'Dùng CPU' hoặc giảm số bước rồi đọc lại.";
  } else { banner.hidden = true; }
  $("result").classList.add("show");
  $("player").play().catch(() => {});
}

$("unloadBtn").onclick = async () => {
  try {
    const data = await (await fetch("/api/unload", { method: "POST" })).json();
    toast(data.message || "Đã giải phóng VRAM.");
  } catch { toast("Không gọi được giải phóng VRAM.", true); }
};

/* ---------- Lịch sử ---------- */
async function loadHistory() {
  const list = $("histList");
  list.innerHTML = '<div class="empty">Đang tải...</div>';
  try {
    const { items } = await (await fetch("/api/history")).json();
    if (!items.length) { list.innerHTML = '<div class="empty">Chưa có file nào.</div>'; return; }
    list.innerHTML = "";
    items.forEach((m) => list.appendChild(histRow(m)));
  } catch { list.innerHTML = '<div class="empty">Không tải được lịch sử.</div>'; }
}

const ICON_PLAY = '<svg viewBox="0 0 24 24" fill="none" width="16" height="16"><path d="M8 5l11 7-11 7V5z" fill="currentColor"/></svg>';
const ICON_PAUSE = '<svg viewBox="0 0 24 24" fill="none" width="16" height="16"><path d="M7 5h3v14H7zM14 5h3v14h-3z" fill="currentColor"/></svg>';
const ICON_TRASH = '<svg viewBox="0 0 24 24" fill="none" width="16" height="16"><path d="M5 7h14M9 7V5h6v2M7 7l1 13h8l1-13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function collapseAllHistAudio(except) {
  document.querySelectorAll(".hist-item").forEach((it) => {
    const a = it.querySelector(".hist-audio");
    if (a !== except) {
      a.pause();
      a.hidden = true;
      it.classList.remove("playing");
      it.querySelector(".play").innerHTML = ICON_PLAY;
    }
  });
}

function histRow(m) {
  const time = (m.created || "").replace("T", " ");
  const text = m.text || "(không có nội dung)";
  const voice = m.ref_voice ? m.ref_voice.split(/[\\/]/).pop() : "giọng mặc định";
  const partial = m.partial ? '<span class="badge">[dở dang] </span>' : "";
  const row = document.createElement("div");
  row.className = "hist-item";
  row.innerHTML =
    `<div class="hist-main">
       <button class="play" title="Nghe / dừng">${ICON_PLAY}</button>
       <div class="info"><div class="txt">${escapeHtml(text)}</div>
         <div class="sub">${partial}${time} · ${escapeHtml(voice)}</div></div>
       <button class="del" title="Xóa">${ICON_TRASH}</button>
     </div>
     <audio class="hist-audio" controls preload="none" hidden></audio>`;

  const playBtn = row.querySelector(".play");
  const audio = row.querySelector(".hist-audio");

  // Bấm play -> phát NGAY trong dòng này (thu lại dòng khác đang phát).
  playBtn.onclick = () => {
    const willOpen = audio.hidden;
    collapseAllHistAudio(audio);
    if (willOpen) {
      if (!audio.src) audio.src = `/api/audio/${m.wav}?t=` + Date.now();
      audio.hidden = false;
      row.classList.add("playing");
      audio.play().catch(() => {});
    } else {
      audio.pause();
      audio.hidden = true;
      row.classList.remove("playing");
    }
  };
  audio.onplay = () => { playBtn.innerHTML = ICON_PAUSE; row.classList.add("playing"); };
  audio.onpause = () => { playBtn.innerHTML = ICON_PLAY; };
  audio.onended = () => { playBtn.innerHTML = ICON_PLAY; };

  row.querySelector(".del").onclick = async () => {
    try {
      await fetch("/api/history/" + encodeURIComponent(m.wav), { method: "DELETE" });
      toast("Đã xóa " + m.wav);
      loadHistory();
    } catch { toast("Không xóa được file.", true); }
  };
  return row;
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* ---------- Khởi tạo ---------- */
initTheme();
loadRefs();
if (new URLSearchParams(location.search).get("tab") === "history") {
  document.querySelector('.tab[data-view="history"]').click();
}
