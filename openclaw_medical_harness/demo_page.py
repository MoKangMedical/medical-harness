"""Interactive demo page for the FastAPI demo server."""

from __future__ import annotations


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>OpenClaw-Medical-Harness</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #09131d;
      --bg-alt: #0f1f2d;
      --panel: rgba(10, 24, 36, 0.82);
      --ink: #eef7ff;
      --muted: #9eb7c7;
      --accent: #5ce1e6;
      --accent-2: #ff8a5b;
      --line: rgba(92, 225, 230, 0.18);
      --glow: rgba(92, 225, 230, 0.16);
      --mono: "IBM Plex Mono", monospace;
      --display: "Space Grotesk", sans-serif;
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 15% 20%, rgba(92, 225, 230, 0.18), transparent 28%),
        radial-gradient(circle at 88% 18%, rgba(255, 138, 91, 0.18), transparent 22%),
        linear-gradient(180deg, #07111a 0%, #09131d 45%, #0a1621 100%);
      font-family: var(--display);
      min-height: 100vh;
      overflow-x: hidden;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size: 44px 44px;
      mask-image: linear-gradient(180deg, rgba(255,255,255,0.3), transparent 85%);
      opacity: 0.18;
    }

    .hero {
      min-height: 100svh;
      padding: 28px 32px 40px;
      display: grid;
      grid-template-rows: auto 1fr auto;
      position: relative;
    }

    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 16px;
    }

    .brand {
      font-size: 14px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--accent);
      font-family: var(--mono);
    }

    .version {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 12px;
    }

    .hero-grid {
      display: grid;
      grid-template-columns: minmax(320px, 1.1fr) minmax(320px, 0.9fr);
      align-items: center;
      gap: 44px;
      padding: 40px 0;
    }

    .eyebrow {
      color: var(--accent-2);
      font-family: var(--mono);
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-size: 12px;
      margin-bottom: 18px;
    }

    h1 {
      margin: 0;
      font-size: clamp(56px, 9vw, 132px);
      line-height: 0.92;
      max-width: 9ch;
      letter-spacing: -0.05em;
    }

    .hero-copy p {
      margin: 18px 0 0;
      max-width: 42ch;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.6;
    }

    .hero-actions {
      margin-top: 30px;
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
    }

    .cta, .ghost {
      appearance: none;
      border: 0;
      cursor: pointer;
      padding: 14px 18px;
      font: 600 14px var(--display);
      letter-spacing: 0.02em;
      transition: transform .28s ease, background-color .28s ease, color .28s ease;
    }

    .cta {
      background: var(--accent);
      color: #031216;
      box-shadow: 0 12px 30px rgba(92, 225, 230, 0.26);
    }

    .ghost {
      background: transparent;
      color: var(--ink);
      border: 1px solid var(--line);
    }

    .cta:hover, .ghost:hover { transform: translateY(-2px); }

    .signal-wall {
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(15,31,45,0.78), rgba(9,19,29,0.85));
      padding: 22px;
      position: relative;
      overflow: hidden;
    }

    .signal-wall::after {
      content: "";
      position: absolute;
      inset: auto -18% -36% auto;
      width: 260px;
      height: 260px;
      background: radial-gradient(circle, rgba(92,225,230,0.28), transparent 65%);
      transform: rotate(12deg);
    }

    .signal-row {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-bottom: 16px;
    }

    .signal-label {
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-family: var(--mono);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }

    .signal-value {
      font-size: 28px;
      letter-spacing: -0.04em;
    }

    .heartbeat {
      margin-top: 16px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      display: grid;
      gap: 10px;
      color: var(--muted);
      font-size: 14px;
    }

    .hero-footer {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
      border-top: 1px solid var(--line);
      padding-top: 18px;
      color: var(--muted);
      font-size: 14px;
    }

    .lab {
      font-family: var(--mono);
      color: var(--accent);
    }

    .workspace {
      padding: 0 32px 48px;
    }

    .workspace-shell {
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      gap: 26px;
      align-items: start;
    }

    .rail {
      position: sticky;
      top: 24px;
      border-top: 1px solid var(--line);
      padding-top: 20px;
    }

    .rail h2 {
      margin: 0 0 16px;
      font-size: 28px;
      letter-spacing: -0.04em;
    }

    .rail p {
      margin: 0 0 20px;
      color: var(--muted);
      line-height: 1.6;
      font-size: 14px;
    }

    .nav-list {
      display: grid;
      gap: 8px;
    }

    .nav-button {
      border: 0;
      background: transparent;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      color: var(--muted);
      text-align: left;
      padding: 14px 0;
      cursor: pointer;
      transition: color .24s ease, transform .24s ease;
      font: 500 15px var(--display);
    }

    .nav-button.active {
      color: var(--ink);
      transform: translateX(6px);
    }

    .workbench {
      border-top: 1px solid var(--line);
      padding-top: 20px;
    }

    .panel {
      display: none;
      min-height: 640px;
      grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
      gap: 20px;
      align-items: start;
      animation: fadePanel .45s ease;
    }

    .panel.active { display: grid; }

    @keyframes fadePanel {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .form-plane, .result-plane {
      border: 1px solid var(--line);
      background: var(--panel);
      backdrop-filter: blur(12px);
    }

    .form-plane {
      padding: 22px;
    }

    .result-plane {
      min-height: 100%;
      padding: 22px;
      position: sticky;
      top: 24px;
    }

    .plane-title {
      margin: 0 0 14px;
      font-size: 24px;
      letter-spacing: -0.04em;
    }

    .plane-copy {
      margin: 0 0 22px;
      color: var(--muted);
      line-height: 1.6;
      font-size: 14px;
    }

    .field-grid {
      display: grid;
      gap: 14px;
    }

    .field-row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }

    label {
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-family: var(--mono);
    }

    input, textarea, select {
      width: 100%;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
      color: var(--ink);
      padding: 12px 14px;
      font: 400 14px var(--display);
      resize: vertical;
      outline: none;
      transition: border-color .24s ease, transform .24s ease;
    }

    input:focus, textarea:focus, select:focus {
      border-color: rgba(92,225,230,0.56);
      transform: translateY(-1px);
    }

    textarea { min-height: 122px; }
    .mini { min-height: 88px; }

    .actions {
      margin-top: 18px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    .action-button {
      border: 0;
      cursor: pointer;
      padding: 12px 16px;
      font: 600 13px var(--display);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      background: rgba(92,225,230,0.12);
      color: var(--accent);
      transition: background .24s ease, transform .24s ease;
    }

    .action-button:hover { background: rgba(92,225,230,0.18); transform: translateY(-2px); }

    .result-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
    }

    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font: 13px/1.6 var(--mono);
      color: #d7eef0;
    }

    .result-shell {
      border-top: 1px solid var(--line);
      padding-top: 16px;
      min-height: 380px;
    }

    .tool-strip {
      margin-top: 18px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }

    .tool-item {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      border-bottom: 1px solid rgba(255,255,255,0.04);
      padding-bottom: 8px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 8px;
      border: 1px solid rgba(255,255,255,0.08);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-family: var(--mono);
      color: var(--muted);
    }

    .status-good { color: var(--accent); }
    .status-warn { color: var(--accent-2); }

    .stagger {
      opacity: 0;
      animation: rise .8s ease forwards;
    }

    .stagger:nth-child(2) { animation-delay: .12s; }
    .stagger:nth-child(3) { animation-delay: .24s; }
    .stagger:nth-child(4) { animation-delay: .36s; }

    @keyframes rise {
      from { opacity: 0; transform: translateY(18px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @media (max-width: 1080px) {
      .hero-grid, .workspace-shell, .panel { grid-template-columns: 1fr; }
      .result-plane { position: relative; top: 0; }
      h1 { max-width: 12ch; }
    }

    @media (max-width: 720px) {
      .hero, .workspace { padding-left: 18px; padding-right: 18px; }
      .field-row, .signal-row { grid-template-columns: 1fr; }
      h1 { font-size: clamp(44px, 18vw, 72px); }
      .hero-footer { flex-direction: column; align-items: start; }
    }
  </style>
</head>
<body>
  <section class="hero">
    <div class="topbar stagger">
      <div class="brand">Medical Harness / Live Console</div>
      <div class="version">v__VERSION__</div>
    </div>

    <div class="hero-grid">
      <div class="hero-copy">
        <div class="eyebrow stagger">Harness-first medical AI orchestration</div>
        <h1 class="stagger">OpenClaw Medical Harness</h1>
        <p class="stagger">Run diagnosis, drug discovery, health management, MiMo media generation, and OpenArena readiness flows from one surface. The model is replaceable. The harness is the system.</p>
        <div class="hero-actions stagger">
          <button class="cta" onclick="document.getElementById('workspace').scrollIntoView()">Launch Workbench</button>
          <button class="ghost" onclick="refreshSignals()">Refresh Runtime</button>
        </div>
      </div>

      <div class="signal-wall stagger">
        <div class="signal-row">
          <div>
            <span class="signal-label">Tools Registered</span>
            <div class="signal-value" id="signal-tools">__TOOL_COUNT__</div>
          </div>
          <div>
            <span class="signal-label">Runtime</span>
            <div class="signal-value" id="signal-runtime">Live</div>
          </div>
          <div>
            <span class="signal-label">OpenArena</span>
            <div class="signal-value" id="signal-openarena">Readiness</div>
          </div>
        </div>
        <div class="heartbeat">
          <div><span class="lab">API</span> <span id="heartbeat-api">Waiting for /health-check …</span></div>
          <div><span class="lab">Registry</span> <span id="heartbeat-registry">Fetching real adapter metadata …</span></div>
          <div><span class="lab">Submit</span> <span id="heartbeat-submit">OpenArena runtime not checked yet</span></div>
        </div>
      </div>
    </div>

    <div class="hero-footer stagger">
      <div>Three harnesses, one MiMo media lane, one optional OpenArena submission lane.</div>
      <div class="lab">HTTP + local adapters / MiMo OpenAI-compatible media / readiness scoring</div>
    </div>
  </section>

  <section class="workspace" id="workspace">
    <div class="workspace-shell">
      <aside class="rail">
        <h2>Workbench</h2>
        <p>Each lane has one job. Feed clinical data on the left, inspect structured output on the right, and keep the registry and submission state visible while you work.</p>
        <div class="nav-list">
          <button class="nav-button active" data-panel-target="diagnosis">Diagnosis Harness</button>
          <button class="nav-button" data-panel-target="drug">Drug Discovery</button>
          <button class="nav-button" data-panel-target="health">Health Management</button>
          <button class="nav-button" data-panel-target="media">MiMo Media</button>
          <button class="nav-button" data-panel-target="openarena">OpenArena</button>
        </div>
      </aside>

      <div class="workbench">
        <div class="panel active" id="panel-diagnosis">
          <section class="form-plane">
            <h3 class="plane-title">Diagnostic lane</h3>
            <p class="plane-copy">For symptom triage, differential generation, and next-step testing strategy.</p>
            <form id="form-diagnosis" class="field-grid">
              <label>Symptoms (comma separated)
                <textarea name="symptoms">bilateral ptosis, fatigable weakness, diplopia</textarea>
              </label>
              <div class="field-row">
                <label>Age
                  <input name="age" value="35" />
                </label>
                <label>Sex
                  <select name="sex">
                    <option value="F" selected>F</option>
                    <option value="M">M</option>
                  </select>
                </label>
              </div>
              <label>Specialty
                <input name="specialty" value="neurology" />
              </label>
              <div class="actions">
                <button class="action-button" type="submit">Run Diagnosis</button>
              </div>
            </form>
          </section>
          <section class="result-plane">
            <div class="result-meta">
              <span>Structured output</span>
              <span id="diagnosis-meta">idle</span>
            </div>
            <div class="result-shell"><pre id="diagnosis-result">Ready.</pre></div>
          </section>
        </div>

        <div class="panel" id="panel-drug">
          <section class="form-plane">
            <h3 class="plane-title">Discovery lane</h3>
            <p class="plane-copy">For target-aware candidate retrieval, ADMET summarization, and optimization cues.</p>
            <form id="form-drug" class="field-grid">
              <div class="field-row">
                <label>Target
                  <input name="target" value="EGFR" />
                </label>
                <label>Disease
                  <input name="disease" value="NSCLC" />
                </label>
              </div>
              <label>Max compounds
                <input name="max_compounds" value="5" />
              </label>
              <div class="actions">
                <button class="action-button" type="submit">Run Discovery</button>
              </div>
            </form>
          </section>
          <section class="result-plane">
            <div class="result-meta">
              <span>Candidate stack</span>
              <span id="drug-meta">idle</span>
            </div>
            <div class="result-shell"><pre id="drug-result">Ready.</pre></div>
          </section>
        </div>

        <div class="panel" id="panel-health">
          <section class="form-plane">
            <h3 class="plane-title">Longitudinal care lane</h3>
            <p class="plane-copy">For care planning, adherence tracking, and follow-up checkpoints across chronic management workflows.</p>
            <form id="form-health" class="field-grid">
              <label>Conditions (comma separated)
                <input name="conditions" value="type 2 diabetes" />
              </label>
              <div class="field-row">
                <label>Age
                  <input name="age" value="55" />
                </label>
                <label>Goal
                  <input name="health_goal" value="HbA1c below 7.0%" />
                </label>
              </div>
              <label>Lab results JSON
                <textarea class="mini" name="lab_results">{"hba1c": 7.2}</textarea>
              </label>
              <div class="actions">
                <button class="action-button" type="submit">Run Health Plan</button>
              </div>
            </form>
          </section>
          <section class="result-plane">
            <div class="result-meta">
              <span>Care output</span>
              <span id="health-meta">idle</span>
            </div>
            <div class="result-shell"><pre id="health-result">Ready.</pre></div>
          </section>
        </div>

        <div class="panel" id="panel-openarena">
          <section class="form-plane">
            <h3 class="plane-title">OpenArena lane</h3>
            <p class="plane-copy">Run a readiness score locally, inspect the exact payload, and optionally submit if runtime credentials are configured.</p>
            <form id="form-openarena" class="field-grid">
              <label>Project name
                <input name="project_name" value="OpenClaw-Medical-Harness" />
              </label>
              <div class="field-row">
                <label>GitHub repo
                  <input name="github_repo_url" value="https://github.com/MoKangMedical/openclaw-medical-harness" />
                </label>
                <label>X status URL
                  <input name="x_post_url" value="" placeholder="https://x.com/.../status/123" />
                </label>
              </div>
              <div class="field-row">
                <label>Submitter name
                  <input name="submitter_name" value="Lin Zhang" />
                </label>
                <label>Payout address
                  <input name="submitter_payout_address" value="" placeholder="0x..." />
                </label>
              </div>
              <label>Team contact
                <input name="team_contact" value="" placeholder="email, @handle" />
              </label>
              <label>Submitter contact
                <input name="submitter_contact" value="" placeholder="email, @handle" />
              </label>
              <label>Ranking reason
                <textarea name="ranking_reason">OpenClaw-Medical-Harness turns medical AI work into a reusable harness architecture, combining tool orchestration, context shaping, validation, and recovery into a model-agnostic medical workflow layer.</textarea>
              </label>
              <label>Additional notes
                <textarea class="mini" name="additional_notes">Public repository is available.</textarea>
              </label>
              <div class="actions">
                <button class="action-button" type="button" onclick="checkOpenArena()">Check Readiness</button>
                <button class="action-button" type="button" onclick="submitOpenArena()">Submit Live</button>
                <button class="action-button" type="button" onclick="submitOpenArenaDefaults()">One-click via .env</button>
              </div>
            </form>
          </section>
          <section class="result-plane">
            <div class="result-meta">
              <span>Submission status</span>
              <span id="openarena-meta">idle</span>
            </div>
            <div class="result-shell"><pre id="openarena-result">Ready.</pre></div>
            <div class="tool-strip" id="openarena-runtime"></div>
          </section>
        </div>

        <div class="panel" id="panel-media">
          <section class="form-plane">
            <h3 class="plane-title">MiMo media lane</h3>
            <p class="plane-copy">Use Xiaomi MiMo for TTS, audio understanding, video understanding, and video production packages. Official docs expose speech synthesis plus audio/video understanding; rendered video generation is not publicly exposed.</p>

            <form id="form-media-tts" class="field-grid">
              <label>Speech text
                <textarea name="text">请用中文为患者解释为什么要按时复查糖化血红蛋白。</textarea>
              </label>
              <div class="field-row">
                <label>Voice
                  <select name="voice">
                    <option value="mimo_default" selected>mimo_default</option>
                    <option value="default_zh">default_zh</option>
                    <option value="default_en">default_en</option>
                  </select>
                </label>
                <label>Format
                  <select name="audio_format">
                    <option value="wav" selected>wav</option>
                    <option value="pcm16">pcm16</option>
                  </select>
                </label>
              </div>
              <label>Style
                <input name="style" value="Calm Warm" placeholder="Happy / Whisper / Slow down / 唱歌" />
              </label>
              <div class="actions">
                <button class="action-button" type="submit">Synthesize Speech</button>
              </div>
            </form>

            <form id="form-media-audio" class="field-grid" style="margin-top: 24px;">
              <label>Audio URL
                <input name="audio_url" value="" placeholder="https://example.com/audio.wav" />
              </label>
              <label>Prompt
                <input name="prompt" value="Please summarize the audio and extract the key clinical message." />
              </label>
              <div class="actions">
                <button class="action-button" type="submit">Analyze Audio</button>
              </div>
            </form>

            <form id="form-media-video" class="field-grid" style="margin-top: 24px;">
              <label>Video URL
                <input name="video_url" value="" placeholder="https://example.com/video.mp4" />
              </label>
              <div class="field-row">
                <label>FPS
                  <input name="fps" value="2" />
                </label>
                <label>Resolution
                  <select name="media_resolution">
                    <option value="default" selected>default</option>
                    <option value="low">low</option>
                    <option value="high">high</option>
                  </select>
                </label>
              </div>
              <label>Prompt
                <input name="prompt" value="Please describe the video and extract the medically relevant actions." />
              </label>
              <div class="actions">
                <button class="action-button" type="submit">Analyze Video</button>
              </div>
            </form>

            <form id="form-media-video-create" class="field-grid" style="margin-top: 24px;">
              <label>Video brief
                <textarea name="brief">制作一条 60 秒患者教育短视频，主题是高血压患者为什么要每天固定时间测量血压。</textarea>
              </label>
              <div class="field-row">
                <label>Audience
                  <input name="audience" value="patients" />
                </label>
                <label>Duration seconds
                  <input name="duration_seconds" value="60" />
                </label>
              </div>
              <div class="field-row">
                <label>Language
                  <input name="language" value="zh" />
                </label>
                <label>Tone
                  <input name="tone" value="clear medical education" />
                </label>
              </div>
              <div class="actions">
                <button class="action-button" type="submit">Create Video Package</button>
              </div>
            </form>
          </section>
          <section class="result-plane">
            <div class="result-meta">
              <span>MiMo output</span>
              <span id="media-meta">idle</span>
            </div>
            <div class="result-shell"><pre id="media-result">Ready.</pre></div>
          </section>
        </div>
      </div>
    </div>
  </section>

  <script>
    const navButtons = Array.from(document.querySelectorAll('.nav-button'));
    const panels = Array.from(document.querySelectorAll('.panel'));

    function showPanel(panelName) {
      navButtons.forEach(button => button.classList.toggle('active', button.dataset.panelTarget === panelName));
      panels.forEach(panel => panel.classList.toggle('active', panel.id === 'panel-' + panelName));
    }

    navButtons.forEach(button => button.addEventListener('click', () => showPanel(button.dataset.panelTarget)));

    function pretty(value) {
      return JSON.stringify(value, null, 2);
    }

    async function fetchJson(url, options) {
      const response = await fetch(url, options);
      const text = await response.text();
      try {
        return { ok: response.ok, status: response.status, data: JSON.parse(text) };
      } catch (error) {
        return { ok: response.ok, status: response.status, data: { raw: text } };
      }
    }

    function parseCsv(text) {
      return text.split(',').map(item => item.trim()).filter(Boolean);
    }

    function parseJsonField(text) {
      if (!text.trim()) return {};
      return JSON.parse(text);
    }

    async function refreshSignals() {
      const health = await fetchJson('/health-check');
      const tools = await fetchJson('/api/tools');
      const media = await fetchJson('/media/runtime');
      const runtime = await fetchJson('/openarena/runtime');

      document.getElementById('heartbeat-api').textContent = health.ok ? ('healthy / ' + health.data.version) : 'unavailable';
      document.getElementById('heartbeat-registry').textContent = tools.ok ? (tools.data.tools.length + ' transport-backed tools active') : 'tool registry unavailable';
      document.getElementById('heartbeat-submit').textContent = runtime.ok
        ? (runtime.data.can_submit_live ? 'runtime configured for live submit' : 'runtime not fully configured')
        : (media.ok ? (media.data.has_api_key ? 'MiMo media runtime configured' : 'MiMo API key missing') : 'runtime unavailable');

      document.getElementById('signal-tools').textContent = tools.ok ? tools.data.tools.length : '--';
      document.getElementById('signal-runtime').textContent = health.ok ? 'Healthy' : 'Down';
      document.getElementById('signal-openarena').textContent = runtime.ok ? (runtime.data.can_submit_live ? 'Ready' : 'Check') : 'Unknown';

      if (tools.ok) {
        const openArenaRuntime = document.getElementById('openarena-runtime');
        openArenaRuntime.innerHTML = tools.data.tools.slice(0, 6).map(tool =>
          '<div class="tool-item"><span>' + tool.name + '</span><span class="pill">' + tool.transport + ' / ' + tool.protocol + '</span></div>'
        ).join('');
      }

      if (runtime.ok) {
        hydrateOpenArenaDefaults(runtime.data.submission_defaults || {});
      }
    }

    async function submitDiagnosis(event) {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const payload = {
        symptoms: parseCsv(form.get('symptoms') || ''),
        specialty: form.get('specialty') || 'neurology',
        patient: {
          age: Number(form.get('age') || 0),
          sex: form.get('sex') || ''
        }
      };
      document.getElementById('diagnosis-meta').textContent = 'running';
      const response = await fetchJson('/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      document.getElementById('diagnosis-meta').textContent = response.ok ? 'complete' : 'error';
      document.getElementById('diagnosis-result').textContent = pretty(response.data);
    }

    async function submitDrug(event) {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const payload = {
        target: form.get('target'),
        disease: form.get('disease'),
        max_compounds: Number(form.get('max_compounds') || 5),
      };
      document.getElementById('drug-meta').textContent = 'running';
      const response = await fetchJson('/drug-discovery', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      document.getElementById('drug-meta').textContent = response.ok ? 'complete' : 'error';
      document.getElementById('drug-result').textContent = pretty(response.data);
    }

    async function submitHealth(event) {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const payload = {
        conditions: parseCsv(form.get('conditions') || ''),
        health_goal: form.get('health_goal'),
        age: Number(form.get('age') || 0),
        lab_results: parseJsonField(form.get('lab_results') || '{}'),
      };
      document.getElementById('health-meta').textContent = 'running';
      const response = await fetchJson('/health', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      document.getElementById('health-meta').textContent = response.ok ? 'complete' : 'error';
      document.getElementById('health-result').textContent = pretty(response.data);
    }

    async function submitMediaTts(event) {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const payload = {
        text: form.get('text'),
        voice: form.get('voice'),
        audio_format: form.get('audio_format'),
        style: form.get('style'),
      };
      document.getElementById('media-meta').textContent = 'synthesizing';
      const response = await fetchJson('/media/audio/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      document.getElementById('media-meta').textContent = response.ok ? 'speech-ready' : 'error';
      document.getElementById('media-result').textContent = pretty(response.data);
    }

    async function submitMediaAudio(event) {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const payload = {
        audio_url: form.get('audio_url'),
        prompt: form.get('prompt'),
      };
      document.getElementById('media-meta').textContent = 'audio-understanding';
      const response = await fetchJson('/media/audio/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      document.getElementById('media-meta').textContent = response.ok ? 'audio-complete' : 'error';
      document.getElementById('media-result').textContent = pretty(response.data);
    }

    async function submitMediaVideo(event) {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const payload = {
        video_url: form.get('video_url'),
        fps: Number(form.get('fps') || 2),
        media_resolution: form.get('media_resolution'),
        prompt: form.get('prompt'),
      };
      document.getElementById('media-meta').textContent = 'video-understanding';
      const response = await fetchJson('/media/video/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      document.getElementById('media-meta').textContent = response.ok ? 'video-complete' : 'error';
      document.getElementById('media-result').textContent = pretty(response.data);
    }

    async function submitMediaVideoCreate(event) {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const payload = {
        brief: form.get('brief'),
        audience: form.get('audience'),
        duration_seconds: Number(form.get('duration_seconds') || 60),
        language: form.get('language'),
        tone: form.get('tone'),
      };
      document.getElementById('media-meta').textContent = 'video-package';
      const response = await fetchJson('/media/video/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      document.getElementById('media-meta').textContent = response.ok ? 'package-ready' : 'error';
      document.getElementById('media-result').textContent = pretty(response.data);
    }

    function buildOpenArenaPayload() {
      const form = new FormData(document.getElementById('form-openarena'));
      return {
        project_name: form.get('project_name'),
        github_repo_url: form.get('github_repo_url'),
        x_post_url: form.get('x_post_url'),
        team_contact: form.get('team_contact'),
        submitter_name: form.get('submitter_name'),
        submitter_contact: form.get('submitter_contact'),
        submitter_payout_address: form.get('submitter_payout_address'),
        ranking_reason: form.get('ranking_reason'),
        additional_notes: form.get('additional_notes'),
        team_aware: true,
      };
    }

    async function checkOpenArena() {
      document.getElementById('openarena-meta').textContent = 'checking';
      const response = await fetchJson('/openarena/readiness', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildOpenArenaPayload()),
      });
      document.getElementById('openarena-meta').textContent = response.ok ? 'ready-check' : 'error';
      document.getElementById('openarena-result').textContent = pretty(response.data);
    }

    async function submitOpenArena() {
      document.getElementById('openarena-meta').textContent = 'submitting';
      const response = await fetchJson('/openarena/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildOpenArenaPayload()),
      });
      document.getElementById('openarena-meta').textContent = response.ok ? 'submitted' : 'error';
      document.getElementById('openarena-result').textContent = pretty(response.data);
    }

    async function submitOpenArenaDefaults() {
      document.getElementById('openarena-meta').textContent = 'one-click';
      const response = await fetchJson('/openarena/submit-default', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      document.getElementById('openarena-meta').textContent = response.ok ? 'submitted' : 'error';
      document.getElementById('openarena-result').textContent = pretty(response.data);
    }

    function hydrateOpenArenaDefaults(defaults) {
      const form = document.getElementById('form-openarena');
      if (!form || !defaults) return;
      Object.entries(defaults).forEach(([key, value]) => {
        const field = form.elements.namedItem(key);
        if (field && !field.value && value) {
          field.value = value;
        }
      });
    }

    document.getElementById('form-diagnosis').addEventListener('submit', submitDiagnosis);
    document.getElementById('form-drug').addEventListener('submit', submitDrug);
    document.getElementById('form-health').addEventListener('submit', submitHealth);
    document.getElementById('form-media-tts').addEventListener('submit', submitMediaTts);
    document.getElementById('form-media-audio').addEventListener('submit', submitMediaAudio);
    document.getElementById('form-media-video').addEventListener('submit', submitMediaVideo);
    document.getElementById('form-media-video-create').addEventListener('submit', submitMediaVideoCreate);

    refreshSignals();
  </script>
</body>
</html>
""".strip()


def render_demo_page(*, version: str, tool_count: int) -> str:
    return (
        HTML_TEMPLATE
        .replace("__VERSION__", version)
        .replace("__TOOL_COUNT__", str(tool_count))
    )
