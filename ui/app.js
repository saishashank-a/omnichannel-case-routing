const PAGE_SIZE = 100;
const TICKET_FIELDS = ['ticket_id','customer_id','channel_id','intent_id','language_code','urgency','priority','created_at','after_hours','status','current_queue_id','transfer_count','escalation_count','reopen_count','first_response_at','resolved_at','csat'];
const DATA = new URLSearchParams(location.search).get('data') || '../data/starter';
const base = new URL(DATA.replace(/\/$/, '') + '/', location.href);
const tables = ['ticket', 'assignment_event', 'sla_event', 'message', 'agent'];
const data = { ticket: [], assignment_event: [], sla_event: [], message: [], agent: [], metrics: {}, ground_truth: [], findings: [] };
const ticketById = new Map();
const eventsByTicket = new Map();
const agentById = new Map();
const expectedByTicket = new Map();
let page = 0;
let visibleTickets = [];

const esc = value => String(value ?? '—').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);
const val = value => value === null || value === undefined || value === '' ? '—' : esc(value);
const rows = value => Array.isArray(value) ? value.filter(x => x && typeof x === 'object') : [];
const byId = (map, key) => map.get(key) || [];
const stamp = value => value ? esc(new Date(value).toLocaleString()) : '—';
const pctClass = n => Number(n) >= 90 ? 'good' : Number(n) >= 75 ? 'warn' : 'bad';

async function load(path, fallback, label) {
  try {
    const response = await fetch(new URL(path, base));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    document.querySelector('#messages').insertAdjacentHTML('beforeend', `<div class="message error">Could not load ${esc(label)} (${esc(path)}): ${esc(error.message)}</div>`);
    return fallback;
  }
}

async function start() {
  document.querySelector('#dataset-label').textContent = `Data: ${decodeURIComponent(DATA)}`;
  const requests = tables.map(name => load(`json/${name}.json`, [], `${name}.json`));
  requests.push(load('metrics.json', {}, 'metrics.json'));
  requests.push(load('ground_truth/ground_truth.json', [], 'ground_truth.json'));
  requests.push(load('validation/findings.json', [], 'findings.json'));
  const results = await Promise.all(requests);
  tables.forEach((name, i) => data[name] = rows(results[i]));
  data.metrics = results[5] && typeof results[5] === 'object' && !Array.isArray(results[5]) ? results[5] : {};
  data.ground_truth = rows(results[6]);
  data.findings = rows(results[7]);
  data.ticket.forEach(ticket => { if (ticket.ticket_id) ticketById.set(ticket.ticket_id, ticket); });
  data.agent.forEach(agent => { if (agent.agent_id) agentById.set(agent.agent_id, agent); });
  for (const table of ['assignment_event', 'sla_event', 'message']) {
    data[table].forEach(item => {
      if (!item.ticket_id) return;
      if (!eventsByTicket.has(item.ticket_id)) eventsByTicket.set(item.ticket_id, []);
      eventsByTicket.get(item.ticket_id).push({ ...item, source: table });
    });
  }
  data.ground_truth.forEach(item => {
    if (!item.ticket_id) return;
    if (!expectedByTicket.has(item.ticket_id)) expectedByTicket.set(item.ticket_id, []);
    expectedByTicket.get(item.ticket_id).push(item);
  });
  renderOverview(); renderTickets(); renderAnomalies(); bindTabs();
}

