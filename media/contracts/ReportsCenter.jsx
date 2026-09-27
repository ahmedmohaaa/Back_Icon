import { useState, useEffect, useRef, useMemo } from 'react';
import { useAuth } from '../../context/AuthContext';
import apiClient from '../../api/axios';
import {
  getOverviewStatistics, getProjectReport, getTaskReport,
  getEmployeeReport, getFinancialReport,
} from '../../api/services/reports';
import {
  BarChart3, FolderKanban, ListChecks, Users as UsersIcon, Wallet,
  RefreshCw, Download, TrendingUp, AlertTriangle, CheckCircle2,
  Clock, CircleDot, ArrowUpRight,
} from 'lucide-react';

/* ═══════════════════════════════════════════════════════════════
   مركز التقارير الشامل — Reports Center
   أربعة تقارير فوق لوحة مؤشرات حية، برسوم SVG خالصة.
   ═══════════════════════════════════════════════════════════════ */

const TABS = [
  { id: 'projects',  label: 'Projects',  Icon: FolderKanban },
  { id: 'tasks',     label: 'Tasks',     Icon: ListChecks },
  { id: 'employees', label: 'Employees', Icon: UsersIcon },
  { id: 'financial', label: 'Financial', Icon: Wallet },
];

const fmt = (n) => Number(n || 0).toLocaleString('en-US');
const money = (n) => fmt(Number(n || 0).toFixed(0));
const pctNum = (v) => { const x = parseFloat(v); return isNaN(x) ? 0 : x; };

/* ── عدّاد متحرّك ─────────────────────────────────────────── */
function useCountUp(target, decimals = 0, duration = 900) {
  const [val, setVal] = useState(0);
  const ref = useRef(0);
  useEffect(() => {
    const from = ref.current; const to = Number(target) || 0;
    const start = performance.now();
    let raf;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const cur = from + (to - from) * eased;
      setVal(cur); ref.current = cur;
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return decimals ? val.toFixed(decimals) : Math.round(val).toLocaleString('en-US');
}

/* ── كشف عند التمرير ─────────────────────────────────────── */
function useReveal(deps) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const io = new IntersectionObserver((es) =>
      es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }),
      { threshold: 0.1 });
    el.querySelectorAll('.rv').forEach((n) => io.observe(n));
    return () => io.disconnect();
  }, deps);
  return ref;
}

/* ── رسم دائري SVG ───────────────────────────────────────── */
function Donut({ segments, size = 168, thickness = 22 }) {
  const total = segments.reduce((s, x) => s + (Number(x.value) || 0), 0) || 1;
  const r = (size - thickness) / 2; const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="rpt-donut">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,.06)" strokeWidth={thickness} />
      {segments.map((s, i) => {
        const frac = (Number(s.value) || 0) / total;
        const dash = frac * c;
        const el = (
          <circle key={i} cx={size/2} cy={size/2} r={r} fill="none" stroke={s.color}
            strokeWidth={thickness} strokeDasharray={`${dash} ${c - dash}`}
            strokeDashoffset={-offset} strokeLinecap="butt"
            transform={`rotate(-90 ${size/2} ${size/2})`} style={{ transition: 'stroke-dasharray .8s ease' }} />
        );
        offset += dash; return el;
      })}
    </svg>
  );
}

