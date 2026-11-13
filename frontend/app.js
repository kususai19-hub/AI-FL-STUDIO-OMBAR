/* ==========================================================================
   OMBAR FL-AI Studio  -  Frontend logic
   Sends prompts to the FastAPI backend, streams live events over WebSocket,
   renders the AI plan + execution results, and keeps a command history.
   ========================================================================== */

(function () {
  "use strict";

  // ---- DOM -------------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  const els = {
    prompt:        $("promptInput"),
    send:          $("sendBtn"),
    clear:         $("clearBtn"),
    backendUrl:    $("backendUrl"),
    planBox:       $("planBox"),
    planList:      $("planList"),
    planConf:      $("planConf"),
    logStream:     $("logStream"),
    history:       $("history"),
    wsState:       $("wsState"),
    autoscroll:    $("autoscroll"),
    statusCluster: $("statusCluster"),
    refreshStatus: $("refreshStatus"),
    toast:         $("toast"),
    chips:         Array.from(document.querySelectorAll(".chip")),
  };

  // ---- State -----------------------------------------------------------
  let backendBase = localStorage.getItem("ombar.backend") || "http://localhost:8080";
  els.backendUrl.value = backendBase;
  let ws = null;
  let history = JSON.parse(localStorage.getItem("ombar.history") || "[]");

  // ---- Utilities -------------------------------------------------------
  function toast(msg, kind) {
    els.toast.textContent = msg;
    els.toast.className = "toast" + (kind ? " " + kind : "");
    els.toast.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => (els.toast.hidden = true), 3200);
  }

  function nowTime() {
    return new Date().toLocaleTimeString("id-ID", { hour12: false });
  }

  function logLine(ev, text, kind) {
    const div = document.createElement("div");
    div.className = "line";
    div.innerHTML =
      '<span class="ts">[' + nowTime() + ']</span> ' +
      '<span class="ev ' + (kind || "") + '">' + (ev || "") + '</span> ' +
      '<span class="msg"></span>';
    div.querySelector(".msg").textContent = text;
    els.logStream.appendChild(div);
    if (els.autoscroll.checked) {
      els.logStream.scrollTop = els.logStream.scrollHeight;
    }
  }

  function setStatus(key, state) {
    const pill = els.statusCluster.querySelector(
      '.status-pill[data-key="' + key + '"]'
    );
    if (!pill) return;
    pill.classList.remove("ok", "warn", "bad");
    pill.classList.add(state);
  }

  function deriveWsUrl(httpBase) {
    // http://host:port -> ws://host:port/ws
    let url = httpBase.trim().replace(/^https:/, "wss:").replace(/^http:/, "ws:");
    if (!url.endsWith("/")) url += "/";
    return url + "ws";
  }

  // ---- Backend URL change ---------------------------------------------
  els.backendUrl.addEventListener("change", () => {
    backendBase = els.backendUrl.value.trim().replace(/\/$/, "");
    localStorage.setItem("ombar.backend", backendBase);
    toast("Backend URL disimpan: " + backendBase);
    connectWs();
    pollStatus();
  });

  // ---- Status polling --------------------------------------------------
  async function pollStatus() {
    try {
      const r = await fetch(backendBase + "/api/status", {
        method: "GET",
        headers: { "Accept": "application/json" },
      });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const data = await r.json();
      setStatus("backend", "ok");
      setStatus("mcp", data.mcp && data.mcp.reachable ? "ok" : "bad");
      setStatus("fl", data.fl_studio && data.fl_studio.connected ? "ok" : "warn");
      logLine("status",
        "backend ok | mcp " + (data.mcp.reachable ? "online" : "offline") +
        " | fl " + (data.fl_studio.connected ? "connected" : "n/a"));
    } catch (e) {
      setStatus("backend", "bad");
      setStatus("mcp", "bad");
      setStatus("fl", "bad");
      logLine("status", "backend unreachable: " + e.message, "err");
    }
  }

  els.refreshStatus.addEventListener("click", pollStatus);

  // ---- WebSocket -------------------------------------------------------
  function connectWs() {
    if (ws) {
      try { ws.close(); } catch (e) {}
      ws = null;
    }
    const url = deriveWsUrl(backendBase);
    els.wsState.textContent = "WebSocket: connecting...";
    try {
      ws = new WebSocket(url);
    } catch (e) {
      els.wsState.textContent = "WebSocket: error";
      logLine("ws", "WebSocket gagal: " + e.message, "err");
      return;
    }
    ws.onopen = function () {
      els.wsState.textContent = "WebSocket: connected";
      logLine("ws", "connected to " + url, "ok");
    };
    ws.onmessage = function (evt) {
      try {
        const msg = JSON.parse(evt.data);
        handleEvent(msg);
      } catch (e) {
        logLine("ws", evt.data);
      }
    };
    ws.onclose = function () {
      els.wsState.textContent = "WebSocket: closed";
      logLine("ws", "disconnected - reconnect in 4s", "warn");
      setTimeout(connectWs, 4000);
    };
    ws.onerror = function () {
      els.wsState.textContent = "WebSocket: error";
    };
  }

  function handleEvent(msg) {
    const ev = msg.event || "event";
    const p = msg.payload || {};
    let kind = "";
    let text = "";
    switch (ev) {
      case "prompt.received":
        text = "prompt: " + (p.prompt || "");
        break;
      case "plan.ready":
        renderPlan(p.plan);
        text = "rencana siap (" + (p.plan.steps || []).length + " langkah)";
        kind = "ok";
        break;
      case "step.start":
        text = "#" + p.index + "/" + p.total + " " + p.tool + " - " + (p.note || "");
        break;
      case "step.done":
        kind = p.ok ? "ok" : "err";
        text = "#" + p.index + " " + (p.ok ? "OK" : "GAGAL") +
               " " + (p.result && p.result.text ? "-> " + p.result.text : "");
        break;
      case "plan.done":
        text = "eksekusi selesai (" + (p.results || []).length + " hasil)";
        kind = "ok";
        break;
      case "mcp.connected":
        text = "MCP terhubung: " + JSON.stringify(p.server || {});
        kind = "ok";
        break;
      case "mcp.request":
        text = "-> " + p.method + " " + JSON.stringify(p.params || {});
        break;
      case "mcp.response":
        text = "<- " + p.method + " OK";
        break;
      case "server.start":
        text = "backend start | mcp " + (p.mcp_reachable ? "ok" : "offline");
        break;
      case "ws.connected":
      case "ws.disconnected":
        return; // already handled
      default:
        text = JSON.stringify(p);
    }
    logLine(ev, text, kind);
  }

  // ---- Plan rendering --------------------------------------------------
  function renderPlan(plan) {
    if (!plan || !plan.steps || !plan.steps.length) {
      els.planBox.hidden = true;
      return;
    }
    els.planList.innerHTML = "";
    plan.steps.forEach(function (s) {
      const li = document.createElement("li");
      const tag = '<span class="tag ' + s.group + '">' + s.group + "</span>";
      const args = '<code style="color:#8aa39c">' +
        JSON.stringify(s.args) + "</code>";
      li.innerHTML = tag +
        '<b>' + s.tool + "</b> " +
        '<span style="color:#cde7df">- ' + (s.note || "") + "</span> " +
        args;
      els.planList.appendChild(li);
    });
    els.planConf.textContent =
      "confidence " + Math.round((plan.confidence || 0) * 100) + "%";
    els.planBox.hidden = false;
  }

  // ---- Send prompt -----------------------------------------------------
  async function sendPrompt(promptText) {
    const prompt = (promptText || els.prompt.value).trim();
    if (!prompt) {
      toast("Prompt kosong", "warn");
      return;
    }
    els.send.disabled = true;
    const original = els.send.innerHTML;
    els.send.innerHTML =
      '<span class="spinner"></span> Memproses...';

    logLine("send", 'POST /api/prompt  "' + prompt.slice(0, 60) + (prompt.length > 60 ? "..." : "") + '"');

    try {
      const r = await fetch(backendBase + "/api/prompt", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify({ prompt: prompt, context: {} }),
      });
      const raw = await r.text();
      let data;
      try { data = JSON.parse(raw); }
      catch (e) { data = { ok: false, error: "Bad JSON: " + raw.slice(0, 120) }; }

      if (data.ok) {
        renderPlan(data.plan);
        const okCount = (data.results || []).filter(function (x) {
          return x && x.ok !== false;
        }).length;
        addHistory(prompt, true,
          okCount + "/" + (data.results || []).length + " langkah OK");
        toast("Selesai: " + okCount + "/" + (data.results || []).length + " langkah OK");
        logLine("done", "respons diterima (" + (data.results || []).length + " hasil)", "ok");
      } else {
        addHistory(prompt, false, data.error || "gagal");
        toast("Gagal: " + (data.error || "unknown"), "err");
        logLine("done", "error: " + (data.error || "unknown"), "err");
      }
    } catch (e) {
      // ERR_CONNECTION_REFUSED typically lands here
      addHistory(prompt, false, "koneksi gagal");
      toast("Tidak bisa terhubung ke backend " + backendBase +
            " - jalankan server.py / launcher", "err");
      logLine("done", "fetch error: " + e.message, "err");
    } finally {
      els.send.disabled = false;
      els.send.innerHTML = original;
    }
  }

  els.send.addEventListener("click", () => sendPrompt());

  els.prompt.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      sendPrompt();
    }
  });

  els.clear.addEventListener("click", () => {
    els.prompt.value = "";
    els.planBox.hidden = true;
    els.prompt.focus();
  });

  els.chips.forEach(function (chip) {
    chip.addEventListener("click", () => {
      els.prompt.value = chip.dataset.prompt;
      els.prompt.focus();
    });
  });

  // ---- History ---------------------------------------------------------
  function addHistory(prompt, ok, summary) {
    history.unshift({
      time: nowTime(),
      prompt: prompt,
      ok: ok,
      summary: summary,
    });
    history = history.slice(0, 25);
    localStorage.setItem("ombar.history", JSON.stringify(history));
    renderHistory();
  }
  function renderHistory() {
    if (!history.length) {
      els.history.innerHTML =
        '<div class="empty">Belum ada perintah.</div>';
      return;
    }
    els.history.innerHTML = "";
    history.forEach(function (h) {
      const item = document.createElement("div");
      item.className = "item";
      item.innerHTML =
        '<div class="top"><span>' + h.time + '</span>' +
        '<span class="res ' + (h.ok ? "ok" : "bad") + '">' +
        (h.ok ? "OK" : "GAGAL") + '</span></div>' +
        '<div class="p"></div>' +
        '<div class="top" style="margin-top:4px"><span>' + h.summary + '</span></div>';
      item.querySelector(".p").textContent = h.prompt;
      els.history.appendChild(item);
    });
  }
  renderHistory();

  // ---- Boot ------------------------------------------------------------
  logLine("boot", "OMBAR FL-AI Studio dashboard ready");
  pollStatus();
  connectWs();
  setInterval(pollStatus, 15000); // refresh status every 15s
})();
