(() => {
  const $ = (selector) => document.querySelector(selector);
  const elements = {
    topDate: $("#top-date"), topTime: $("#top-time"), topStatus: $("#top-status"), heroState: $("#hero-state"),
    apiCheck: $("#check-api"), apiNote: $("#check-api-note"), apiState: $("#check-api-state"),
    skillList: $("#skill-list"), skillCount: $("#skill-count"), navSkillCount: $("#nav-skill-count"),
    skillSummary: $("#skill-summary"), skillsFoot: $("#skills-foot"), metricService: $("#metric-service span"),
    metricSkills: $("#metric-skills"), activity: $("#activity-list"), activityCount: $("#activity-count"),
    conversation: $("#conversation"), commandForm: $("#command-form"), commandInput: $("#command-input"),
    search: $("#search-input"), refresh: $("#refresh-button"), diagnostics: $("#diagnostics-button"), focus: $("#focus-toggle"),
    voiceButton: $("#voice-button"), voiceCard: $("#voice-card"), voiceDot: $("#voice-dot"), voiceStatus: $("#voice-status"),
    voiceNote: $("#voice-note"), speechToggle: $("#speech-toggle"), webSearch: $("#web-search-button")
  };
  const sessionEvents = [];
  const conversationHistory = [];
  let skills = [];
  let recognition = null;
  let listening = false;
  let speechEnabled = true;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceInputAvailable = Boolean(SpeechRecognition);
  const voiceOutputAvailable = Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);

  function updateClock() {
    const now = new Date();
    elements.topDate.textContent = new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" }).format(now).toUpperCase();
    elements.topTime.textContent = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(now);
  }

  function showToast(message, type) {
    const previous = document.querySelector(".toast");
    if (previous) previous.remove();
    const toast = document.createElement("div");
    toast.className = ("toast " + (type || "")).trim();
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    toast.textContent = message;
    document.body.append(toast);
    window.setTimeout(() => toast.remove(), 3600);
  }

  function setServiceState(ready, detail, offlineSafe, webSearchEnabled) {
    const label = ready ? "ONLINE" : "OFFLINE";
    const color = ready ? "online" : "offline";
    elements.topStatus.innerHTML = '<span class="status-dot ' + color + '"></span><span>' + label + "</span>";
    elements.heroState.innerHTML = '<i class="status-dot ' + color + '"></i> ' + label;
    elements.apiCheck.className = "check-icon" + (ready ? " good" : "");
    elements.apiCheck.textContent = ready ? "✓" : "!";
    elements.apiNote.textContent = detail || (ready ? "JARVIS is ready" : "JARVIS service is unavailable");
    elements.apiState.textContent = ready ? "READY" : "OFFLINE";
    elements.apiState.style.color = ready ? "var(--teal)" : "var(--red)";
    elements.metricService.textContent = ready ? "ON" : "OFF";
    elements.metricService.parentElement.classList.toggle("safe", ready);
    const safe = offlineSafe === true;
    const safetyLabel = webSearchEnabled === true ? "WEB SEARCH ON" : (webSearchEnabled === false ? "SEARCH OFF" : "UNKNOWN");
    $("#offline-safe-chip").textContent = safetyLabel;
    $("#check-offline").className = "check-icon" + (webSearchEnabled ? " good" : "");
    $("#check-offline").textContent = webSearchEnabled ? "✓" : (webSearchEnabled === false ? "!" : "··");
    $("#check-offline-note").textContent = webSearchEnabled ? "Search runs only when you ask" : (webSearchEnabled === false ? "Disabled in local settings" : "Awaiting service configuration");
    $("#check-offline-state").textContent = webSearchEnabled ? "ON" : (webSearchEnabled === false ? "OFF" : "WAIT");
    $("#check-offline-state").style.color = webSearchEnabled ? "var(--teal)" : (webSearchEnabled === false ? "var(--red)" : "var(--muted)");
    $("#metric-offline span").textContent = safe ? "ON" : (offlineSafe === false ? "OFF" : "—");
    $("#metric-offline").classList.toggle("safe", safe);
    const webState = $("#web-search-state");
    webState.textContent = webSearchEnabled ? "AVAILABLE" : "DISABLED";
    webState.style.color = webSearchEnabled ? "var(--teal)" : "var(--muted)";
    $("#integration-count").textContent = ((webSearchEnabled ? 1 : 0) + (voiceInputAvailable || voiceOutputAvailable ? 1 : 0)) + " AVAILABLE";
  }

  function setVoiceState(mode, detail) {
    const active = mode === "listening";
    elements.voiceCard.classList.toggle("listening", active);
    elements.voiceDot.className = "status-dot " + (active ? "online" : "muted");
    elements.voiceStatus.textContent = active ? "Listening…" : (mode === "error" ? "Voice needs attention" : (voiceInputAvailable ? "Voice ready" : "Open Edge or Chrome"));
    elements.voiceNote.textContent = detail || (voiceInputAvailable
      ? (voiceOutputAvailable ? "Browser speech transcribes; audio may be processed online" : "Input works; spoken output is unavailable")
      : "Voice input needs Edge or Chrome; text chat still works");
    const voiceState = voiceInputAvailable && voiceOutputAvailable ? "READY"
      : voiceInputAvailable ? "INPUT ONLY" : voiceOutputAvailable ? "OUTPUT ONLY" : "UNAVAILABLE";
    $("#voice-integration-state").textContent = voiceState;
    $("#voice-integration-state").style.color = voiceState === "READY" ? "var(--teal)" : "var(--amber)";
  }

  function setModelState(model) {
    const state = model || { provider: "none", status: "missing" };
    const geminiConfigured = state.provider === "gemini" && ["ready", "key_set"].includes(state.status);
    const geminiReady = state.provider === "gemini" && state.status === "ready";
    const ollamaReady = state.provider === "ollama" && state.status === "ready";
    const geminiState = $("#gemini-state");
    const ollamaState = $("#ollama-state");
    geminiState.textContent = geminiReady ? "FREE MODEL READY"
      : state.provider === "gemini" && state.status === "invalid" ? "KEY REJECTED"
        : geminiConfigured ? "KEY SET · UNVERIFIED" : "NEEDS FREE KEY";
    geminiState.style.color = geminiReady ? "var(--teal)"
      : state.provider === "gemini" && state.status === "invalid" ? "var(--red)" : "var(--muted)";
    ollamaState.textContent = ollamaReady ? "MODEL READY" : (state.status === "model_missing" ? "MODEL NEEDED" : "NOT RUNNING");
    ollamaState.style.color = ollamaReady ? "var(--teal)" : "var(--muted)";
    $("#chat-capability").textContent = geminiReady
      ? "Gemini free-tier answers naturally · Web results used when helpful · Follow-up context stays in this tab"
      : geminiConfigured
        ? "Gemini key set · Access is checked on the first answer · Follow-up context stays in this tab"
      : ollamaReady
        ? "Local Ollama answers naturally · Web results used when helpful · Follow-up context stays in this tab"
        : state.provider === "gemini" && state.status === "invalid"
          ? "Gemini rejected this key · Replace it in the local .env file"
        : "Add a free Gemini API key or connect Ollama for natural answers · Search works without a model";
    const available = (Number($("#integration-count").textContent.match(/^\d+/)?.[0]) || 0) + (geminiConfigured || ollamaReady ? 1 : 0);
    $("#integration-count").textContent = available + " AVAILABLE";
  }

  function pushActivity(title, detail, type) {
    sessionEvents.unshift({ title, detail, type: type || "ok", time: new Date() });
    sessionEvents.splice(6);
    renderActivity();
  }

  function renderActivity() {
    elements.activity.replaceChildren();
    elements.activityCount.textContent = sessionEvents.length + " EVENT" + (sessionEvents.length === 1 ? "" : "S");
    if (!sessionEvents.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.innerHTML = '<span class="empty-glyph">⌁</span><p>Standing by, sir.</p><small>Assistant activity will appear here.</small>';
      elements.activity.append(empty);
      return;
    }
    sessionEvents.forEach((event) => {
      const row = document.createElement("div");
      row.className = "activity-item";
      const icon = document.createElement("span");
      icon.className = "activity-icon";
      icon.textContent = event.type === "error" ? "!" : (event.type === "warn" ? "◇" : "✓");
      const copy = document.createElement("span");
      copy.className = "activity-copy";
      const title = document.createElement("strong");
      title.textContent = event.title;
      const detail = document.createElement("small");
      detail.textContent = event.detail;
      copy.append(title, detail);
      const time = document.createElement("span");
      time.className = "activity-time";
      time.textContent = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(event.time);
      row.append(icon, copy, time);
      elements.activity.append(row);
    });
  }

  function renderSkills(items) {
    skills = Array.isArray(items) ? items : [];
    const filter = elements.search.value.trim().toLowerCase();
    const visible = skills.filter((skill) => (skill.name + " " + skill.description + " " + (skill.tools || []).map((tool) => tool.name).join(" ")).toLowerCase().includes(filter));
    elements.skillList.replaceChildren();
    elements.skillCount.textContent = String(skills.length).padStart(2, "0");
    elements.navSkillCount.textContent = String(skills.length);
    elements.metricSkills.textContent = String(skills.length).padStart(2, "0");
    elements.skillSummary.textContent = skills.length + " MODULE" + (skills.length === 1 ? "" : "S") + " REGISTERED";
    elements.skillsFoot.textContent = skills.reduce((sum, skill) => sum + (skill.tools || []).length, 0) + " tools declared";
    if (!visible.length) {
      const empty = document.createElement("div");
      empty.className = "no-skills";
      empty.textContent = skills.length ? "No skills match that search." : "No skills are registered.";
      elements.skillList.append(empty);
      return;
    }
    visible.forEach((skill) => {
      const row = document.createElement("div");
      row.className = "skill-row";
      const symbol = document.createElement("span");
      symbol.className = "skill-symbol";
      symbol.textContent = skill.name === "system" ? "⌁" : "◈";
      const meta = document.createElement("span");
      meta.className = "skill-meta";
      const name = document.createElement("strong");
      name.textContent = skill.name;
      const description = document.createElement("small");
      description.textContent = (skill.description || "Registered skill") + " · " + (skill.tools || []).length + " tools";
      meta.append(name, description);
      const state = document.createElement("b");
      state.className = "ready-label";
      state.textContent = "READY";
      row.append(symbol, meta, state);
      elements.skillList.append(row);
    });
  }

  function addMessage(role, text, sources) {
    const row = document.createElement("div");
    row.className = "message-row " + role;
    if (role === "assistant") {
      const mark = document.createElement("span");
      mark.className = "message-mark";
      mark.textContent = "J";
      row.append(mark);
    }
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    row.append(paragraph);
    if (role === "assistant" && Array.isArray(sources) && sources.length) {
      const sourceList = document.createElement("div");
      sourceList.className = "message-sources";
      sources.slice(0, 5).forEach((source) => {
        try {
          const url = new URL(source.url, window.location.href);
          if (!["https:", "http:"].includes(url.protocol)) return;
          const link = document.createElement("a");
          link.href = url.href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = source.title || url.hostname;
          sourceList.append(link);
        } catch (_) { /* Ignore malformed external result links. */ }
      });
      if (sourceList.childElementCount) row.append(sourceList);
    }
    elements.conversation.append(row);
    elements.conversation.scrollTop = elements.conversation.scrollHeight;
  }

  async function request(path, options) {
    const settings = options || {};
    const response = await fetch(path, {
      ...settings,
      headers: { "Content-Type": "application/json", ...(settings.headers || {}) }
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || ("Request failed (" + response.status + ")"));
    return payload;
  }

  async function refreshStatus(announce) {
    try {
      const results = await Promise.all([request("/health"), request("/v1/skills")]);
      const health = results[0];
      renderSkills(results[1]);
      const ready = health.status === "ready";
      setServiceState(ready, ready ? "Responding on this device" : "Core is halted; restart JARVIS to resume", health.offline_safe, health.web_search_enabled);
      setModelState(health.llm);
      if (announce) {
        pushActivity("Diagnostics complete", results[1].length + " skills · API " + (ready ? "ready" : health.status), ready ? "ok" : "error");
        showToast(ready ? "Diagnostics complete · " + results[1].length + " skills ready" : "JARVIS core is halted", ready ? "" : "error");
      }
    } catch (error) {
      setServiceState(false, "Could not reach the local API", undefined);
      if (announce) showToast(error.message, "error");
    }
  }

  async function sendCommand(text) {
    return sendCommandWithOptions(text, false);
  }

  async function sendCommandWithOptions(text, forceWebSearch) {
    const command = text.trim();
    if (!command) {
      if (forceWebSearch) showToast("Enter what you would like me to search for, sir.", "warning");
      return;
    }
    addMessage("user", command);
    elements.commandInput.value = "";
    const button = $("#send-button");
    button.disabled = true;
    try {
      const body = { text: command, history: conversationHistory.slice(-16) };
      if (forceWebSearch) body.search_web = true;
      const result = await request("/v1/chat", { method: "POST", body: JSON.stringify(body) });
      let answer = result.answer || result.message || result.summary || "Request queued, sir.";
      if (!result.answer && result.status === "completed") {
        const output = result.output;
        if (output && typeof output === "object" && output.status === "ready") {
          answer = "Certainly, sir. JARVIS is ready. Offline-safe mode is " + (output.offline_safe ? "on." : "off.");
        } else if (typeof output === "string") {
          answer = /\bsir\b/i.test(output) ? output : "Certainly, sir. " + output;
        } else if (output !== undefined) {
          answer = "Certainly, sir. " + JSON.stringify(output);
        }
      }
      addMessage("assistant", answer, result.sources);
      if (result.provider === "gemini") setModelState({ provider: "gemini", status: "ready" });
      conversationHistory.push({ role: "user", content: command }, { role: "assistant", content: answer });
      conversationHistory.splice(0, Math.max(0, conversationHistory.length - 16));
      pushActivity(result.provider === "DuckDuckGo" ? "Web search complete" : "Command processed", command.slice(0, 72),
        ["unmatched", "unavailable", "disabled", "no_results"].includes(result.status) ? "warn" : "ok");
      if (result.status === "unmatched") showToast("No configured skill matched that command, sir. Ask a question to search the web.", "warning");
      if (result.status === "unavailable") showToast("Web search could not reach the internet.", "error");
      if (result.status === "disabled") showToast("Web search is disabled in the local settings.", "warning");
      if (result.status === "setup_required") showToast("Add a free Gemini API key or connect Ollama to enable natural answers.", "warning");
      if (result.status === "model_unavailable") showToast("I couldn't complete that answer just now, sir. Please try again in a moment.", "warning");
      if (result.search_warning) showToast(result.search_warning, "warning");
      if (result.external_content_warning) showToast("Instruction-like text detected; it was not executed.", "warning");
      speakAnswer(result.spoken_answer || answer);
    } catch (error) {
      const answer = "I could not complete that request, sir: " + error.message;
      addMessage("assistant", answer);
      conversationHistory.push({ role: "user", content: command }, { role: "assistant", content: answer });
      conversationHistory.splice(0, Math.max(0, conversationHistory.length - 16));
      speakAnswer(answer);
      pushActivity("Command failed", error.message, "error");
      showToast(error.message, "error");
    } finally {
      button.disabled = false;
      elements.commandInput.focus();
    }
  }

  function preferredVoice() {
    if (!voiceOutputAvailable) return null;
    const voices = window.speechSynthesis.getVoices();
    return voices.find((voice) => /^en-GB$/i.test(voice.lang)) || voices.find((voice) => /^en/i.test(voice.lang)) || null;
  }

  function speakAnswer(text) {
    if (!speechEnabled || !voiceOutputAvailable || !text) return;
    window.speechSynthesis.cancel();
    const utterance = new window.SpeechSynthesisUtterance(String(text).slice(0, 900));
    utterance.lang = "en-GB";
    utterance.rate = 0.96;
    utterance.pitch = 0.94;
    const voice = preferredVoice();
    if (voice) utterance.voice = voice;
    window.speechSynthesis.speak(utterance);
  }

  function startVoiceInput() {
    if (!voiceInputAvailable) {
      setVoiceState("error", "Microphone speech input is unavailable here; use Edge or Chrome.");
      showToast("Voice input needs a browser with speech recognition. Text commands remain available.", "warning");
      return;
    }
    if (listening && recognition) {
      recognition.stop();
      return;
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    recognition = new SpeechRecognition();
    recognition.lang = "en-GB";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      listening = true;
      elements.voiceButton.setAttribute("aria-pressed", "true");
      setVoiceState("listening", "Listening now. Your browser handles speech recognition; audio may be processed online.");
    };
    recognition.onresult = (event) => {
      let transcript = "";
      let finalResult = false;
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
        finalResult = finalResult || event.results[index].isFinal;
      }
      if (transcript) elements.commandInput.value = transcript.trim();
      if (finalResult && transcript.trim()) {
        const recognized = transcript.trim();
        pushActivity("Voice question captured", recognized.slice(0, 72), "ok");
        sendCommand(recognized);
      }
    };
    recognition.onerror = (event) => {
      listening = false;
      elements.voiceButton.setAttribute("aria-pressed", "false");
      const detail = event.error === "not-allowed"
        ? "Allow microphone access in your browser to use voice input."
        : event.error === "no-speech" ? "No speech was heard. Press the microphone and try again."
          : "Voice recognition stopped (" + event.error + "). Try again or type your question.";
      setVoiceState("error", detail);
      showToast(detail, "warning");
    };
    recognition.onend = () => {
      listening = false;
      elements.voiceButton.setAttribute("aria-pressed", "false");
      setVoiceState("ready");
    };
    try {
      recognition.start();
    } catch (error) {
      listening = false;
      setVoiceState("error", "Could not start the microphone. Check browser permissions and try again.");
      showToast(error.message, "error");
    }
  }

  elements.commandForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendCommand(elements.commandInput.value);
  });
  elements.voiceButton.addEventListener("click", startVoiceInput);
  elements.webSearch.addEventListener("click", () => sendCommandWithOptions(elements.commandInput.value, true));
  elements.speechToggle.addEventListener("click", () => {
    speechEnabled = !speechEnabled;
    elements.speechToggle.setAttribute("aria-pressed", String(speechEnabled));
    elements.speechToggle.querySelector(".toggle-label").textContent = speechEnabled ? "VOICE ON" : "VOICE OFF";
    if (!speechEnabled && window.speechSynthesis) window.speechSynthesis.cancel();
    showToast(speechEnabled ? "Spoken replies enabled, sir." : "Spoken replies muted, sir.");
  });
  elements.refresh.addEventListener("click", () => refreshStatus(true));
  elements.diagnostics.addEventListener("click", () => refreshStatus(true));
  elements.search.addEventListener("input", () => renderSkills(skills));
  elements.focus.addEventListener("click", () => {
    document.body.classList.toggle("focus-mode");
    elements.focus.setAttribute("aria-pressed", String(document.body.classList.contains("focus-mode")));
  });
  document.querySelectorAll("[data-action]").forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.action === "new-command") {
      elements.commandInput.focus();
      elements.commandInput.scrollIntoView({ behavior: "smooth", block: "center" });
    } else if (button.dataset.action === "skills") {
      document.querySelector("#skills").scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      refreshStatus(true);
    }
  }));
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      event.preventDefault();
      elements.search.focus();
    }
  });

  updateClock();
  setVoiceState("ready");
  if (!voiceInputAvailable) {
    elements.voiceButton.disabled = true;
    elements.voiceButton.title = "Voice input requires Microsoft Edge or Google Chrome";
  }
  if (!voiceOutputAvailable) {
    speechEnabled = false;
    elements.speechToggle.disabled = true;
    elements.speechToggle.setAttribute("aria-pressed", "false");
    elements.speechToggle.querySelector(".toggle-label").textContent = "VOICE N/A";
  }
  window.setInterval(updateClock, 1000);
  window.setInterval(() => refreshStatus(false), 15000);
  refreshStatus(false);
})();
