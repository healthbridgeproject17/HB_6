import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client.js';
import { cx, fmtDateTime } from '../../components/ui.jsx';
import IncidentPanel from '../../components/security/IncidentPanel.jsx';
import ModelCard from '../../components/security/ModelCard.jsx';
import ScoreChart from '../../components/security/ScoreChart.jsx';
import {
  Btn, DarkAlert, FAMILIES, INCIDENT_STATUS, MACHINE_STATUS, Panel, RISK, RiskBadge, darkField, fmtTime, usePoll,
} from '../../components/security/parts.jsx';

const KEEP = 60; // windows shown on the chart

function Tile({ label, value, sub }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-0.5 text-2xl font-semibold text-slate-100">{value}</div>
      {sub && <div className="text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

function MachineCard({ m, selected, onSelect }) {
  const st = MACHINE_STATUS[m.status] || MACHINE_STATUS.no_data;
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={() => onSelect(m.id)}
      className={cx('rounded-2xl border p-3 text-left transition', selected ? 'border-teal-400 bg-slate-800' : 'border-slate-800 bg-slate-900 hover:border-slate-600')}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-semibold text-slate-100">{m.name}</span>
        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] text-slate-400">{m.kind === 'agent' ? 'agent' : 'simulated'}</span>
      </div>
      <div className="mt-2 flex items-center gap-2 text-sm text-slate-300">
        <span className={cx('h-2.5 w-2.5 rounded-full', st.dot)} aria-hidden="true" />
        {st.label}
      </div>
      <div className="mt-1 text-xs text-slate-500">
        {m.last_score != null ? `score ${m.last_score.toFixed(2)} · ` : ''}{m.windows} windows
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {m.open_incident && <RiskBadge level={m.open_incident.risk_level} />}
        {m.isolated_simulated && <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-xs text-violet-200">isolated (simulated)</span>}
        {m.simulation && <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-xs text-sky-300">playing {m.simulation.window}/{m.simulation.total}</span>}
      </div>
    </button>
  );
}

function TokenBox({ info, onDismiss }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try { await navigator.clipboard.writeText(info.token); setCopied(true); } catch { /* the token is shown, so it can be copied by hand */ }
  }
  return (
    <div role="status" className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-100">
      <div className="font-semibold">Agent token for {info.name}</div>
      <code className="mt-1 block break-all rounded bg-slate-950 px-2 py-1.5 text-xs text-emerald-200">{info.token}</code>
      <p className="mt-1 text-xs text-emerald-200/80">{info.note}</p>
      <div className="mt-2 flex gap-2"><Btn onClick={copy}>{copied ? 'Copied' : 'Copy token'}</Btn><Btn onClick={onDismiss}>I have saved it</Btn></div>
    </div>
  );
}

const FEED_ROWS = 10;

export default function SecurityMonitor() {
  const [overview, setOverview] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [error, setError] = useState('');
  const [machineId, setMachineId] = useState(null);
  const [incidentId, setIncidentId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [windows, setWindows] = useState([]);
  const [model, setModel] = useState({ loading: true });
  const [tokenInfo, setTokenInfo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [family, setFamily] = useState('fast_encryptor');
  const [filter, setFilter] = useState('open');
  const [newMachine, setNewMachine] = useState({ name: '', kind: 'simulated' });
  const lastSeq = useRef(0);

  const machines = overview?.machines || [];
  const machine = machines.find((m) => m.id === machineId) || machines[0] || null;
  const mid = machine?.id;

  // ---- data
  const refresh = useCallback(async () => {
    try {
      const [o, i] = await Promise.all([api('/security/overview'), api('/security/incidents?limit=50')]);
      setOverview(o);
      setIncidents(i.incidents);
      setError('');
    } catch (e) {
      setError(e.message);
    }
  }, []);
  usePoll(refresh, 2000);

  useEffect(() => {
    api('/security/model')
      .then((r) => setModel({ summary: r.summary }))
      .catch((e) => setModel({ error: e.message }));
  }, []);

  useEffect(() => { lastSeq.current = 0; setWindows([]); }, [mid]);
  useEffect(() => {                       // "Clear demo data" resets a machine's counter
    if (machine && machine.windows < lastSeq.current) { lastSeq.current = 0; setWindows([]); }
  }, [machine?.windows]); // eslint-disable-line react-hooks/exhaustive-deps

  const pollFeed = useCallback(async () => {
    if (!mid) return;
    try {
      const r = await api(`/security/feed?machine_id=${mid}&limit=${KEEP}&after_seq=${lastSeq.current}`);
      if (r.machine_id !== mid || !r.windows.length) return;
      lastSeq.current = r.windows[r.windows.length - 1].seq;
      setWindows((prev) => [...prev, ...r.windows].slice(-KEEP));
    } catch { /* the overview poll shows connection problems */ }
  }, [mid]);
  usePoll(pollFeed, 1000, [mid]);

  const pollDetail = useCallback(async () => {
    if (!incidentId) { setDetail(null); return; }
    try { setDetail((await api(`/security/incidents/${incidentId}`)).incident); } catch { setDetail(null); }
  }, [incidentId]);
  usePoll(pollDetail, 2000, [incidentId]);

  // show the newest open incident automatically the first time one appears
  useEffect(() => {
    if (incidentId == null) {
      const firstOpen = incidents.find((i) => i.status === 'open' || i.status === 'acknowledged');
      if (firstOpen) setIncidentId(firstOpen.id);
    }
  }, [incidents, incidentId]);

  // ---- actions (each one is recorded in the audit log by the backend)
  async function act(path, body, method = 'POST') {
    setBusy(true);
    setError('');
    try {
      const r = await api(path, { method, body });
      await refresh();
      if (incidentId) await pollDetail();
      return r || true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function addMachine(e) {
    e.preventDefault();
    const r = await act('/security/machines', newMachine);
    if (r) {
      setNewMachine({ name: '', kind: newMachine.kind });
      if (r.token) setTokenInfo({ name: r.machine.name, token: r.token, note: r.token_note });
      setMachineId(r.machine.id);
    }
  }

  async function quickStart() {
    for (const name of ['Demo-PC-1', 'Demo-PC-2']) {
      if (!(await act('/security/machines', { name, kind: 'simulated' }))) break;
    }
  }

  async function rotate() {
    const r = await act(`/security/machines/${mid}/token`, {});
    if (r?.token) setTokenInfo({ name: machine.name, token: r.token, note: r.token_note });
  }

  async function clearDemo() {
    if (!window.confirm('Delete all windows and incidents of the simulated machines? Agent machines are not touched.')) return;
    const r = await act('/security/demo-data', undefined, 'DELETE');
    if (r) { setWindows([]); lastSeq.current = 0; setIncidentId(null); setDetail(null); }
  }

  const visibleIncidents = incidents.filter((i) => filter === 'all' || i.status === 'open' || i.status === 'acknowledged');
  const totalWindows = machines.reduce((n, m) => n + m.windows, 0);
  const risk = overview?.open_by_risk || {};
  const recent = windows.slice(-FEED_ROWS).reverse();

  return (
    <div className="-mx-3 -my-4 min-h-[80vh] bg-slate-950 px-3 py-5 text-slate-200 sm:mx-0 sm:my-0 sm:rounded-2xl sm:px-6 sm:py-6">
      <div className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-50">Security monitor</h1>
            <p className="max-w-3xl text-sm text-slate-400">
              Watches ransomware-like behaviour in activity numbers reported every 5 seconds. Everything here is <b className="text-slate-200">simulated</b>:
              isolation only records a decision, and the model was trained on synthetic data.
            </p>
          </div>
          <Link to="/admin" className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800">← Admin dashboard</Link>
        </div>

        <DarkAlert>{error}</DarkAlert>
        {overview && !overview.available && (
          <div role="alert" className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
            The detection engine is not available, so nothing can be scored. {overview.message}
          </div>
        )}
        {tokenInfo && <TokenBox info={tokenInfo} onDismiss={() => setTokenInfo(null)} />}

        {!overview ? (
          <p className="py-10 text-center text-sm text-slate-500">Loading…</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Tile label="Open incidents" value={overview.open_incidents}
                sub={['critical', 'high', 'medium', 'low'].filter((k) => risk[k]).map((k) => `${risk[k]} ${RISK[k].label.toLowerCase()}`).join(' · ') || 'none'} />
              <Tile label="Machines" value={machines.length} sub={`${machines.filter((m) => m.kind === 'agent').length} agent · ${machines.filter((m) => m.kind === 'simulated').length} simulated`} />
              <Tile label="Windows scored" value={totalWindows} sub={`${overview.window_seconds}-second windows`} />
              <Tile label="Alert threshold" value={overview.threshold ?? '—'} sub="model score" />
            </div>

            <Panel title="Machines" action={
              machines.length > 0 && <Btn disabled={busy} onClick={clearDemo}>Clear demo data</Btn>}>
              {machines.length === 0 ? (
                <div className="flex flex-wrap items-center gap-3 text-sm text-slate-400">
                  <span>No machines yet.</span>
                  <Btn variant="primary" disabled={busy} onClick={quickStart}>Add two demo machines</Btn>
                </div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {machines.map((m) => <MachineCard key={m.id} m={m} selected={m.id === mid} onSelect={setMachineId} />)}
                </div>
              )}
              <form onSubmit={addMachine} className="mt-4 flex flex-wrap items-end gap-2 border-t border-slate-800 pt-4">
                <label className="min-w-[10rem] flex-1 text-xs text-slate-400">New machine name
                  <input className={cx(darkField, 'mt-1')} required minLength={2} maxLength={60} value={newMachine.name}
                    onChange={(e) => setNewMachine({ ...newMachine, name: e.target.value })} placeholder="e.g. Lab-PC-2" />
                </label>
                <label className="text-xs text-slate-400">Kind
                  <select className={cx(darkField, 'mt-1')} value={newMachine.kind} onChange={(e) => setNewMachine({ ...newMachine, kind: e.target.value })}>
                    <option value="simulated">Simulated machine</option>
                    <option value="agent">Real computer with an agent</option>
                  </select>
                </label>
                <Btn variant="primary" disabled={busy}>Add machine</Btn>
              </form>
            </Panel>

            {machine && (
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">
                <Panel title={`Live feed · ${machine.name}`} className="min-w-0 lg:col-span-3">
                  <ScoreChart windows={windows} threshold={overview.threshold} />

                  <div className="mt-4 flex flex-wrap items-end gap-2">
                    {machine.kind === 'simulated' ? (
                      <>
                        <label className="min-w-[12rem] flex-1 text-xs text-slate-400">Simulated behaviour
                          <select className={cx(darkField, 'mt-1')} value={family} onChange={(e) => setFamily(e.target.value)} disabled={Boolean(machine.simulation)}>
                            {FAMILIES.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                          </select>
                        </label>
                        {machine.simulation ? (
                          <Btn variant="danger" disabled={busy} onClick={() => act(`/security/machines/${mid}/simulate/stop`, {})}>Stop simulation</Btn>
                        ) : (
                          <Btn variant="primary" disabled={busy || !machine.is_active || !overview.available}
                            onClick={() => act(`/security/machines/${mid}/simulate`, { family, tick: 1, lead_in: 8 })}>Start simulation</Btn>
                        )}
                      </>
                    ) : (
                      <p className="flex-1 text-sm text-slate-400">This machine sends its own telemetry with its token ({machine.status === 'offline' ? 'no data for 30 seconds' : 'one window every 5 seconds'}).</p>
                    )}
                    {machine.kind === 'agent' && <Btn disabled={busy} onClick={rotate}>New token</Btn>}
                    <Btn disabled={busy} onClick={() => act(`/security/machines/${mid}/active`, { is_active: !machine.is_active }, 'PATCH')}>
                      {machine.is_active ? 'Disable' : 'Enable'}
                    </Btn>
                  </div>

                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full min-w-[34rem] text-left text-xs">
                      <thead className="text-slate-500">
                        <tr><th className="py-1 font-medium">#</th><th className="font-medium">Time</th><th className="font-medium">Score</th><th className="font-medium">Result</th>
                          <th className="font-medium">Files/s</th><th className="font-medium">Random-looking writes</th><th className="font-medium">Folders</th><th className="font-medium">Out MB/s</th>
                          {machine.kind === 'simulated' && <th className="font-medium">Simulator truth</th>}</tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 text-slate-300">
                        {recent.length === 0 && <tr><td colSpan={9} className="py-3 text-slate-500">No windows yet. Start a simulation, or wait for the agent.</td></tr>}
                        {recent.map((w) => (
                          <tr key={w.seq}>
                            <td className="py-1 text-slate-500">{w.seq}</td><td>{fmtTime(w.ts)}</td><td>{w.score.toFixed(2)}</td>
                            <td className={w.alert ? 'font-semibold text-rose-300' : w.above ? 'text-amber-300' : 'text-emerald-300'}>{w.alert ? 'ALERT' : w.above ? 'High' : 'Normal'}</td>
                            <td>{w.features.files_modified_per_s.toFixed(1)}</td><td>{Math.round(w.features.high_entropy_write_ratio * 100)}%</td>
                            <td>{Math.round(w.features.distinct_dirs_touched)}</td><td>{w.features.bytes_out_mb_per_s.toFixed(2)}</td>
                            {machine.kind === 'simulated' && <td className="text-slate-500">{w.phase || '—'}</td>}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Panel>

                <div className="min-w-0 lg:col-span-2">
                  <IncidentPanel incident={detail} busy={busy} onAct={act} />
                </div>
              </div>
            )}

            <Panel title="Incidents" action={
              <select aria-label="Which incidents to list" className={darkField.replace('w-full', 'w-auto')} value={filter} onChange={(e) => setFilter(e.target.value)}>
                <option value="open">Open only</option><option value="all">All incidents</option>
              </select>}>
              {visibleIncidents.length === 0 ? (
                <p className="text-sm text-slate-500">No incidents{filter === 'open' ? ' open right now' : ' yet'}.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[32rem] text-left text-sm">
                    <thead className="text-xs text-slate-500"><tr><th className="py-1 font-medium">#</th><th className="font-medium">Machine</th><th className="font-medium">Risk</th><th className="font-medium">Status</th><th className="font-medium">Opened</th><th /></tr></thead>
                    <tbody className="divide-y divide-slate-800">
                      {visibleIncidents.map((i) => (
                        <tr key={i.id} className={cx(i.id === incidentId && 'bg-slate-800/60')}>
                          <td className="py-2 text-slate-500">{i.id}</td>
                          <td className="font-medium text-slate-100">{i.machine_name}</td>
                          <td><RiskBadge level={i.risk_level} /></td>
                          <td className="text-slate-300">{INCIDENT_STATUS[i.status]}</td>
                          <td className="text-slate-400">{fmtDateTime(i.opened_at)}</td>
                          <td className="text-right"><Btn onClick={() => setIncidentId(i.id)}>View</Btn></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>

            <ModelCard state={model} />
          </>
        )}
      </div>
    </div>
  );
}