/* ── أعمدة SVG ───────────────────────────────────────────── */
function Bars({ data, height = 150 }) {
  const max = Math.max(1, ...data.map((d) => Number(d.value) || 0));
  return (
    <div className="rpt-bars" style={{ height }}>
      {data.map((d, i) => {
        const h = ((Number(d.value) || 0) / max) * 100;
        return (
          <div key={i} className="rpt-bar-col">
            <span className="rpt-bar-val">{fmt(d.value)}</span>
            <div className="rpt-bar-track">
              <div className="rpt-bar-fill" style={{ height: `${h}%`, background: d.color, animationDelay: `${i * 70}ms` }} />
            </div>
            <span className="rpt-bar-lbl">{d.label}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ── تصدير CSV (بدون مكتبات، يدعم العربية عبر BOM) ─────── */
function downloadCSV(filename, rows, columns) {
  if (!rows.length) return;
  const head = columns.map((c) => `"${String(c.header).replace(/"/g, '""')}"`).join(',');
  const body = rows.map((r) =>
    columns.map((c) => `"${String(r[c.key] ?? '').replace(/"/g, '""')}"`).join(',')
  ).join('\n');
  const blob = new Blob(['\uFEFF' + head + '\n' + body], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

/* ═══════════════════════════════════════════════════════════ */
export default function ReportsCenter() {
  const { user } = useAuth();
  const fullName = user ? `${user.first_name || ''} ${user.last_name || ''}`.trim() : '';
const [activeTab, setActiveTab] = useState('projects');
const [taskStatusFilter, setTaskStatusFilter] = useState('ALL');
  const [tab, setTab] = useState('projects');
  const [stats, setStats] = useState(null);
  const [clients, setClients] = useState([]);
  const [data, setData] = useState({ projects: null, tasks: null, employees: null, financial: null });
  const [loading, setLoading] = useState(true);

  // فلاتر تقرير المشاريع (الباك إند يدعمها)
  const [pf, setPf] = useState({ scope: '', status: '', client: '', date_from: '', date_to: '' });

  // جلب كل شيء مرة واحدة
  useEffect(() => {
    setLoading(true);
    Promise.all([
      getOverviewStatistics().then((r) => r.data).catch(() => null),
      getTaskReport().then((r) => r.data).catch(() => null),
      getEmployeeReport().then((r) => r.data).catch(() => null),
      getFinancialReport().then((r) => r.data).catch(() => null),
      apiClient.get('clients/').then((r) => (r.data.results || r.data) || []).catch(() => []),
    ]).then(([s, t, e, f, cl]) => {
      setStats(s); setData((d) => ({ ...d, tasks: t, employees: e, financial: f })); setClients(cl);
    }).finally(() => setLoading(false));
  }, []);

  // تقرير المشاريع مع الفلاتر
  useEffect(() => {
    setLoading(true);
    getProjectReport(pf).then((r) => setData((d) => ({ ...d, projects: r.data })))
      .catch(() => setData((d) => ({ ...d, projects: null })))
      .finally(() => setLoading(false));
  }, [pf]);

  const refresh = () => { window.location.reload(); };
  const wrap = useReveal([tab, loading]);

  const pa = stats?.projects_analysis || {};
  const te = stats?.tasks_efficiency || {};
  const fa = stats?.financial_analytics || {};

  return (
    <div ref={wrap} className="rpt-root">
      <style>{CSS}</style>
      <div className="rpt-ambient" aria-hidden />

      {/* ── الرأس ─────────────────────────────────────── */}
      <header className="rpt-head rv">
        <div>
          <span className="rpt-kicker">ANALYTICS CONSOLE </span>
          <h1 className="rpt-title">Reports Center</h1>
          <p className="rpt-sub">Unified view of office performance — projects, tasks, staff, and finance.</p>
        </div>
        <div className="rpt-head-right">
          <span className="rpt-live"><i /> Live</span>
          <span className="rpt-who">{fullName}</span>
          <button className="rpt-iconbtn" onClick={refresh} title="تحديث"><RefreshCw size={16} /></button>
        </div>
      </header>

      {/* ── لوحة المؤشرات (شبكة غير متماثلة) ─────────── */}
      <section className="rpt-kpis rv">
        <div className="rpt-kpi rpt-kpi--hero">
          <span className="rpt-kpi-lbl">Total Projects</span>
          <span className="rpt-kpi-num"><HeroNum v={pa.total_projects} /></span>
          <span className="rpt-kpi-foot">
            <span className="dot dot--g" /> {pa.active_projects || 0} Active
            <span className="rpt-sep">·</span> {pa.closed_projects || 0} Closed
          </span>
        </div>
        <div className="rpt-kpi">
          <span className="rpt-kpi-lbl">Task Completion Rate</span>
          <span className="rpt-kpi-num rpt-kpi-num--em"><HeroNum v={te.completion_rate_percentage} dec={1} suffix="%" /></span>
          <div className="rpt-mini-bar"><i style={{ width: `${pctNum(te.completion_rate_percentage)}%` }} /></div>
        </div>
        <div className="rpt-kpi">
          <span className="rpt-kpi-lbl">Total Billed</span>
          <span className="rpt-kpi-num rpt-kpi-num--sky"><HeroNum v={fa.total_billed} /></span>
          <span className="rpt-kpi-foot">QR</span>
        </div>
        <div className="rpt-kpi">
          <span className="rpt-kpi-lbl">Total Collected</span>
          <span className="rpt-kpi-num rpt-kpi-num--g"><HeroNum v={fa.total_collected} /></span>
          <span className="rpt-kpi-foot">QR</span>
        </div>
        <div className="rpt-kpi">
          <span className="rpt-kpi-lbl">Total Receivables</span>
          <span className="rpt-kpi-num rpt-kpi-num--r"><HeroNum v={fa.total_receivables} /></span>
          <span className="rpt-kpi-foot">QR</span>
        </div>
      </section>

      {/* ── التبويبات ─────────────────────────────────── */}
      <nav className="rpt-tabs rv">
        {TABS.map((t) => (
          <button key={t.id} className={`rpt-tab ${tab === t.id ? 'on' : ''}`} onClick={() => setTab(t.id)}>
            <t.Icon size={16} /> {t.label}
          </button>
        ))}
        <button className="rpt-export" onClick={() => exportTab(tab, data)}>
          <Download size={15} /> Export CSV
        </button>
      </nav>

      {/* ── المحتوى ───────────────────────────────────── */}
      <div className="rpt-body">
        {loading && <div className="rpt-loading">Loading data...</div>}

        {!loading && tab === 'projects' && (
          <ProjectsTab data={data.projects} pf={pf} setPf={setPf} clients={clients} wrap={wrap} />
        )}
        {!loading && tab === 'tasks' && <TasksTab data={data.tasks} />}
        {!loading && tab === 'employees' && <EmployeesTab data={data.employees} />}
        {!loading && tab === 'financial' && <FinancialTab data={data.financial} />}
      </div>
    </div>
  );
}

function HeroNum({ v, dec = 0, suffix = '' }) {
  const out = useCountUp(v, dec);
  return <>{out}{suffix}</>;
}

/* ═══════════════════ تبويب المشاريع ═══════════════════ */
function ProjectsTab({ data, pf, setPf, clients }) {
  const rows = data?.projects || [];
  const donut = [
    { value: data?.active || 0, color: '#3fae84', label: 'Active' },
    { value: data?.closed || 0, color: '#6b7682', label: 'Closed' },
  ];
  return (
    <div className="rpt-grid-2">
      <div className="rpt-panel rv">
        <div className="rpt-panel-h"><FolderKanban size={16} /> Report Filters</div>
        <div className="rpt-filters">
          <Field label="Scope">
            <select value={pf.scope} onChange={(e) => setPf({ ...pf, scope: e.target.value })}>
              <option value="">All</option><option value="DESIGN">Design</option>
              <option value="SUPERVISION">Supervision</option><option value="BOTH">Both</option>
            </select>
          </Field>
          <Field label="Status">
            <select value={pf.status} onChange={(e) => setPf({ ...pf, status: e.target.value })}>
              <option value="">All</option><option value="active">Active</option><option value="closed">Closed</option>
            </select>
          </Field>
          <Field label="Client">
            <select value={pf.client} onChange={(e) => setPf({ ...pf, client: e.target.value })}>
              <option value="">All</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <Field label="From Date"><input type="date" value={pf.date_from} onChange={(e) => setPf({ ...pf, date_from: e.target.value })} /></Field>
          <Field label="To Date"><input type="date" value={pf.date_to} onChange={(e) => setPf({ ...pf, date_to: e.target.value })} /></Field>
        </div>
      </div>

      <div className="rpt-panel rv">
        <div className="rpt-panel-h">Distribution by Status</div>
        <div className="rpt-donut-wrap">
          <Donut segments={donut} />
          <ul className="rpt-legend">
            {donut.map((s, i) => (
              <li key={i}><i style={{ background: s.color }} /> {s.label} <b>{s.value}</b></li>
            ))}
            <li className="rpt-legend-total">Total <b>{data?.total || 0}</b></li>
          </ul>
        </div>
      </div>

      <div className="rpt-panel rpt-panel--wide rv">
        <div className="rpt-panel-h">Project Records <span className="rpt-count">{rows.length}</span></div>
        <Table head={['Number', 'Name', 'Client', 'Scope', 'Status', 'Priority']}
          rows={rows}
          cells={(p) => [
            <code>{p.project_no}</code>, p.name, p.client_name || '—',
            <Tag tone={p.scope === 'DESIGN' ? 'sky' : p.scope === 'SUPERVISION' ? 'violet' : 'amber'}>{p.scope}</Tag>,
            <Tag tone={p.is_active ? 'g' : 'z'}>{p.is_active ? 'Active' : 'Closed'}</Tag>,
            <Tag tone={prioTone(p.priority)}>{p.priority}</Tag>,
          ]} />
      </div>
    </div>
  );
}

/* ═══════════════════ تبويب المهام ═══════════════════ */
function TasksTab({ data }) {
  const tasks = data?.tasks || [];
  const bars = [
    { label: 'Completed', value: data?.completed || 0, color: '#3fae84' },
    { label: 'In Progress', value: data?.in_progress || 0, color: '#5cc8ff' },
    { label: 'On Hold', value: data?.on_hold || 0, color: '#e3a948' },
    { label: 'Total', value: data?.total || 0, color: '#8a93a0' },
  ];
  return (
    <div className="rpt-grid-2">
      <div className="rpt-panel rv">
        <div className="rpt-panel-h">Distribution by Status</div>
        <Bars data={bars} />
        <p className="rpt-note">The backend displays a sample of the latest 100 tasks; filtering here is local to this sample.</p>
      </div>
      <div className="rpt-panel rv">
        <div className="rpt-panel-h">Performance Indicators</div>
        <div className="rpt-stat-rows">
          <StatRow label="Total Tasks" value={fmt(data?.total)} />
          <StatRow label="Completed" value={fmt(data?.completed)} tone="g" />
          <StatRow label="Approved Tasks" value={fmt(data?.approved)} tone="em" />
          <StatRow label="In Progress" value={fmt(data?.in_progress)} tone="sky" />
          <StatRow label="Delayed / On Hold" value={fmt(data?.on_hold)} tone="r" />
          <StatRow label="Completion Rate" value={`${pctNum(data?.completion_rate_percentage).toFixed(1)}%`} tone="em" />
        </div>
      </div>
      <div className="rpt-panel rpt-panel--wide rv">
        <div className="rpt-panel-h">Task List <span className="rpt-count">{tasks.length}</span></div>
        <Table head={['Task', 'Project', 'Assigned To', 'Status', 'Progress']}
          rows={tasks}
          cells={(t) => [
            t.title || t.discipline_name || '—', t.project_name || '—', t.assigned_to_name || 'Not Assigned',
            <Tag tone={statusTone(t.status)}>{t.status}</Tag>,
            <span className="rpt-prog"><i style={{ width: `${t.progress_percentage || 0}%` }} /><b>{t.progress_percentage || 0}%</b></span>,
          ]} />
      </div>
    </div>
  );
}

/* ═══════════════════ تبويب الموظفين ═══════════════════ */
function EmployeesTab({ data }) {
  const list = useMemo(() =>
    [...(Array.isArray(data) ? data : [])].sort((a, b) => pctNum(b.completion_rate) - pctNum(a.completion_rate)),
    [data]);
  return (
    <div className="rpt-grid-2">
      <div className="rpt-panel rpt-panel--wide rv">
        <div className="rpt-panel-h">Employee Rankings <span className="rpt-count">{list.length}</span></div>
        <div className="rpt-emp-list">
          {list.map((e, i) => {
            const rate = pctNum(e.completion_rate);
            return (
              <div key={e.user?.id || i} className="rpt-emp rv">
                <span className="rpt-rank">{String(i + 1).padStart(2, '0')}</span>
                <div className="rpt-emp-id">
                  <span className="rpt-emp-name">{e.user?.first_name} {e.user?.last_name}</span>
                  <span className="rpt-emp-role">{e.user?.role_display || e.user?.role}</span>
                </div>
                <div className="rpt-emp-bar"><i style={{ width: `${rate}%`, background: rate >= 70 ? '#3fae84' : rate >= 40 ? '#e3a948' : '#d9606a' }} /></div>
                <div className="rpt-emp-nums">
                  <span><b>{e.completed_tasks || 0}</b>/<span>{e.total_tasks || 0}</span></span>
                  <b className="rpt-emp-rate">{rate.toFixed(0)}%</b>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════ تبويب المالي ═══════════════════ */
function FinancialTab({ data }) {
  const invoiced = Number(data?.total_invoiced || 0);
  const collected = Number(data?.total_collected || 0);
  const outstanding = invoiced - collected; // تعويض bug الباك إند (total_outstanding=0)
  const donut = [
    { value: collected, color: '#3fae84', label: 'Collected' },
    { value: Math.max(outstanding, 0), color: '#d9606a', label: 'Outstanding' },
  ];
  const invoices = data?.invoices || [];
  return (
    <div className="rpt-grid-2">
      <div className="rpt-panel rv">
        <div className="rpt-panel-h">Collection vs. Outstanding</div>
        <div className="rpt-donut-wrap">
          <Donut segments={donut} />
          <ul className="rpt-legend">
            <li><i style={{ background: '#3fae84' }} /> Collected <b>{money(collected)}</b></li>
            <li><i style={{ background: '#d9606a' }} /> Outstanding <b>{money(Math.max(outstanding, 0))}</b></li>
            <li className="rpt-legend-total">Invoiced <b>{money(invoiced)}</b></li>
          </ul>
        </div>
        <p className="rpt-note">The "Outstanding" value is calculated on the frontend (Invoiced − Collected) to compensate for the inactive backend field.</p>
      </div>
      <div className="rpt-panel rv">
        <div className="rpt-panel-h">Performance Indicators</div>
        <div className="rpt-stat-rows">
          <StatRow label="Total Invoiced" value={money(invoiced)} tone="sky" />
          <StatRow label="Total Collected" value={money(collected)} tone="g" />
          <StatRow label="Total Outstanding" value={money(Math.max(outstanding, 0))} tone="r" />
          <StatRow label="Overdue Invoices" value={fmt(data?.overdue_count)} tone="r" />
        </div>
        {Number(data?.overdue_count) > 0 && (
          <div className="rpt-alert"><AlertTriangle size={15} /> There are invoices that have exceeded their due dates — please review the collection panel.</div>
        )}
      </div>
      <div className="rpt-panel rpt-panel--wide rv">
        <div className="rpt-panel-h">Invoices <span className="rpt-count">{invoices.length}</span></div>
        <Table head={['Invoice', 'Milestone', 'Amount', 'Due Date', 'Status']}
          rows={invoices}
          cells={(iv) => [
            iv.title || '—', iv.milestone_type || '—', money(iv.total_amount),
            iv.due_date || '—', <Tag tone={invTone(iv.status)}>{iv.status}</Tag>,
          ]} />
      </div>
    </div>
  );
}

/* ═══════════════════ مكوّنات مساعدة ═══════════════════ */
function Field({ label, children }) {
  return <label className="rpt-field"><span>{label}</span>{children}</label>;
}
function StatRow({ label, value, tone = '' }) {
  return (
    <div className="rpt-statrow">
      <span>{label}</span>
      <b className={tone ? `t-${tone}` : ''}>{value}</b>
    </div>
  );
}
function Tag({ tone = 'z', children }) { return <span className={`rpt-tag rpt-tag--${tone}`}>{children}</span>; }

function Table({ head, rows, cells }) {
  if (!rows.length) return <div className="rpt-empty">No matching data.</div>;
  return (
    <div className="rpt-table-wrap">
      <table className="rpt-table">
        <thead><tr>{head.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={r.id ?? ri}>{cells(r).map((c, ci) => <td key={ci}>{c}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ═══════════════════ تصدير حسب التبويب ═══════════════════ */
function exportTab(tab, data) {
  const stamp = new Date().toISOString().slice(0, 10);
  if (tab === 'projects') {
    const rows = data.projects?.projects || [];
    downloadCSV(`projects-${stamp}.csv`, rows, [
      { key: 'project_no', header: 'Project Number' }, { key: 'name', header: 'Project Name' },
      { key: 'client_name', header: 'Client Name' }, { key: 'scope', header: 'Scope' },
      { key: 'is_active', header: 'Active' }, { key: 'priority', header: 'Priority' },
    ]);
  } else if (tab === 'tasks') {
    downloadCSV(`tasks-${stamp}.csv`, data.tasks?.tasks || [], [
      { key: 'title', header: 'Task Title' }, { key: 'project_name', header: 'Project Name' },
      { key: 'assigned_to_name', header: 'Assigned To' }, { key: 'status', header: 'Status' },
      { key: 'progress_percentage', header: 'Progress' },
    ]);
  } else if (tab === 'employees') {
    const rows = (data.employees || []).map((e) => ({
      name: `${e.user?.first_name || ''} ${e.user?.last_name || ''}`.trim(),
      role: e.user?.role_display || e.user?.role, total: e.total_tasks,
      completed: e.completed_tasks, rate: e.completion_rate,
    }));
    downloadCSV(`employees-${stamp}.csv`, rows, [
      { key: 'name', header: 'Name' }, { key: 'role', header: 'Role' },
      { key: 'total', header: 'Total Tasks' }, { key: 'completed', header: 'Completed' }, { key: 'rate', header: 'Completion Rate' },
    ]);
  } else {
    downloadCSV(`invoices-${stamp}.csv`, data.financial?.invoices || [], [
      { key: 'title', header: 'Invoice' }, { key: 'milestone_type', header: 'Milestone' },
      { key: 'total_amount', header: 'Amount' }, { key: 'due_date', header: 'Due Date' }, { key: 'status', header: 'Status' },
    ]);
  }
}

/* ═══════════════════ ألوان الوسوم ═══════════════════ */
const prioTone = (p) => ({ URGENT: 'r', HIGH: 'amber', MEDIUM: 'sky', LOW: 'g' }[p] || 'z');
const statusTone = (s) => ({ COMPLETED: 'g', APPROVED: 'em', ON_GOING: 'sky', ON_HOLD: 'r', UNDER_STUDY: 'sky', UNCHARTED: 'z', COMMENT: 'amber' }[s] || 'z');
const invTone = (s) => ({ PAID: 'g', ISSUED: 'sky', PARTIALLY_PAID: 'amber', OVERDUE: 'r', DRAFT: 'z', CANCELLED: 'z' }[s] || 'z');

/* ═══════════════════════════════════════════════════════════
   الأنماط — غرفة تحليلات حبرية (الوضع الفاتح)
   ═══════════════════════════════════════════════════════════ */
const CSS = `
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');
.rpt-root{
  --ink:#ffffff; --panel:#ffffff; --panel2:#f8fafc; --line:#e2e8f0; --line2:#cbd5e1;
  --paper:#0f172a; --muted:#64748b;
  --g:#15803d; --em:#059669; --sky:#0284c7; --amber:#d97706; --r:#dc2626; --violet:#7c3aed; --z:#64748b;
  position:relative; min-height:100vh; padding:30px clamp(16px,4vw,44px) 70px;
  color:var(--paper); font-family:'IBM Plex Sans Arabic','Space Grotesk',sans-serif;
  background:linear-gradient(180deg,#f8fafc,#f1f5f9);
}
.rpt-ambient{ position:absolute; inset:0; pointer-events:none;
  background:
    radial-gradient(60% 45% at 88% -8%, rgba(217,119,6,.05), transparent 60%),
    radial-gradient(55% 45% at -5% 105%, rgba(2,132,199,.05), transparent 60%),
    linear-gradient(rgba(2,132,199,.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(2,132,199,.03) 1px, transparent 1px);
  background-size:auto,auto,44px 44px,44px 44px;
  -webkit-mask-image:radial-gradient(130% 100% at 50% 0%,#000,transparent 85%);
          mask-image:radial-gradient(130% 100% at 50% 0%,#000,transparent 85%);
}
.rpt-root > *{ position:relative; }
.rv{ opacity:0; transform:translateY(16px); transition:opacity .7s ease, transform .7s cubic-bezier(.2,.7,.2,1); }
.rv.in{ opacity:1; transform:none; }

/* الرأس */
.rpt-head{ display:flex; justify-content:space-between; align-items:flex-end; gap:20px; flex-wrap:wrap;
  padding-bottom:22px; border-bottom:1px solid var(--line); }
.rpt-kicker{ font-family:'Space Grotesk'; font-size:11px; letter-spacing:.34em; color:var(--amber); }
.rpt-title{ font-family:'Space Grotesk','IBM Plex Sans Arabic'; font-size:clamp(30px,5vw,52px); font-weight:700; line-height:1; margin:8px 0 6px; letter-spacing:-.02em; }
.rpt-sub{ color:var(--muted); font-size:14px; margin:0; }
.rpt-head-right{ display:flex; align-items:center; gap:12px; }
.rpt-live{ display:inline-flex; align-items:center; gap:7px; font-size:12px; color:var(--g); }
.rpt-live i{ width:8px; height:8px; border-radius:50%; background:var(--g); position:relative; }
.rpt-live i::after{ content:""; position:absolute; inset:-4px; border-radius:50%; background:var(--g); opacity:.5; animation:rpt-ping 1.8s infinite; }
@keyframes rpt-ping{ 70%,100%{ transform:scale(2.4); opacity:0; } }
.rpt-who{ font-size:13px; color:var(--paper); padding:6px 12px; border:1px solid var(--line); border-radius:999px; background:var(--panel); }
.rpt-iconbtn{ display:grid; place-items:center; width:36px; height:36px; border-radius:10px; border:1px solid var(--line);
  background:var(--panel); color:var(--muted); cursor:pointer; transition:.25s; box-shadow: 0 1px 2px rgba(0,0,0,0.02); }
.rpt-iconbtn:hover{ color:var(--paper); border-color:var(--sky); transform:rotate(90deg); }

/* المؤشرات */
.rpt-kpis{ display:grid; grid-template-columns:1.6fr 1fr 1fr 1fr 1fr; gap:14px; margin-top:22px; }
@media(max-width:1000px){ .rpt-kpis{ grid-template-columns:1fr 1fr; } .rpt-kpi--hero{ grid-column:1/-1; } }
.rpt-kpi{ position:relative; background:linear-gradient(180deg,rgba(0,0,0,.01),transparent),var(--panel);
  border:1px solid var(--line); border-radius:16px; padding:18px 18px 16px; overflow:hidden;
  transition:transform .35s cubic-bezier(.2,.7,.2,1), border-color .35s, box-shadow .35s; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02); }
.rpt-kpi:hover{ transform:translateY(-4px); border-color:var(--line2); box-shadow:0 12px 24px -10px rgba(15,23,42,.1); }
.rpt-kpi--hero{ background:linear-gradient(135deg,rgba(217,119,6,.06),transparent 60%),var(--panel); border-color:rgba(217,119,6,.25); }
.rpt-kpi-lbl{ display:block; font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
.rpt-kpi-num{ display:block; font-family:'Space Grotesk'; font-weight:700; font-size:clamp(28px,3.4vw,40px); line-height:1.05; margin:8px 0 6px; font-variant-numeric:tabular-nums; }
.rpt-kpi-num--em{ color:var(--em); } .rpt-kpi-num--sky{ color:var(--sky); }
.rpt-kpi-num--g{ color:var(--g); } .rpt-kpi-num--r{ color:var(--r); }
.rpt-kpi-foot{ font-size:12px; color:var(--muted); display:flex; align-items:center; gap:7px; }
.rpt-sep{ opacity:.5; }
.dot{ width:8px; height:8px; border-radius:50%; display:inline-block; } .dot--g{ background:var(--g); }
.rpt-mini-bar{ height:6px; border-radius:99px; background:rgba(0,0,0,.06); overflow:hidden; }
.rpt-mini-bar i{ display:block; height:100%; border-radius:99px; background:linear-gradient(90deg,var(--g),var(--em)); transition:width 1s ease; }

/* التبويبات */
.rpt-tabs{ display:flex; gap:8px; margin-top:24px; flex-wrap:wrap; align-items:center;
  border-bottom:1px solid var(--line); padding-bottom:14px; }
.rpt-tab{ display:inline-flex; align-items:center; gap:8px; padding:9px 16px; border-radius:11px 11px 0 0;
  border:1px solid transparent; border-bottom:none; background:transparent; color:var(--muted);
  cursor:pointer; font-family:inherit; font-size:14px; transition:.25s; }
.rpt-tab:hover{ color:var(--paper); }
.rpt-tab.on{ color:var(--paper); background:var(--panel); border-color:var(--line); box-shadow: 0 -2px 10px rgba(0,0,0,0.02); }
.rpt-export{ margin-inline-start:auto; display:inline-flex; align-items:center; gap:8px; padding:9px 16px;
  border-radius:10px; border:1px solid var(--line); background:var(--panel); color:var(--paper);
  cursor:pointer; font-family:inherit; font-size:13px; transition:.25s; box-shadow: 0 1px 2px rgba(0,0,0,0.02); }
.rpt-export:hover{ border-color:var(--g); color:var(--g); }

/* اللوحات */
.rpt-body{ margin-top:18px; }
.rpt-loading{ padding:60px; text-align:center; color:var(--muted); }
.rpt-grid-2{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }
@media(max-width:880px){ .rpt-grid-2{ grid-template-columns:1fr; } }
.rpt-panel{ background:linear-gradient(180deg,rgba(0,0,0,.01),transparent),var(--panel);
  border:1px solid var(--line); border-radius:16px; padding:18px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02); }
.rpt-panel--wide{ grid-column:1/-1; }
.rpt-panel-h{ display:flex; align-items:center; gap:9px; font-size:14px; font-weight:600; color:var(--paper);
  padding-bottom:12px; margin-bottom:14px; border-bottom:1px solid var(--line); }
.rpt-count{ margin-inline-start:auto; font-family:'JetBrains Mono'; font-size:11px; color:var(--muted);
  background:rgba(0,0,0,.05); padding:2px 9px; border-radius:999px; }

/* الفلاتر */
.rpt-filters{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.rpt-field{ display:flex; flex-direction:column; gap:6px; font-size:12px; color:var(--muted); }
.rpt-field select,.rpt-field input{ background:var(--panel); border:1px solid var(--line); border-radius:9px;
  padding:9px 11px; color:var(--paper); font-family:inherit; font-size:13px; outline:none; transition:.2s; box-shadow: inset 0 1px 2px rgba(0,0,0,0.02); }
.rpt-field select:focus,.rpt-field input:focus{ border-color:var(--sky); box-shadow: 0 0 0 2px rgba(2,132,199,0.1); }

/* الدونات والأسطورة */
.rpt-donut-wrap{ display:flex; align-items:center; gap:22px; flex-wrap:wrap; justify-content:center; }
.rpt-donut{ filter:drop-shadow(0 4px 12px rgba(0,0,0,.06)); }
.rpt-donut circle[stroke="rgba(255,255,255,.06)"] { stroke: rgba(0,0,0,.04); }
.rpt-legend{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:9px; font-size:13px; color:var(--muted); }
.rpt-legend li{ display:flex; align-items:center; gap:9px; }
.rpt-legend i{ width:11px; height:11px; border-radius:3px; display:inline-block; }
.rpt-legend b{ margin-inline-start:auto; color:var(--paper); font-family:'JetBrains Mono'; }
.rpt-legend-total{ padding-top:8px; border-top:1px solid var(--line); }

/* الأعمدة */
.rpt-bars{ display:flex; align-items:flex-end; gap:18px; padding:6px 4px 0; }
.rpt-bar-col{ flex:1; display:flex; flex-direction:column; align-items:center; height:100%; justify-content:flex-end; }
.rpt-bar-val{ font-family:'JetBrains Mono'; font-size:12px; color:var(--paper); margin-bottom:6px; }
.rpt-bar-track{ width:100%; max-width:46px; height:100%; background:rgba(0,0,0,.04); border-radius:8px 8px 0 0; display:flex; align-items:flex-end; overflow:hidden; }
.rpt-bar-fill{ width:100%; border-radius:8px 8px 0 0; animation:rpt-grow .8s cubic-bezier(.2,.7,.2,1) both; }
@keyframes rpt-grow{ from{ height:0 !important; } }
.rpt-bar-lbl{ font-size:11px; color:var(--muted); margin-top:8px; }

/* صفوف الإحصاء */
.rpt-stat-rows{ display:flex; flex-direction:column; }
.rpt-statrow{ display:flex; justify-content:space-between; align-items:center; padding:11px 2px; border-bottom:1px solid var(--line); font-size:13px; color:var(--muted); }
.rpt-statrow:last-child{ border-bottom:none; }
.rpt-statrow b{ font-family:'JetBrains Mono'; color:var(--paper); }
.t-g{ color:var(--g)!important; } .t-sky{ color:var(--sky)!important; } .t-r{ color:var(--r)!important; } .t-em{ color:var(--em)!important; }

/* الموظفون */
.rpt-emp-list{ display:flex; flex-direction:column; gap:8px; }
.rpt-emp{ display:grid; grid-template-columns:34px 1.4fr 2fr 1fr; align-items:center; gap:14px;
  padding:10px 12px; border:1px solid var(--line); border-radius:12px; background:var(--panel2);
  transition:transform .3s cubic-bezier(.2,.7,.2,1), border-color .3s, box-shadow .3s; }
.rpt-emp:hover{ transform:translateX(-4px); border-color:var(--line2); box-shadow: 0 4px 12px rgba(0,0,0,0.03); }
[dir=rtl] .rpt-emp:hover{ transform:translateX(4px); }
.rpt-rank{ font-family:'JetBrains Mono'; font-size:13px; color:var(--muted); }
.rpt-emp-name{ display:block; font-size:13px; font-weight:600; color:var(--paper); }
.rpt-emp-role{ font-size:11px; color:var(--muted); }
.rpt-emp-bar{ height:7px; border-radius:99px; background:rgba(0,0,0,.06); overflow:hidden; }
.rpt-emp-bar i{ display:block; height:100%; border-radius:99px; transition:width 1s ease; }
.rpt-emp-nums{ display:flex; align-items:center; justify-content:flex-end; gap:10px; font-size:12px; color:var(--muted); }
.rpt-emp-nums b{ color:var(--paper); font-family:'JetBrains Mono'; }
.rpt-emp-rate{ color:var(--em)!important; }

/* الجدول */
.rpt-table-wrap{ overflow-x:auto; }
.rpt-table{ width:100%; border-collapse:collapse; font-size:13px; }
.rpt-table th{ text-align:start; font-size:11px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted);
  padding:10px 12px; border-bottom:1px solid var(--line2); font-weight:600; }
.rpt-table td{ padding:11px 12px; border-bottom:1px solid var(--line); color:var(--paper); }
.rpt-table tbody tr{ transition:background .2s, transform .2s; }
.rpt-table tbody tr:hover{ background:rgba(2,132,199,.04); }
.rpt-table code{ font-family:'JetBrains Mono'; font-size:12px; color:var(--sky); background:rgba(2,132,199,.08); padding:2px 6px; border-radius:4px; }
.rpt-empty{ padding:40px; text-align:center; color:var(--muted); }
.rpt-note{ margin-top:14px; font-size:11px; color:var(--muted); line-height:1.7; }
.rpt-alert{ margin-top:14px; display:flex; align-items:center; gap:9px; font-size:12px; color:var(--r);
  background:rgba(220,38,38,.08); border:1px solid rgba(220,38,38,.2); border-radius:10px; padding:10px 12px; }

/* الوسوم والتقدّم */
.rpt-tag{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:11px; font-weight:600; }
.rpt-tag--g{ background:rgba(21,128,61,.12); color:var(--g); }
.rpt-tag--em{ background:rgba(5,150,105,.12); color:var(--em); }
.rpt-tag--sky{ background:rgba(2,132,199,.12); color:var(--sky); }
.rpt-tag--amber{ background:rgba(217,119,6,.12); color:var(--amber); }
.rpt-tag--r{ background:rgba(220,38,38,.12); color:var(--r); }
.rpt-tag--violet{ background:rgba(124,58,237,.12); color:var(--violet); }
.rpt-tag--z{ background:rgba(100,116,139,.12); color:var(--z); }
.rpt-prog{ display:flex; align-items:center; gap:8px; min-width:96px; }
.rpt-prog i{ flex:1; height:6px; border-radius:99px; background:rgba(0,0,0,.06); position:relative; overflow:hidden; }
.rpt-prog i::after{ content:""; position:absolute; inset:0; width:var(--w,0); }
.rpt-prog i{ background:linear-gradient(90deg,var(--sky),var(--g)) no-repeat; background-size:var(--w,0%) 100%; background-color:rgba(0,0,0,.06); }
.rpt-prog b{ font-family:'JetBrains Mono'; font-size:11px; color:var(--paper); min-width:34px; text-align:end; }
`;

