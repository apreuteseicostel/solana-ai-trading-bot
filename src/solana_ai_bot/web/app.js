const $ = (id) => document.getElementById(id);
let data = null;
let busy = false;
const titles = {
  overview: ['Research overview', 'Follow observations. Inspect decisions. Measure the experiment.'],
  signals: ['SIGNAL history', 'Review historic simulated decisions; not live trade alerts.'],
  'paper-auto': ['PAPER AUTO status', 'Inspect bounded paper simulation and its unknown process health.'],
  positions: ['Paper positions', 'Inspect simulated exposure and the freshness of liquidation marks.'],
  wallets: ['Wallet observations', 'Inspect recorded activity with its original data source.'],
  decisions: ['Decision journal', 'Trace simulated fills and rejected signals to their reasons.'],
  limits: ['Experiment limits', 'Review the recorded assumptions behind this paper book.'],
};
const money = (raw) => raw == null ? 'Unknown' : (raw / 1e6).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 4});
const short = (v) => !v ? '—' : String(v).length > 21 ? String(v).slice(0, 10) + '…' + String(v).slice(-7) : String(v);
const human = (v) => String(v ?? 'Unknown').replaceAll('_', ' ');
const date = (v) => v == null ? 'Unavailable' : new Date(v * 1000).toLocaleString();
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = String(text);
  if (cls) node.className = cls;
  return node;
}
function keyValue(parent, label, value) {
  const row = el('div'); row.append(el('dt', label), el('dd', value)); parent.append(row);
}
function table(id, headers, rows, empty) {
  const container = $(id); container.replaceChildren();
  if (!rows.length) { container.append(el('div', empty, 'empty')); return; }
  const t = el('table'); const head = el('thead'); const tr = el('tr');
  headers.forEach(h => tr.append(el('th', h))); head.append(tr); t.append(head);
  const body = el('tbody');
  rows.forEach(row => {
    const tr = el('tr');
    row.forEach(cell => {
      const td = el('td');
      if (cell instanceof Node) td.append(cell); else td.textContent = String(cell ?? '—');
      tr.append(td);
    }); body.append(tr);
  }); t.append(body); container.append(t);
}
function identifier(value) { const n = el('span', short(value), 'mono'); n.title = String(value ?? ''); return n; }
function status(value) { return el('span', value === 'filled' ? 'Paper fill' : human(value), `pill ${value === 'filled' ? 'filled' : value === 'rejected' ? 'rejected' : ''}`); }
function decisionRows(items) { return items.map(d => [identifier(d.signature), human(d.source), status(d.status), d.side || '—', human(d.reason)]); }
function visibleDecisions() {
  if (!data) return [];
  const query = $('search').value.toLowerCase().trim();
  return data.recent_decisions.filter(d => ($('status').value === 'all' || d.status === $('status').value)
    && [d.signature, d.wallet, d.reason, d.source, d.side].some(v => String(v ?? '').toLowerCase().includes(query)));
}
function renderJournal() {
  const visible = visibleDecisions();
  table('decisions-table', ['Signature', 'Data source', 'Status', 'Side', 'Reason'], decisionRows(visible), 'No decisions match these filters.');
  $('decision-count').textContent = `${visible.length} of ${data.recent_decisions.length} loaded decisions${data.decisions_truncated ? ' · Latest 200 only; older decisions remain in SQLite.' : ''}`;
}
function render() {
  const s = data.state;
  $('metrics').replaceChildren();
  const cards = [
    ['Paper cash', s.cash_raw, 'USDC', 'Available simulated balance'],
    ['Realized paper P&L', s.realized_pnl_raw, 'USDC', 'Closed simulated positions only'],
    ['Liquidation equity', data.equity_raw, 'USDC', data.equity_raw == null ? 'Missing or stale liquidation marks' : 'Cash + fresh liquidation estimates'],
    ['Max observed drawdown', s.max_drawdown_bps / 100, '%', 'Recorded paper-book peak to trough'],
  ];
  cards.forEach(([label, value, unit, note], index) => {
    const card = el('article', null, 'metric');
    const figure = el('div', index === 3 ? value.toFixed(2) : money(value), `metric-value ${index === 1 ? value < 0 ? 'negative' : 'positive' : ''}`);
    if (value != null) figure.append(el('small', unit));
    card.append(el('div', label, 'metric-label'), figure, el('div', note, 'metric-note')); $('metrics').append(card);
  });
  const mode = s.dataset_mode || 'no observations';
  $('provenance').replaceChildren(el('span', 'i', 'notice-icon'), el('span',
    `${human(mode).toUpperCase()} · ${mode === 'forward_observations' ? 'Forward observations remain unverified; all fills are simulated.' : 'Demo and replay observations are not live market performance.'} ${s.halted ? 'New paper exposure halted by the engine.' : 'Recorded paper risk limits apply.'}`));
  const total = data.recent_decisions.length;
  const filled = data.recent_decisions.filter(d => d.status === 'filled').length;
  const rejected = data.recent_decisions.filter(d => d.status === 'rejected').length;
  const other = total - filled - rejected;
  $('outcomes').replaceChildren();
  const counts = el('div', null, 'outcome-total'); counts.append(el('strong', total), el('span', data.decisions_truncated ? 'latest 200 decisions' : 'recorded decisions')); $('outcomes').append(counts);
  // SVG attributes avoid inline styles under the restrictive content policy.
  const ns = 'http://www.w3.org/2000/svg'; const bar = document.createElementNS(ns, 'svg');
  bar.setAttribute('viewBox', '0 0 100 4'); bar.setAttribute('role', 'img'); bar.setAttribute('aria-label', `${filled} simulated fills, ${rejected} rejected, ${other} other`);
  let offset = 0;
  [[filled, '#98edc4'], [rejected, '#7182a0'], [other, '#c0a879']].forEach(([count, color]) => {
    const rect = document.createElementNS(ns, 'rect'); const width = total ? count * 100 / total : 0;
    for (const [key, value] of Object.entries({x: offset, y: 0, width, height: 4, fill: color})) rect.setAttribute(key, String(value));
    offset += width; bar.append(rect);
  }); $('outcomes').append(bar);
  $('outcome-legend').replaceChildren();
  [[filled, 'Paper fills', ''], [rejected, 'Rejected', 'legend-reject'], [other, 'Other', 'legend-other']].forEach(([count, label, cls]) => {
    const n = el('span'); n.append(el('span', null, `legend-dot ${cls}`), document.createTextNode(`${label} · ${count}`)); $('outcome-legend').append(n);
  });
  $('observability').replaceChildren();
  keyValue($('observability'), 'Collector health', 'Unknown · no heartbeat');
  keyValue($('observability'), 'Last stored observation', date(data.latest_observed_at));
  keyValue($('observability'), 'Observation scope', 'Whole database · all runs');
  keyValue($('observability'), 'Recorded provider requests', Object.values(data.provider_usage.requests_by_host).reduce((a, b) => a + b, 0));
  keyValue($('observability'), 'API billing', 'Unknown · excluded from P&L');
  table('recent-table', ['Signature', 'Data source', 'Status', 'Side', 'Reason'], decisionRows(data.recent_decisions.slice(0, 5)), 'No decisions recorded. Run a paper experiment to populate this journal.');
  table('positions-table', ['Mint', 'Wallet', 'Quantity · atomic units', 'Cost · USDC', 'Liquidation · USDC', 'Quote time'], Object.values(s.positions).map(p => [identifier(p.mint), identifier(p.wallet), String(p.quantity_raw), money(p.cost_raw), p.marked_at != null && data.generated_at - p.marked_at >= 0 && data.generated_at - p.marked_at <= data.config.max_quote_age_seconds ? money(p.liquidation_raw) : 'Unknown · stale/missing', date(p.marked_at)]), 'No open paper positions in this experiment.');
  table('wallets-table', ['Wallet', 'Signature', 'Kind', 'Data source', 'Observed at'], data.observations.map(o => [identifier(o.wallet), identifier(o.signature), human(o.kind), human(o.source), date(o.observed_at)]), 'No wallet observations stored.');
  table('signals-table',
    ['Signature', 'Recorded at', 'Provenance', 'Outcome', 'Side', 'Reason'],
    (data.signal_feed || []).map(row => [
      identifier(row.signature), date(row.at), human(row.source),
      human(row.classification), row.side || '—', human(row.reason),
    ]),
    'No recorded SIGNAL history. This page does not generate live buy alerts.'
  );
  $('paper-auto-info').replaceChildren();
  keyValue($('paper-auto-info'), 'Mode', 'PAPER ONLY · bounded CLI session');
  keyValue($('paper-auto-info'), 'Process health', 'Unknown · no heartbeat or scheduler');
  keyValue($('paper-auto-info'), 'Started from dashboard', 'Not supported · read-only');
  keyValue($('paper-auto-info'), 'Live order execution', 'Disabled');
  keyValue($('paper-auto-info'), 'Dataset origin', human(mode));
  keyValue($('paper-auto-info'), 'Paper entry halt', s.halted ? 'Latched by risk engine' : 'Not latched in recorded run');
  keyValue($('paper-auto-info'), 'Current liquidation equity', data.equity_raw == null ? 'Unknown · no fresh marks' : money(data.equity_raw) + ' USDC');
  $('config').replaceChildren();
  Object.entries(data.config).forEach(([key, value]) => keyValue($('config'), human(key), key.endsWith('_raw') ? `${money(value)} USDC` : key.endsWith('_bps') ? `${value / 100}%` : String(value)));
  $('updated').textContent = `Snapshot · ${date(data.generated_at)}${data.observations_truncated ? ' · Latest 200 observations shown' : ''}`;
  renderJournal();
}
async function refresh() {
  if (busy) return;
  busy = true; $('refresh').disabled = true; $('error').hidden = true;
  const previous = data;
  try {
    const query = $('run').value ? `?run_id=${encodeURIComponent($('run').value)}` : '';
    const response = await fetch(`/api/snapshot${query}`, {cache: 'no-store', signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error('Snapshot unavailable');
    const next = await response.json();
    if (next.schema_version !== 1 || !Array.isArray(next.recent_decisions) || !Array.isArray(next.signal_feed) || !next.paper_auto || !next.state) throw new Error('Unsupported snapshot');
    data = next;
    $('run').replaceChildren(...data.runs.map(run => { const option = el('option', run); option.value = run; return option; }));
    $('run').value = data.run_id;
    render(); $('dashboard').hidden = false;
  } catch {
    data = previous;
    $('error').textContent = data ? 'Refresh failed. The dashboard still shows the previous snapshot; check its timestamp. Collection health is unknown.' : 'No snapshot available. Start with --demo or select an existing intelligence SQLite database containing a paper experiment.';
    $('error').hidden = false;
    if (!data) $('provenance').replaceChildren(el('span', 'No experiment data loaded. All functions are read-only.'));
  } finally { busy = false; $('refresh').disabled = false; $('loading').hidden = true; }
}
function route() {
  const key = Object.hasOwn(titles, location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
  document.querySelectorAll('.view').forEach(n => n.hidden = n.id !== key);
  document.querySelectorAll('[data-view]').forEach(n => { n.classList.toggle('active', n.dataset.view === key); if (n.dataset.view === key) n.setAttribute('aria-current', 'page'); else n.removeAttribute('aria-current'); });
  $('page-title').textContent = titles[key][0]; $('breadcrumb').textContent = titles[key][0]; $('page-description').textContent = titles[key][1];
}
$('refresh').addEventListener('click', refresh);
$('run').addEventListener('change', refresh);
$('search').addEventListener('input', () => data && renderJournal());
$('status').addEventListener('change', () => data && renderJournal());
$('export').addEventListener('click', () => {
  if (!data) return;
  const payload = {run_id: data.run_id, mode: 'paper', generated_at: data.generated_at, source: data.state.dataset_mode, truncated: data.decisions_truncated, decisions: visibleDecisions()};
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'}));
  const link = el('a'); link.href = url; link.download = 'paper-decisions.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
window.addEventListener('hashchange', route); route(); refresh();