function bindTabs() {
  document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => showTab(button.dataset.tab)));
}
function showTab(name) {
  document.querySelectorAll('.tab').forEach(button => button.classList.toggle('active', button.dataset.tab === name));
  document.querySelectorAll('.screen').forEach(section => section.classList.toggle('active', section.id === name));
}
function card(label, value) { return `<div class="card"><span class="label">${esc(label)}</span><strong>${val(value)}</strong></div>`; }
function table(headers, body) {
  return `<div class="table-wrap"><table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${body || `<tr><td colspan="${headers.length}" class="empty">No data available</td></tr>`}</tbody></table></div>`;
}
function renderOverview() {
  const m = data.metrics;
  const detected = Array.isArray(m.anomaly_detection) ? m.anomaly_detection.reduce((n, x) => n + (Number(x.found) || 0), 0) : data.findings.length;
  const sla = rows(m.sla_attainment).map(x => `<tr><td>${val(x.channel_id)}</td><td>${val(x.priority)}</td><td>${val(x.met)}</td><td>${val(x.breached)}</td><td class="pct ${pctClass(x.pct)}">${x.pct == null ? '—' : `${esc(x.pct)}%`}</td></tr>`).join('');
  const rateRows = m.rates && typeof m.rates === 'object' ? Object.entries(m.rates).map(([k,v]) => `<tr><td>${esc(k.replaceAll('_',' '))}</td><td>${val(v)}</td></tr>`).join('') : '';
  const waits = m.queue_wait_minutes && typeof m.queue_wait_minutes === 'object' ? Object.entries(m.queue_wait_minutes).map(([k,v]) => `<tr><td>${esc(k.toUpperCase())}</td><td>${val(v)} min</td></tr>`).join('') : '';
  const csat = m.csat_distribution && typeof m.csat_distribution === 'object' ? Object.entries(m.csat_distribution).map(([k,v]) => `<div class="bar-row"><span>${esc(k)} star</span><div class="bar"><i style="width:${barWidth(v,m.csat_distribution)}%"></i></div><strong>${val(v)}</strong></div>`).join('') : '';
  const peaks = rows(m.peak_concurrency).map(x => `<tr><td>${val(x.agent_id)}</td><td>${val(x.channel_id)}</td><td>${val(x.peak)}</td><td>${val(x.limit)}</td></tr>`).join('');
  const details = Object.keys(m).filter(k => !['sla_attainment','rates','queue_wait_minutes','csat_distribution','peak_concurrency','anomaly_detection'].includes(k)).map(k => `<div class="summary-item">${esc(k.replaceAll('_',' '))}<strong>${val(typeof m[k] === 'object' ? JSON.stringify(m[k]) : m[k])}</strong></div>`).join('');
  document.querySelector('#overview').innerHTML = `<div class="cards">${card('Tickets',data.ticket.length)}${card('Messages',data.message.length)}${card('Agents',data.agent.length)}${card('Anomalies · expected / found',`${data.ground_truth.length} / ${detected}`)}</div>
    <div class="panel"><h2>SLA attainment</h2>${table(['Channel','Priority','Met','Breached','Attainment'],sla)}</div>
    <div class="two-col"><div class="panel"><h2>Rates</h2>${table(['Measure','Value'],rateRows)}</div><div class="panel"><h2>Queue wait</h2>${table(['Percentile','Minutes'],waits)}</div></div>
    <div class="two-col"><div class="panel"><h2>CSAT distribution</h2>${csat ? `<div class="bars">${csat}</div>` : '<div class="empty">No data available</div>'}</div><div class="panel"><h2>Peak concurrency</h2>${table(['Agent','Channel','Peak','Limit'],peaks)}</div></div>${details ? `<div class="panel"><h2>Other metrics</h2><div class="summary-grid">${details}</div></div>` : ''}`;
}
function barWidth(value, group) {
  const max = Math.max(1, ...Object.values(group).map(Number).filter(Number.isFinite));
  return Math.min(100, Math.max(0, Number(value) / max * 100));
}

