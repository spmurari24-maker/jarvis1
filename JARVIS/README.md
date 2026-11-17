# JARVIS Core

A Windows 10 compatible, Python 3.11 foundation for a modular personal assistant. It runs locally. Ordinary questions are answered by the free-tier Gemini API or local Ollama when configured; web search is used for current information or when you press Search Web.

## Implemented in this delivery

- FastAPI service and async CLI harness.
- Responsive HTML/CSS/JavaScript command-center dashboard with live local health and skill data, a working command bar, and clearly marked integrations.
- Browser click-to-talk voice input and spoken replies, with “sir” address and a British English voice preferred when available.
- Live DuckDuckGo search for explicit searches and time-sensitive questions, with source links shown in the conversation and a one-click Search Web control.
- Gemini free-tier API chat with local Ollama fallback, short-term conversation context, and untrusted web evidence supplied to the model when search is used.
- Runtime discovery of YAML skill manifests and trusted Python skill modules.
- Async in-process event bus with bounded queues exposed to skills for publish/subscribe.
- Conservative keyword intent routing; unknown requests never become free-form execution plans.
- Four permission tiers, YAML-configured skill ceilings, and one-time explicit approval tokens for approval-tier, high-risk, and critical tools.
- Shutdown phrase that halts new actions, cancels active async tasks, and clears pending approvals.
- Structured JSONL audit trail with secret-field redaction; actions are recorded before execution.
- Per-client sliding-window rate limiting and optional API-key protection.
- Prompt-injection inspection and untrusted-content framing helper for future web/email/model adapters.
- YAML and `.env` configuration, plus an authenticated encrypted JSON store for future local personal data.
- Demo and read-only system skills, with unit tests for core components and API flows.

## Folder structure

```text
jarvis/
├── config/                 # settings and permission ceilings
├── docs/                   # built-in skill worst-case review
├── jarvis/
│   ├── core/               # safety, event bus, orchestrator, registry
│   ├── skills/             # built-in skills and manifests
│   ├── static/             # browser dashboard
│   ├── api.py              # FastAPI routes
│   └── cli.py              # local CLI harness
├── tests/                  # automated unit and API tests
├── dist/                   # optional prebuilt pure-Python wheel
├── .env.example
├── main.py                 # ASGI entry point
├── pyproject.toml
└── README.md
```

## Install on Windows 10

Install Python 3.11, then in PowerShell:

```powershell
cd path\to\jarvis
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

The project ZIP contains the installable source. For a source install without development tools, run `pip install .`; use `pip install -r requirements.txt` when you also want the test tools.

Set `JARVIS_API_KEY` in `.env` before allowing other devices to reach the service. Keep the default host at `127.0.0.1` for local-only use. Never expose the service directly to the public internet.

## Run

```powershell
python -m jarvis skills
python -m jarvis chat "hello Jarvis"
python -m jarvis call system status
python -m jarvis serve
```

Or run `uvicorn main:app --host 127.0.0.1 --port 8765`. Interactive API docs are at `http://127.0.0.1:8765/docs`. If an API key is configured, pass it in the `X-API-Key` header for control routes.

On Windows, `.\start_jarvis.ps1` creates the virtual environment, installs dependencies on first run, and starts JARVIS in the background. Then refresh `http://127.0.0.1:8765/` in your browser. Server logs are written under `storage/logs/`.

Open the dashboard at `http://127.0.0.1:8765/`. It reads the local service status and registered skills. Normal questions go to the configured answer model using its own knowledge; questions about current information can trigger web search automatically. Press Search Web to search any text. When a model is connected, it can use search results as evidence and the dashboard shows clickable sources. Recent activity and follow-up context stay in the current browser tab.

## Connect the answer model

JARVIS answers ordinary questions with the Gemini API using its own model knowledge. Gemini is tried first; if it is unavailable or the free quota is reached, JARVIS tries Ollama on this computer. Search results are added as evidence when a question is time-sensitive or you press Search Web. The last 16 turns are sent with each chat request to preserve follow-up context for the current browser tab.

