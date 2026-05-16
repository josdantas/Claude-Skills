#!/usr/bin/env python3
"""
Custom eval viewer generator for validador-ideias-literarias.
Fixes:
- ensure_ascii=False so accented characters render correctly
- Markdown files rendered as HTML via marked.js
- HTML positioning maps rendered in sandboxed iframes
- Clean side-by-side comparison layout
"""
import json
import base64
import re
from pathlib import Path

WORKSPACE = Path(__file__).parent / "iteration-1"
OUTPUT = Path(__file__).parent / "eval_review_v2.html"

EVALS = [
    ("eval-0-nutricao",      "🇧🇷 Nutricionista (PT) — Ideia Forte"),
    ("eval-1-ai-bakery",     "🇺🇸 Padaria IA (EN) — Ideia Forte"),
    ("eval-2-felicidade",    "🇧🇷 Felicidade (PT) — Ideia Fraca"),
    ("eval-3-bienestar-es",  "🇪🇸 Bienestar Latinas (ES) — Coleta Parcial"),
    ("eval-4-financas-pt",   "🇧🇷 Finanças Jovens (PT) — Inputs Completos"),
]

def read_file(path: Path) -> dict:
    ext = path.suffix.lower()
    name = path.name
    if ext in {".md", ".txt", ".json", ".csv", ".py"}:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = "(erro ao ler arquivo)"
        return {"name": name, "type": "md" if ext == ".md" else "text", "content": content}
    elif ext == ".html":
        try:
            raw = path.read_bytes()
            b64 = base64.b64encode(raw).decode("ascii")
        except Exception:
            return {"name": name, "type": "error", "content": "Erro"}
        return {"name": name, "type": "html_iframe", "b64": b64}
    elif ext in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
        try:
            raw = path.read_bytes()
            b64 = base64.b64encode(raw).decode("ascii")
        except Exception:
            return {"name": name, "type": "error", "content": "Erro"}
        mime = {"png":"image/png","jpg":"image/jpeg","jpeg":"image/jpeg","gif":"image/gif","svg":"image/svg+xml"}.get(ext.lstrip("."), "image/png")
        return {"name": name, "type": "image", "b64": b64, "mime": mime}
    else:
        # binary download
        try:
            raw = path.read_bytes()
            b64 = base64.b64encode(raw).decode("ascii")
        except Exception:
            return {"name": name, "type": "error", "content": "Erro"}
        return {"name": name, "type": "binary", "b64": b64}

def load_run(eval_dir: Path, config: str) -> dict:
    run_dir = eval_dir / config
    outputs_dir = run_dir / "outputs"
    
    # Load grading
    grading = None
    for gpath in [run_dir / "grading.json", eval_dir / config / "grading.json"]:
        if gpath.exists():
            grading = json.loads(gpath.read_text(encoding="utf-8"))
            break
    
    # Load prompt from eval_metadata.json
    prompt = ""
    meta_path = eval_dir / "eval_metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        prompt = meta.get("prompt", "")
    
    # Load output files
    files = []
    if outputs_dir.exists():
        SKIP = {"transcript.md", "user_notes.md", "metrics.json"}
        for f in sorted(outputs_dir.iterdir()):
            if f.is_file() and f.name not in SKIP:
                files.append(read_file(f))
    
    return {
        "config": config,
        "prompt": prompt,
        "grading": grading,
        "files": files,
    }

def build_data():
    evals = []
    for eval_id, label in EVALS:
        eval_dir = WORKSPACE / eval_id
        if not eval_dir.exists():
            continue
        evals.append({
            "id": eval_id,
            "label": label,
            "with_skill": load_run(eval_dir, "with_skill"),
            "without_skill": load_run(eval_dir, "without_skill"),
        })
    
    # Load benchmark
    benchmark = None
    bpath = WORKSPACE / "benchmark.json"
    if bpath.exists():
        benchmark = json.loads(bpath.read_text(encoding="utf-8"))
    
    return {"evals": evals, "benchmark": benchmark}