function renderTickets() {
  const options = (field, label) => `<select id="filter-${field}"><option value="">All ${label}</option>${[...new Set(data.ticket.map(t => t[field]).filter(v => v != null))].sort().map(v => `<option>${esc(v)}</option>`).join('')}</select>`;
  document.querySelector('#tickets').innerHTML = `<div class="filters">${options('channel_id','channels')}${options('priority','priorities')}${options('status','statuses')}<input id="ticket-search" type="search" placeholder="Search ticket ID"><label class="check"><input type="checkbox" id="has-transfer"> Transfer</label><label class="check"><input type="checkbox" id="has-escalation"> Escalation</label><label class="check"><input type="checkbox" id="is-reopened"> Reopened</label><label class="check"><input type="checkbox" id="after-hours"> After hours</label><label class="check"><input type="checkbox" id="has-anomaly"> Anomaly</label></div><div id="ticket-detail"></div><div class="panel table-card" id="ticket-list"></div>`;
  document.querySelectorAll('.filters select,.filters input').forEach(el => el.addEventListener(el.type === 'search' ? 'input' : 'change', () => { page = 0; updateTicketList(); }));
  updateTicketList();
}
function filterTickets() {
  const get = id => document.getElementById(id);
  return data.ticket.filter(t => (!get('filter-channel_id').value || t.channel_id === get('filter-channel_id').value)
    && (!get('filter-priority').value || t.priority === get('filter-priority').value)
    && (!get('filter-status').value || t.status === get('filter-status').value)
    && (!get('ticket-search').value || String(t.ticket_id || '').toLowerCase().includes(get('ticket-search').value.toLowerCase()))
    && (!get('has-transfer').checked || Number(t.transfer_count) > 0)
    && (!get('has-escalation').checked || Number(t.escalation_count) > 0)
    && (!get('is-reopened').checked || Number(t.reopen_count) > 0 || t.status === 'REOPENED')
    && (!get('after-hours').checked || Number(t.after_hours) === 1)
    && (!get('has-anomaly').checked || expectedByTicket.has(t.ticket_id)));
}
function updateTicketList() {
  visibleTickets = filterTickets();
  const maxPage = Math.max(0, Math.ceil(visibleTickets.length / PAGE_SIZE) - 1);
  page = Math.min(page, maxPage);
  const shown = visibleTickets.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const body = shown.map(t => `<tr data-id="${esc(t.ticket_id)}"><td>${val(t.ticket_id)}</td><td>${val(t.channel_id)}</td><td>${val(t.priority)}</td><td>${val(t.status)}</td><td>${val(t.current_queue_id)}</td><td>${val(t.transfer_count)}</td><td>${val(t.escalation_count)}</td><td>${expectedByTicket.has(t.ticket_id) ? 'Yes' : '—'}</td></tr>`).join('');
  document.querySelector('#ticket-list').innerHTML = `${table(['Ticket','Channel','Priority','Status','Queue','Transfers','Escalations','Anomaly'],body)}<div class="pagination"><span>${visibleTickets.length ? `${page*PAGE_SIZE+1}–${Math.min((page+1)*PAGE_SIZE,visibleTickets.length)} of ${visibleTickets.length}` : '0 tickets'}</span><div><button id="prev-page" ${page===0?'disabled':''}>Previous</button> <button id="next-page" ${page>=maxPage?'disabled':''}>Next</button></div></div>`;
  document.querySelectorAll('#ticket-list tr[data-id]').forEach(row => row.addEventListener('click', () => openTicket(row.dataset.id)));
  document.querySelector('#prev-page').addEventListener('click', () => { page--; updateTicketList(); });
  document.querySelector('#next-page').addEventListener('click', () => { page++; updateTicketList(); });
}
function openTicket(id) {
  const ticket = ticketById.get(id);
  if (!ticket) return;
  const badges = byId(expectedByTicket,id).map(x => `<span class="badge">${val(x.issue_type)}</span>`).join('');
  const fields = TICKET_FIELDS.map(key => `<div class="field">${esc(key.replaceAll('_',' '))}<strong>${val(ticket[key])}</strong></div>`).join('');
  const rank = { assignment_event: 0, sla_event: 1, message: 2 };
  const timeline = byId(eventsByTicket,id).slice().sort((a,b) => String(a.ts || '').localeCompare(String(b.ts || '')) || rank[a.source]-rank[b.source] || (Number(a.seq)||0)-(Number(b.seq)||0));
  const eventHtml = timeline.map(item => {
    const kind = item.source === 'assignment_event' ? 'assignment' : item.source === 'sla_event' ? 'sla' : 'message';
    const agent = item.agent_id ? (agentById.get(item.agent_id)?.display_name || item.agent_id) : null;
    const meta = [item.event_type, item.author_type, agent, item.queue_id, item.translation_flag != null ? `Translation: ${item.translation_flag}` : null, item.due_at ? `Due: ${stamp(item.due_at)}` : null].filter(Boolean).map(esc).join(' · ');
    const body = item.body ?? item.reason ?? '';
    return `<div class="event ${kind}"><time>${stamp(item.ts)}</time><div>${meta || esc(item.source.replace('_',' '))}</div>${body ? `<p>${esc(body)}</p>` : ''}</div>`;
  }).join('');
  document.querySelector('#ticket-detail').innerHTML = `<div class="panel detail"><div class="detail-head"><div><h2>${val(ticket.ticket_id)} ${badges}</h2><span class="muted">Ticket detail</span></div><button class="close" id="close-detail">Close</button></div><div class="field-grid">${fields}</div><h2>Timeline</h2><div class="timeline">${eventHtml || '<div class="empty">No events available</div>'}</div></div>`;
  document.querySelector('#close-detail').addEventListener('click', () => document.querySelector('#ticket-detail').replaceChildren());
}