**Free setup:** create a free API key at [Google AI Studio](https://aistudio.google.com/api-keys), copy `.env.example` to `.env`, and set `GEMINI_API_KEY=your-key` in that file. JARVIS defaults to `gemini-3.5-flash-lite`, a lower-latency model whose input and output are listed as free on Google's free tier. Change it with `JARVIS_GEMINI_MODEL` if needed. Usage is still subject to account and quota limits. Do not link a paid billing project if you want to keep this setup free. Keep the key in `.env`; do not paste it into chat or commit it. The free tier may use prompts to improve Google's products, so do not send sensitive personal data through it.

For a local fallback, install Ollama, download the configured model with `ollama pull gemma4`, and keep the Ollama service running. Change `JARVIS_OLLAMA_MODEL` if you install a different model. JARVIS does not download model weights automatically.

If neither provider is ready, JARVIS will say model setup is required. The web-search route still works on its own, but it will return a quoted search excerpt instead of a generated conversational answer. The free Gemini tier has rate limits and can be unavailable after its quota is used; Ollama is the no-API-fee local fallback. No language model can guarantee every answer is correct; JARVIS is instructed to state uncertainty and show sources for web-grounded answers.

For voice, open the dashboard in a supported desktop browser, allow microphone access when prompted, and press the microphone button. JARVIS transcribes one spoken question, displays the transcript and answer, then reads the answer aloud. Browser speech recognition support varies; the browser or operating system may send audio to its speech service. Spoken output uses the system's available voice, preferring British English. This is click-to-talk, not an always-on wake word.

Web search is enabled by default, but ordinary questions do not automatically trigger a search. Search runs for explicit requests or questions that appear to need current facts; results are treated as untrusted evidence, never as executable instructions. Disable it with `JARVIS_WEB_SEARCH_ENABLED=false` or `web_search_enabled: false` in `config/settings.yaml`. Search needs an internet connection. If no answer model is configured, JARVIS can only show a short search excerpt and cannot provide a conversational answer.

Example approval cycle:

```powershell
$pending = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/v1/skills/demo/demo_critical_action -ContentType 'application/json' -Body '{"arguments":{}}'
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/v1/confirmations/$($pending.confirmation_id)"
```

The approval token is one-use and expires after the configured interval. Critical actions always require approval; this example's critical action is intentionally harmless.

## Configuration

Edit `config/settings.yaml` and `config/permissions.yaml`, or override host, port, offline-safe mode, audit path, API key, and encryption key through variables in `.env.example`. Process environment variables normally take precedence over `.env`; a non-empty `GEMINI_API_KEY` in this project's `.env` takes precedence over a system-wide key so JARVIS can use the key you set for this project. Skill permission ceilings can restrict a manifest's declared tier.

Generate an encryption key with:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store it as `JARVIS_ENCRYPTION_KEY` in `.env`; do not commit the key. `EncryptedJsonStore` requires a key and rejects an invalid key or modified ciphertext. The current demo does not persist personal data. The audit trail omits request bodies and redacts common secret fields, but local audit files are not encrypted.

## Add a skill

Create a directory under `skills/` with `manifest.yaml`, a Python module, and a `BaseSkill` subclass. The manifest declares its name, description, permission tier, tools, risk, and optional intent phrases. The registry imports each declared module on startup. **Only install trusted skill code:** Python plugins run with the same operating-system permissions as JARVIS; manifest permissions are an application guard, not an OS sandbox. Every tool must validate arguments and should be reviewed for worst-case failures.

High-risk or critical tools always request approval even for an autonomous skill. Purchase, delete, unlock, send, and trade operations require approval when their operation name is declared in the manifest. Mark sensitive operations with `critical_action: true` and an appropriate risk level.

## Safety and current limits

- Run on loopback. API-key protection is optional; without a key, do not expose the service to a network.
- The shutdown phrase is accepted through the local API/orchestrator, not by a microphone or hardware switch. Restart the process to resume after shutdown.
- Permission tiers and confirmations are software gates. They are not speaker verification, PIN entry, OS-level confinement, or a defense against a malicious local user.
- Prompt-injection detection uses heuristics and cannot establish that content is safe. Web results are wrapped as untrusted evidence before they are sent to the model.
- Event delivery is in-process and best-effort when a subscriber queue fills; Redis is not configured.
- Gemini and Ollama adapters are implemented, but need a valid free API key or a running local model. Wake-word/VAD voice control and memory extraction are not implemented. Click-to-talk browser speech and web search are available when the browser and internet support them. The dashboard is a responsive HTML/CSS/JavaScript interface; the React/Three.js/WebXR holographic HUD is still future work.

## Tests

```powershell
python -m pytest
```

Tests cover skill discovery and behavior, routing, event delivery, permission enforcement, approval flows, shutdown, rate limits, audit redaction, prompt-injection framing, encrypted storage, web-result parsing, question routing, and FastAPI routes.

## Original wish-list status

The foundational core, responsive dashboard, click-to-talk browser voice, spoken answers, basic web search, and Gemini/Ollama chat adapters are implemented. A free API key or local model must be configured before natural answers are available. These remain **future extensions**, not implemented or implied to work: model-driven tool calls and multi-step planning; always-on wake-word/VAD/streaming speech and speaker verification; personality modes; conversation/episodic/semantic memory and memory viewer; calendar, Gmail, tasks, briefings, research synthesis and citation verification; React/Three.js/WebXR HUD; computer control and browser automation; coding/CAD/simulation; camera vision and gesture control; Home Assistant; security monitoring; host/network/OBD telemetry; finance, travel, health, calls, messaging, and translation integrations; proactive notifications, multi-agent collaboration, self-improvement, and emergency playbooks. Hardware-dependent suit features require external devices and are not part of this package.

## Delivery steps

1. **Foundation:** implemented here, with tests and setup documentation.
2. **Consolidation and packaging:** validate the install/run path and deliver this project as a ZIP. No approval pause is used between these two requested steps.