def generate_html(data: dict) -> str:
    data_json = json.dumps(data, ensure_ascii=False)
    
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Eval Review — Validador de Ideias Literárias</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  :root {{
    --bg: #faf9f5;
    --surface: #fff;
    --border: #e5e3d8;
    --text: #1a1a18;
    --muted: #888;
    --accent: #c94f2c;
    --green: #2e7d5e;
    --green-bg: #edf5f0;
    --red: #b33;
    --red-bg: #fdf0f0;
    --blue: #1565c0;
    --blue-bg: #e8f0fe;
    --gold: #c17f24;
    --gold-bg: #fef8ec;
    --radius: 8px;
    --shadow: 0 1px 4px rgba(0,0,0,.08);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); }}

  /* Header */
  .header {{
    background: #1a1a18; color: #faf9f5;
    padding: 1.25rem 2rem;
    display: flex; align-items: center; gap: 1rem;
  }}
  .header h1 {{ font-size: 1.1rem; font-weight: 600; }}
  .header .sub {{ font-size: 0.8rem; opacity: 0.6; margin-top: 0.2rem; }}

  /* Benchmark banner */
  .benchmark {{
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 0.75rem 2rem;
    display: flex; gap: 2rem; align-items: center; flex-wrap: wrap;
  }}
  .bm-label {{ font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }}
  .bm-val {{ font-size: 1.4rem; font-weight: 700; }}
  .bm-val.green {{ color: var(--green); }}
  .bm-val.red {{ color: var(--red); }}
  .bm-item {{ display: flex; flex-direction: column; gap: 2px; }}
  .bm-sep {{ width: 1px; background: var(--border); height: 2rem; }}

  /* Nav tabs */
  .tabs {{ 
    border-bottom: 2px solid var(--border);
    display: flex; gap: 0; padding: 0 2rem;
    background: var(--surface);
    overflow-x: auto;
  }}
  .tab-btn {{
    padding: 0.75rem 1.25rem;
    border: none; background: none; cursor: pointer;
    font-size: 0.875rem; font-weight: 500; color: var(--muted);
    border-bottom: 2px solid transparent; margin-bottom: -2px;
    white-space: nowrap; transition: all .15s;
  }}
  .tab-btn.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
  .tab-btn:hover:not(.active) {{ color: var(--text); }}

  /* Main content */
  .content {{ padding: 1.5rem 2rem; max-width: 1400px; margin: 0 auto; }}

  /* Prompt card */
  .prompt-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 1rem 1.25rem;
    margin-bottom: 1.25rem; box-shadow: var(--shadow);
  }}
  .prompt-card .section-label {{
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .05em; color: var(--muted); margin-bottom: 0.5rem;
  }}
  .prompt-text {{ font-size: 0.9rem; line-height: 1.6; white-space: pre-wrap; }}

  /* Two-column compare */
  .compare {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }}
  @media (max-width: 900px) {{ .compare {{ grid-template-columns: 1fr; }} }}

  /* Config card */
  .config-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); box-shadow: var(--shadow);
    overflow: hidden;
  }}
  .config-header {{
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 0.75rem;
  }}
  .config-badge {{
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .04em; padding: 0.2rem 0.6rem; border-radius: 9999px;
  }}
  .badge-with {{ background: var(--blue-bg); color: var(--blue); }}
  .badge-without {{ background: var(--gold-bg); color: var(--gold); }}

  /* Score summary in config header */
  .score-pill {{
    margin-left: auto;
    font-size: 0.8rem; font-weight: 700;
    padding: 0.2rem 0.7rem; border-radius: 9999px;
  }}
  .score-pass {{ background: var(--green-bg); color: var(--green); }}
  .score-fail {{ background: var(--red-bg); color: var(--red); }}

  /* Grading section */
  .grading {{ padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); }}
  .expectation {{
    display: flex; gap: 0.5rem; align-items: flex-start;
    padding: 0.3rem 0; font-size: 0.82rem; line-height: 1.45;
  }}
  .check {{ font-size: 0.9rem; flex-shrink: 0; margin-top: 1px; }}
  .exp-text {{ color: var(--text); }}
  .exp-evidence {{ color: var(--muted); font-size: 0.77rem; margin-top: 1px; }}

  /* File outputs */
  .files {{ padding: 0.75rem 1rem; display: flex; flex-direction: column; gap: 0.75rem; }}
  .file-card {{
    border: 1px solid var(--border); border-radius: 6px; overflow: hidden;
  }}
  .file-header {{
    background: var(--bg); padding: 0.4rem 0.75rem;
    font-size: 0.75rem; font-weight: 600; color: var(--muted);
    border-bottom: 1px solid var(--border); font-family: monospace;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .file-header a {{ color: var(--accent); text-decoration: none; font-size: 0.7rem; font-weight: 500; }}
  .file-header a:hover {{ text-decoration: underline; }}
  .file-body {{ padding: 0.75rem; }}
  
  /* Markdown rendered */
  .md-content {{
    font-size: 0.85rem; line-height: 1.65; max-height: 500px; overflow-y: auto;
  }}
  .md-content h1, .md-content h2 {{ font-size: 1rem; margin: 0.75rem 0 0.4rem; }}
  .md-content h3 {{ font-size: 0.9rem; margin: 0.6rem 0 0.3rem; }}
  .md-content p {{ margin: 0.3rem 0; }}
  .md-content ul, .md-content ol {{ padding-left: 1.2rem; margin: 0.3rem 0; }}
  .md-content table {{ border-collapse: collapse; font-size: 0.8rem; width: 100%; margin: 0.5rem 0; }}
  .md-content table td, .md-content table th {{ border: 1px solid var(--border); padding: 0.3rem 0.5rem; text-align: left; }}
  .md-content table th {{ background: var(--bg); font-weight: 600; }}
  .md-content code {{ background: #f3f2ee; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.8rem; }}
  .md-content pre {{ background: #f3f2ee; padding: 0.5rem; border-radius: 4px; overflow-x: auto; margin: 0.4rem 0; }}
  .md-content blockquote {{ border-left: 3px solid var(--border); padding-left: 0.75rem; color: var(--muted); }}
  
  /* Raw text */
  .raw-text {{ 
    font-size: 0.78rem; line-height: 1.5; white-space: pre-wrap;
    font-family: 'SF Mono', SFMono-Regular, Consolas, monospace;
    max-height: 400px; overflow-y: auto;
    background: #f8f7f3; padding: 0.5rem; border-radius: 4px;
  }}
  
  /* HTML iframe */
  .html-iframe {{
    width: 100%; height: 480px; border: none; border-radius: 4px;
    background: white;
  }}
  
  /* Binary download */
  .bin-link {{
    display: inline-flex; align-items: center; gap: 0.5rem;
    color: var(--accent); font-size: 0.85rem;
    padding: 0.5rem 0; text-decoration: none;
  }}
  .bin-link:hover {{ text-decoration: underline; }}
  
  /* Notes */
  .notes {{
    font-size: 0.82rem; line-height: 1.5; color: var(--muted);
    padding: 0.5rem 1rem; font-style: italic;
    border-top: 1px solid var(--border);
  }}
  
  /* Tab panels */
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <div class="header h1">📚 Validador de Ideias Literárias — Eval Review</div>
    <div class="sub">Comparação: com skill vs. sem skill</div>
  </div>
</div>

<div class="benchmark" id="benchmark-bar"></div>

<div class="tabs" id="tabs"></div>

<div class="content" id="panels"></div>

<script>
const DATA = {data_json};

// ---- Benchmark bar ----
function renderBenchmark(bm) {{
  const bar = document.getElementById('benchmark-bar');
  if (!bm || !bm.run_summary) {{ bar.style.display='none'; return; }}
  const withS = bm.run_summary.find(r => r.configuration === 'with_skill');
  const withoutS = bm.run_summary.find(r => r.configuration === 'without_skill');
  if (!withS || !withoutS) return;
  const delta = withS.pass_rate.mean - withoutS.pass_rate.mean;
  
  bar.innerHTML = `
    <div class="bm-item">
      <div class="bm-label">Com Skill</div>
      <div class="bm-val green">${{(withS.pass_rate.mean*100).toFixed(0)}}%</div>
    </div>
    <div class="bm-sep"></div>
    <div class="bm-item">
      <div class="bm-label">Sem Skill</div>
      <div class="bm-val red">${{(withoutS.pass_rate.mean*100).toFixed(0)}}%</div>
    </div>
    <div class="bm-sep"></div>
    <div class="bm-item">
      <div class="bm-label">Delta</div>
      <div class="bm-val green">+${{(delta*100).toFixed(0)}}pp</div>
    </div>
    <div class="bm-sep"></div>
    <div class="bm-item">
      <div class="bm-label">Cenários</div>
      <div class="bm-val">${{DATA.evals.length}}</div>
    </div>
  `;
}}

// ---- Tabs ----
function renderTabs() {{
  const tabs = document.getElementById('tabs');
  DATA.evals.forEach((ev, i) => {{
    const btn = document.createElement('button');
    btn.className = 'tab-btn' + (i===0?' active':'');
    btn.textContent = ev.label;
    btn.onclick = () => selectTab(i);
    tabs.appendChild(btn);
  }});
}}

function selectTab(idx) {{
  document.querySelectorAll('.tab-btn').forEach((b,i) => b.classList.toggle('active', i===idx));
  document.querySelectorAll('.tab-panel').forEach((p,i) => p.classList.toggle('active', i===idx));
}}

// ---- Panels ----
function renderPanels() {{
  const container = document.getElementById('panels');
  DATA.evals.forEach((ev, i) => {{
    const panel = document.createElement('div');
    panel.className = 'tab-panel' + (i===0?' active':'');
    panel.innerHTML = buildPanel(ev);
    container.appendChild(panel);
  }});
}}

function buildPanel(ev) {{
  const promptHtml = ev.with_skill.prompt
    ? `<div class="prompt-card"><div class="section-label">Prompt do usuário</div><div class="prompt-text">${{escHtml(ev.with_skill.prompt)}}</div></div>`
    : '';
  
  return `
    ${{promptHtml}}
    <div class="compare">
      ${{buildConfig(ev.with_skill, true)}}
      ${{buildConfig(ev.without_skill, false)}}
    </div>
  `;
}}

function buildConfig(run, isWithSkill) {{
  const passRate = run.grading ? run.grading.pass_rate : null;
  const pct = passRate !== null ? Math.round(passRate * 100) : null;
  const scoreClass = passRate !== null ? (passRate >= 0.8 ? 'score-pass' : 'score-fail') : '';
  const scoreHtml = pct !== null ? `<span class="score-pill ${{scoreClass}}">${{pct}}%</span>` : '';
  
  const badgeClass = isWithSkill ? 'badge-with' : 'badge-without';
  const badgeLabel = isWithSkill ? '✦ Com Skill' : '◇ Sem Skill';
  
  let gradingHtml = '';
  if (run.grading && run.grading.expectations) {{
    const items = run.grading.expectations.map(e => `
      <div class="expectation">
        <span class="check">${{e.passed ? '✅' : '❌'}}</span>
        <div>
          <div class="exp-text">${{escHtml(e.text)}}</div>
          ${{e.evidence ? `<div class="exp-evidence">${{escHtml(e.evidence)}}</div>` : ''}}
        </div>
      </div>
    `).join('');
    gradingHtml = `<div class="grading">${{items}}</div>`;
    if (run.grading.notes) {{
      gradingHtml += `<div class="notes">${{escHtml(run.grading.notes)}}</div>`;
    }}
  }}
  
  let filesHtml = '';
  if (run.files && run.files.length > 0) {{
    const fileCards = run.files.map(f => buildFileCard(f)).join('');
    filesHtml = `<div class="files">${{fileCards}}</div>`;
  }}
  
  return `
    <div class="config-card">
      <div class="config-header">
        <span class="config-badge ${{badgeClass}}">${{badgeLabel}}</span>
        ${{scoreHtml}}
      </div>
      ${{gradingHtml}}
      ${{filesHtml}}
    </div>
  `;
}}

function buildFileCard(file) {{
  let body = '';
  const dl = `<a href="#" onclick="downloadFile(event, this)" data-name="${{escHtml(file.name)}}" data-type="${{escHtml(file.type)}}" data-b64="${{file.b64||''}}">⬇ Download</a>`;
  
  if (file.type === 'md') {{
    const rendered = marked.parse(file.content || '');
    body = `<div class="md-content">${{rendered}}</div>`;
  }} else if (file.type === 'text') {{
    body = `<div class="raw-text">${{escHtml(file.content || '')}}</div>`;
  }} else if (file.type === 'html_iframe') {{
    const src = 'data:text/html;base64,' + file.b64;
    body = `<iframe class="html-iframe" src="${{src}}" sandbox="allow-scripts"></iframe>`;
  }} else if (file.type === 'image') {{
    body = `<img src="data:${{file.mime}};base64,${{file.b64}}" style="max-width:100%;border-radius:4px;" alt="${{escHtml(file.name)}}">`;
  }} else if (file.type === 'binary') {{
    body = `<a class="bin-link" href="#" onclick="downloadFile(event, this)" data-name="${{escHtml(file.name)}}" data-type="binary" data-b64="${{file.b64||''}}">⬇ Baixar ${{escHtml(file.name)}}</a>`;
  }} else {{
    body = `<div class="raw-text" style="color:var(--red)">Erro ao carregar arquivo</div>`;
  }}
  
  return `
    <div class="file-card">
      <div class="file-header">
        <span>${{escHtml(file.name)}}</span>
        ${{file.type !== 'binary' ? dl : ''}}
      </div>
      <div class="file-body">${{body}}</div>
    </div>
  `;
}}

function downloadFile(e, el) {{
  e.preventDefault();
  const name = el.dataset.name;
  const b64 = el.dataset.b64;
  if (!b64) return;
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  const blob = new Blob([bytes]);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
}}

function escHtml(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

// Init
renderBenchmark(DATA.benchmark);
renderTabs();
renderPanels();
</script>
</body>
</html>"""

if __name__ == "__main__":
    data = build_data()
    html = generate_html(data)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"✅ Viewer gerado: {OUTPUT}")
    print(f"   Evals incluídos: {len(data['evals'])}")