function renderAnomalies() {
  const gt = data.ground_truth, found = data.findings;
  const key = x => `${x.issue_type ?? ''}\u0000${x.ticket_id ?? ''}`;
  const gCounts = new Map(), fCounts = new Map();
  gt.forEach(x => gCounts.set(key(x),(gCounts.get(key(x))||0)+1));
  found.forEach(x => fCounts.set(key(x),(fCounts.get(key(x))||0)+1));
  const allKeys = [...new Set([...gCounts.keys(),...fCounts.keys()])];
  const issueTypes = [...new Set([...gt,...found].map(x => x.issue_type).filter(Boolean))].sort();
  const summary = issueTypes.map(type => {
    const keys = allKeys.filter(k => k.startsWith(`${type}\u0000`));
    const caught = keys.filter(k => gCounts.has(k) && fCounts.has(k)).length;
    const missed = keys.filter(k => gCounts.has(k) && !fCounts.has(k)).length;
    const falseAlarm = keys.filter(k => !gCounts.has(k) && fCounts.has(k)).length;
    return `<tr><td>${esc(type)}</td><td>${caught}</td><td>${missed}</td><td>${falseAlarm}</td></tr>`;
  }).join('');
  const body = allKeys.map(k => {
    const g = gt.find(x => key(x) === k), f = found.find(x => key(x) === k), item = g || f;
    const status = g && f ? 'caught' : g ? 'missed' : 'false alarm';
    return `<tr data-id="${esc(item.ticket_id)}"><td>${val(item.issue_type)}</td><td>${val(item.ticket_id)}</td><td class="status ${status.replace(' ','-')}">${status}</td><td>${val(g?.rule_violated ?? f?.check)}</td><td>${val(f?.detail)}</td></tr>`;
  }).join('');
  document.querySelector('#anomalies').innerHTML = `<div class="panel"><h2>Per-issue summary</h2>${table(['Issue type','Caught','Missed','False alarm'],summary)}</div><div class="panel table-card"><h2 style="padding:16px 16px 0">Ground truth and findings</h2>${table(['Issue type','Ticket','Result','Rule / check','Finding detail'],body)}</div>`;
  document.querySelectorAll('#anomalies tr[data-id]').forEach(row => row.addEventListener('click', () => {
    const id = row.dataset.id;
    showTab('tickets');
    const search = document.querySelector('#ticket-search');
    search.value = id; page = 0; updateTicketList();
    if (ticketById.has(id)) openTicket(id);
  }));
}

start();
