from __future__ import annotations

import json
import re
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from r2s.domain import DiscoveryIR
from r2s.storage import list_runs, load_discovery

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
RUN_ID_RE = re.compile(r"^run_[0-9a-f]{20}$")
MAX_EVIDENCE_PAGE_SIZE = 200
MAX_UPDATE_REPORT_BYTES = 2 * 1024 * 1024


DASHBOARD_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Repo → Skill</title>
<style>
:root { color-scheme: dark; --bg:#101416; --panel:#171d20; --line:#2a363b;
  --text:#edf5f2; --muted:#9aacb0; --accent:#65d5a1; --warn:#f4bd65; --danger:#ff7d7d;
  --chip:#233137; --code:#0d1113; }
* { box-sizing:border-box; }
body { margin:0; background:radial-gradient(
  circle at top right,#1c3a35 0,transparent 34%
),var(--bg);
  color:var(--text); font:14px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,
  "Segoe UI",sans-serif; }
header { min-height:74px; display:flex; align-items:center; justify-content:space-between; gap:20px;
  padding:14px 24px; border-bottom:1px solid var(--line); background:rgba(16,20,22,.88); }
.brand { display:flex; align-items:center; gap:12px; font-weight:720; letter-spacing:-.02em;
  font-size:19px; }
.mark { width:31px; height:31px; display:grid; place-items:center; color:#082016; border-radius:9px;
  background:var(--accent); font-weight:900; }
.subtle { color:var(--muted); font-size:12px; }
button { appearance:none; border:1px solid var(--line); background:#1d282c; color:var(--text);
  border-radius:8px;
  padding:8px 12px; cursor:pointer; font:inherit; }
button:hover { border-color:var(--accent); }
.app { display:grid; grid-template-columns:minmax(250px,310px) 1fr; min-height:calc(100vh - 74px); }
aside { border-right:1px solid var(--line); padding:20px 14px; background:rgba(18,24,27,.75); }
.search { width:100%; padding:9px 10px; border:1px solid var(--line); border-radius:8px;
  color:var(--text);
  background:var(--code); font:inherit; outline:none; }
.search:focus { border-color:var(--accent); }
.run-list { display:grid; gap:8px; margin-top:14px; }
.run { width:100%; text-align:left; padding:12px; background:transparent; }
.run.active { background:#20342f; border-color:#397962; }
.run-title { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:650; }
.run-meta { display:flex; align-items:center; gap:6px; margin-top:5px; color:var(--muted);
  font-size:12px; }
main { padding:26px clamp(18px,4vw,52px); max-width:1300px; width:100%; margin:0 auto; }
.empty { display:grid; min-height:58vh; place-content:center; text-align:center;
  color:var(--muted); }
.empty strong { color:var(--text); font-size:20px; }
.hero { display:flex; justify-content:space-between; gap:16px; align-items:flex-start;
  margin-bottom:22px; }
h1 { margin:0; font-size:clamp(24px,3vw,35px); line-height:1.15; letter-spacing:-.035em; }
h2 { margin:0 0 10px; font-size:15px; }
.grid { display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:14px; }
.card { grid-column:span 12; border:1px solid var(--line); background:rgba(23,29,32,.9);
  border-radius:12px; padding:16px; }
.card.half { grid-column:span 6; }
.card.third { grid-column:span 4; }
.metric { font-size:29px; font-weight:720; letter-spacing:-.04em; }
.chips { display:flex; flex-wrap:wrap; gap:7px; }
.chip { display:inline-flex; align-items:center; max-width:100%; overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap;
  padding:3px 8px; border-radius:99px; background:var(--chip); color:#c8d8d5; font-size:12px; }
.good { color:var(--accent); } .warn { color:var(--warn); } .danger { color:var(--danger); }
.rows { display:grid; gap:9px; }
.row { display:flex; justify-content:space-between; gap:18px; padding-bottom:9px;
  border-bottom:1px solid #263136; }
.row:last-child { border:0; padding-bottom:0; }
.row .value { color:#d8e7e2; overflow-wrap:anywhere; text-align:right; }
.capability { border-top:1px solid #2b363a; padding:12px 0; }
.capability:first-child { border-top:0; padding-top:0; }
.capability-title { display:flex; justify-content:space-between; gap:10px; font-weight:650; }
.capability p { margin:4px 0 8px; color:var(--muted); }
code { background:var(--code); border:1px solid #263136; border-radius:5px; padding:1px 5px;
  color:#c8e6dc; }
.finding { padding:9px 0; border-top:1px solid #2b363a; }
.finding:first-child { border-top:0; padding-top:0; }
.finding-message { color:var(--muted); margin-top:2px; }
.evidence { overflow:auto; max-height:460px; }
table { width:100%; border-collapse:collapse; font-size:12px; }
th,td { padding:8px; text-align:left; vertical-align:top; border-bottom:1px solid #293438; }
th { color:var(--muted); font-weight:600; position:sticky; top:0; background:var(--panel); }
td { overflow-wrap:anywhere; }
.error { border-color:#813d3d; color:#ffd2d2; background:#301b1d; }
.hidden { display:none; }
@media (max-width:760px) { .app { grid-template-columns:1fr; }
  aside { border-right:0; border-bottom:1px solid var(--line); }
  main { padding:20px 16px; } .card.half,.card.third { grid-column:span 12; }
  header { padding:13px 16px; } }
</style>
</head>
<body>
<header>
  <div class="brand"><span class="mark">R</span><span>Repo → Skill</span>
    <span class="subtle">证据驱动编译器</span></div>
  <button id="refresh" type="button">刷新运行</button>
</header>
<div class="app">
  <aside>
    <div class="subtle" id="run-count">正在加载运行记录…</div>
    <input class="search" id="search" type="search" placeholder="筛选仓库或运行 ID" aria-label="筛选运行">
    <div class="run-list" id="runs"></div>
  </aside>
  <main id="detail"><section class="empty"><strong>选择一个 Discovery Run</strong>
    <span>查看真实快照、能力、证据、验证和更新差异。</span></section></main>
</div>
<script>
const state = { runs: [], selected: null };
const $ = (selector) => document.querySelector(selector);
function element(name, className, text) {
  const node = document.createElement(name);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function formatTime(value) {
  if (!value) return '未知时间';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}
function short(value, length = 12) {
  return value && value.length > length ? value.slice(0, length) + '…' : value || '—';
}
function appendChip(parent, value, extra) {
  parent.append(element('span', 'chip ' + (extra || ''), value));
}
async function request(path) {
  const response = await fetch(path, { cache: 'no-store' });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || '请求失败');
  return value;
}
function renderRuns() {
  const root = $('#runs');
  const term = $('#search').value.trim().toLowerCase();
  root.replaceChildren();
  const filtered = state.runs.filter((run) => {
    return [run.run_id, run.source_name, run.stage].join(' ').toLowerCase().includes(term);
  });
  $('#run-count').textContent = `共 ${state.runs.length} 个记录，显示 ${filtered.length} 个 Discovery Run`;
  for (const run of filtered) {
    const button = element('button', 'run' + (state.selected === run.run_id ? ' active' : ''));
    button.type = 'button';
    button.addEventListener('click', () => selectRun(run.run_id));
    button.append(element('div', 'run-title', run.source_name || run.run_id));
    const meta = element('div', 'run-meta');
    appendChip(meta, run.readiness || run.outcome || 'DISCOVERY');
    meta.append(document.createTextNode(short(run.run_id, 14)));
    button.append(meta);
    root.append(button);
  }
  if (!filtered.length) root.append(element('div', 'subtle', '没有匹配的 Discovery Run。'));
}
function card(title, className) {
  const section = element('section', 'card ' + (className || ''));
  section.append(element('h2', '', title));
  return section;
}
function row(label, value) {
  const root = element('div', 'row');
  root.append(element('span', 'subtle', label));
  root.append(element('span', 'value', value));
  return root;
}
function renderDetail(data) {
  const root = $('#detail');
  root.replaceChildren();
  const hero = element('div', 'hero');
  const heading = element('div');
  heading.append(element('div', 'subtle', short(data.run_id, 24)));
  heading.append(element('h1', '', data.discovery.snapshot.source_name));
  heading.append(element('div', 'subtle', data.discovery.snapshot.locator));
  hero.append(heading);
  const statuses = element('div', 'chips');
  appendChip(statuses, data.run.outcome || 'COMPLETED', 'good');
  appendChip(statuses, data.integrity, data.integrity === 'VERIFIED' ? 'good' : 'warn');
  hero.append(statuses);
  root.append(hero);

  const grid = element('div', 'grid');
  const capabilities = card('可验证能力', 'third');
  capabilities.append(element('div', 'metric', String(data.discovery.capabilities)));
  capabilities.append(element('div', 'subtle', '来自受支持的 Claim 与 Evidence'));
  grid.append(capabilities);
  const findings = card('发现项', 'third');
  const findingClass = 'metric ' + (data.discovery.findings ? 'warn' : 'good');
  findings.append(element('div', findingClass, String(data.discovery.findings)));
  findings.append(element('div', 'subtle', '错误会阻止 READY 交付'));
  grid.append(findings);
  const changes = card('更新差异', 'third');
  const updateCount = data.updates.length;
  changes.append(element('div', 'metric', String(updateCount)));
  changes.append(element('div', 'subtle', updateCount ? '已记录 Discovery 漂移' : '尚无更新记录'));
  grid.append(changes);

  const snapshot = card('快照', 'half');
  const rows = element('div', 'rows');
  const source = data.discovery.snapshot;
  rows.append(row('类型', source.kind));
  rows.append(row('请求 ref', source.requested_ref || '默认 HEAD'));
  rows.append(row('提交', source.resolved_commit_sha || '非 Git 快照'));
  rows.append(row('分析树', source.tree_sha256));
  rows.append(row('扫描策略', source.scan_policy_id));
  snapshot.append(rows);
  grid.append(snapshot);

  const classification = card('分类与运行', 'half');
  const classes = element('div', 'chips');
  for (const item of data.discovery.languages) appendChip(classes, item);
  for (const item of data.discovery.repository_types) appendChip(classes, item);
  if (!classes.childNodes.length) classes.append(element('span', 'subtle', '未分类'));
  classification.append(classes);
  const runRows = element('div', 'rows');
  runRows.style.marginTop = '15px';
  runRows.append(row('创建时间', formatTime(data.run.created_at)));
  runRows.append(row('子编译', String(data.compilations.length)));
  classification.append(runRows);
  grid.append(classification);

  const capabilityCard = card('能力', 'half');
  if (!data.capabilities.length) capabilityCard.append(element('div', 'subtle', '没有可生成的能力。'));
  for (const item of data.capabilities) {
    const capability = element('div', 'capability');
    const title = element('div', 'capability-title');
    title.append(element('span', '', item.title));
    const command = element('code', '', item.command || '无命令');
    title.append(command);
    capability.append(title);
    capability.append(element('p', '', item.intent));
    const chips = element('div', 'chips');
    appendChip(chips, item.support_level);
    for (const claim of item.claims) appendChip(chips, claim.predicate + ': ' + claim.status);
    capability.append(chips);
    capabilityCard.append(capability);
  }
  grid.append(capabilityCard);

  const findingCard = card('验证与发现', 'half');
  if (!data.findings.length) findingCard.append(element('div', 'good', '没有 Discovery 发现项。'));
  for (const item of data.findings) {
    const finding = element('div', 'finding');
    finding.append(element('strong', item.severity === 'error' ? 'danger' : 'warn', item.code));
    finding.append(element('div', 'finding-message', item.message));
    if (item.path) finding.append(element('div', 'subtle', item.path));
    findingCard.append(finding);
  }
  grid.append(findingCard);

  const updateCard = card('更新差异', 'half');
  if (!data.updates.length) {
    updateCard.append(element('div', 'subtle', '调用 `r2s update` 后，差异报告会显示在此处。'));
  }
  for (const update of data.updates) {
    const updateRow = element('div', 'finding');
    updateRow.append(element('strong', '', update.name));
    const report = update.report || {};
    const changed = (report.changed_capabilities || []).length;
    const added = (report.added_capabilities || []).length;
    const removed = (report.removed_capabilities || []).length;
    const message = `变化能力 ${changed}，新增 ${added}，移除 ${removed}`;
    updateRow.append(element('div', 'finding-message', message));
    updateCard.append(updateRow);
  }
  grid.append(updateCard);

  const evidenceCard = card('证据', 'half');
  const evidenceTop = element('div', 'hero');
  evidenceTop.style.marginBottom = '8px';
  evidenceTop.append(
    element('div', 'subtle', `总计 ${data.discovery.evidence} 条，可分页加载。`),
  );
  const load = element('button', '', '加载前 100 条证据');
  load.type = 'button';
  load.addEventListener(
    'click',
    () => loadEvidence(data.run_id, evidenceCard, load),
  );
  evidenceTop.append(load);
  evidenceCard.append(evidenceTop);
  grid.append(evidenceCard);
  root.append(grid);
}
async function loadEvidence(runId, cardRoot, button) {
  button.disabled = true;
  button.textContent = '正在加载…';
  try {
    const path = '/api/runs/' + encodeURIComponent(runId) + '/evidence?limit=100';
    const data = await request(path);
    const wrap = element('div', 'evidence');
    const table = element('table');
    const header = element('tr');
    for (const label of ['类型', '来源', '定位', '置信度']) {
      header.append(element('th', '', label));
    }
    table.append(header);
    for (const item of data.items) {
      const line = element('tr');
      line.append(element('td', '', item.kind));
      line.append(element('td', '', item.source.path));
      line.append(element('td', '', item.source.pointer));
      line.append(element('td', '', String(item.confidence)));
      table.append(line);
    }
    wrap.append(table);
    cardRoot.append(wrap);
    button.remove();
  } catch (error) {
    button.disabled = false;
    button.textContent = '重新加载证据';
    cardRoot.append(element('div', 'finding-message danger', error.message));
  }
}
async function selectRun(runId) {
  state.selected = runId;
  renderRuns();
  $('#detail').replaceChildren(
    element('section', 'empty', '正在验证并加载运行产物…'),
  );
  try {
    renderDetail(await request('/api/runs/' + encodeURIComponent(runId)));
  } catch (error) {
    const panel = element('section', 'card error');
    panel.append(element('h2', '', '无法加载运行产物'));
    panel.append(element('div', '', error.message));
    $('#detail').replaceChildren(panel);
  }
}
async function refresh() {
  try {
    const payload = await request('/api/runs');
    state.runs = payload.runs;
    if (state.selected && !state.runs.some((run) => run.run_id === state.selected)) {
      state.selected = null;
    }
    renderRuns();
  } catch (error) {
    $('#run-count').textContent = error.message;
  }
}
$('#refresh').addEventListener('click', refresh);
$('#search').addEventListener('input', renderRuns);
refresh();
</script>
</body>
</html>
"""


def validate_ui_host(host: str) -> str:
    if host not in LOOPBACK_HOSTS:
        raise ValueError("UI_HOST_MUST_BE_LOOPBACK")
    return host


def _run_root(output_root: Path, run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("UI_RUN_ID_INVALID")
    root = (output_root / run_id).resolve()
    try:
        root.relative_to(output_root.resolve())
    except ValueError as exc:
        raise ValueError("UI_RUN_PATH_ESCAPE") from exc
    return root


def _discovery_summary(run_root: Path) -> dict[str, Any]:
    discovery = load_discovery(run_root)
    return {
        "run_id": run_root.name,
        "source_name": discovery.source_name,
        "languages": discovery.languages,
        "repository_types": discovery.repository_types,
        "capabilities": len(discovery.capabilities),
        "findings": len(discovery.findings),
    }


def _discovery_runs(output_root: Path) -> list[dict[str, Any]]:
    indexed = {item["run_id"]: item for item in list_runs(output_root)}
    summaries: list[dict[str, Any]] = []
    if not output_root.is_dir():
        return summaries
    for path in sorted(output_root.iterdir()):
        if not path.is_dir() or not RUN_ID_RE.fullmatch(path.name):
            continue
        try:
            summary = _discovery_summary(path)
        except ValueError as exc:
            summary = {
                "run_id": path.name,
                "source_name": "Invalid discovery artifact",
                "languages": [],
                "repository_types": [],
                "capabilities": 0,
                "findings": 1,
                "integrity_error": str(exc),
            }
        summary.update(indexed.get(path.name, {}))
        summaries.append(summary)
    return sorted(
        summaries,
        key=lambda item: (str(item.get("created_at", "")), item["run_id"]),
        reverse=True,
    )


def _capability_payload(discovery: DiscoveryIR) -> list[dict[str, Any]]:
    claims = {claim.id: claim for claim in discovery.claims}
    result: list[dict[str, Any]] = []
    for capability in discovery.capabilities:
        capability_claims = [
            claims[claim_id] for claim_id in capability.claim_ids if claim_id in claims
        ]
        command = next(
            (
                str(claim.object.get("command", ""))
                for claim in capability_claims
                if claim.predicate == "provides_cli"
            ),
            None,
        )
        result.append(
            {
                "id": capability.id,
                "title": capability.title,
                "intent": capability.intent,
                "support_level": capability.support_level,
                "command": command,
                "claims": [
                    {
                        "id": claim.id,
                        "predicate": claim.predicate,
                        "status": claim.status,
                        "confidence": claim.confidence,
                        "object": claim.object,
                        "evidence_ids": list(claim.evidence_ids),
                    }
                    for claim in capability_claims
                ],
            }
        )
    return result


def _update_reports(run_root: Path) -> list[dict[str, Any]]:
    updates_root = run_root / "updates"
    if not updates_root.is_dir() or updates_root.is_symlink():
        return []
    reports: list[dict[str, Any]] = []
    for path in sorted(updates_root.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            continue
        if path.stat().st_size > MAX_UPDATE_REPORT_BYTES:
            continue
        try:
            reports.append({"name": path.name, "report": json.loads(path.read_text())})
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
    return reports


def _detail_payload(output_root: Path, run_id: str) -> dict[str, Any]:
    run_root = _run_root(output_root, run_id)
    discovery = load_discovery(run_root)
    records = list_runs(output_root)
    run = next((item for item in records if item["run_id"] == run_id), {})
    compilations = [item for item in records if item.get("parent_run_id") == run_id]
    return {
        "run_id": run_id,
        "integrity": "VERIFIED",
        "run": run,
        "discovery": {
            "snapshot": asdict(discovery.snapshot),
            "languages": discovery.languages,
            "repository_types": discovery.repository_types,
            "capabilities": len(discovery.capabilities),
            "findings": len(discovery.findings),
            "evidence": len(discovery.evidence),
        },
        "capabilities": _capability_payload(discovery),
        "findings": [asdict(item) for item in discovery.findings],
        "compilations": compilations,
        "updates": _update_reports(run_root),
    }


def _evidence_payload(
    output_root: Path,
    run_id: str,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    discovery = load_discovery(_run_root(output_root, run_id))
    offset = max(offset, 0)
    limit = min(max(limit, 1), MAX_EVIDENCE_PAGE_SIZE)
    items = discovery.evidence[offset : offset + limit]
    return {
        "offset": offset,
        "limit": limit,
        "total": len(discovery.evidence),
        "items": [
            {
                "id": item.id,
                "kind": item.kind,
                "normalized_value": item.normalized_value,
                "source": asdict(item.source),
                "extractor": item.extractor,
                "confidence": item.confidence,
            }
            for item in items
        ],
    }


class R2SUIRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def output_root(self) -> Path:
        return getattr(self.server, "output_root")

    def _send_json(self, status: HTTPStatus, value: Any) -> None:
        content = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_html(self) -> None:
        content = DASHBOARD_HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", _content_security_policy())
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            self._send_html()
            return
        try:
            if parsed.path == "/api/runs":
                self._send_json(HTTPStatus.OK, {"runs": _discovery_runs(self.output_root)})
                return
            match = re.fullmatch(r"/api/runs/(run_[0-9a-f]{20})", parsed.path)
            if match is not None:
                self._send_json(HTTPStatus.OK, _detail_payload(self.output_root, match.group(1)))
                return
            match = re.fullmatch(r"/api/runs/(run_[0-9a-f]{20})/evidence", parsed.path)
            if match is not None:
                query = parse_qs(parsed.query)
                offset = int(query.get("offset", ["0"])[0])
                limit = int(query.get("limit", ["100"])[0])
                self._send_json(
                    HTTPStatus.OK,
                    _evidence_payload(self.output_root, match.group(1), offset, limit),
                )
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "UI_ROUTE_NOT_FOUND"})
        except ValueError as exc:
            self._send_json(HTTPStatus.CONFLICT, {"error": str(exc)})

    def do_POST(self) -> None:
        self._send_json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "UI_READ_ONLY"})


def _content_security_policy() -> str:
    return (
        "default-src 'self'; base-uri 'none'; connect-src 'self'; form-action 'none'; "
        "frame-ancestors 'none'; img-src 'self' data:; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'"
    )


def make_server(output_root: Path, host: str, port: int) -> ThreadingHTTPServer:
    validate_ui_host(host)
    if not 0 <= port <= 65535:
        raise ValueError("UI_PORT_INVALID")
    server = ThreadingHTTPServer((host, port), R2SUIRequestHandler)
    setattr(server, "output_root", output_root.resolve())
    return server
