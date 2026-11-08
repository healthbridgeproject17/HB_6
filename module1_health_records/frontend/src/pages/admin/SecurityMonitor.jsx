import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client.js';
import { cx, fmtDateTime } from '../../components/ui.jsx';
import IncidentPanel from '../../components/security/IncidentPanel.jsx';
import ModelCard from '../../components/security/ModelCard.jsx';
import ScoreChart from '../../components/security/ScoreChart.jsx';
import {
  Btn, DarkAlert, FAMILIES, INCIDENT_STATUS, MACHINE_STATUS, Panel, RISK, RiskBadge, darkField, familyLabel, fmtTime, usePoll,
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
        {m.last_score != null ? `danger score ${m.last_score.toFixed(2)} · ` : ''}{m.windows} checks
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {m.open_incident && <RiskBadge level={m.open_incident.risk_level} />}
        {m.isolated_simulated && <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-xs text-violet-200">isolated (simulated)</span>}
        {m.simulation && <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-xs text-sky-300">playing {m.simulation.window}/{m.simulation.total} checks</span>}
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

const FEED_ROWS = 8;

// What the simulator is doing in each phase, in plain words (shown only for simulated machines).
const PHASE_LABEL = { benign: 'normal work', recon: 'looking around', encrypt: 'locking files', exfil: 'sending data out', sleep: 'pausing' };

const BANNER = {
  alert: 'border-rose-500/50 bg-rose-500/10 text-rose-100',
  watch: 'border-amber-500/50 bg-amber-500/10 text-amber-100',
  ok: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100',
  idle: 'border-slate-700 bg-slate-900 text-slate-200',
};

// One sentence that says what is going on right now, so nobody has to read the numbers.
function StatusBanner({ machines }) {
  const hot = machines.find((m) => m.open_incident);
  let tone = 'idle';
  let title = 'Nothing is being monitored yet';
  let text = 'Pick a computer below and press “Show a ransomware attack” to see how the detector reacts.';
  if (hot) {
    tone = 'alert';
    title = `Possible ransomware activity on ${hot.name}`;
    text = `The detector raised an alert (${(RISK[hot.open_incident.risk_level] || RISK.low).label} risk). Read “What stood out” in the incident panel, then choose what to do.`;
  } else if (machines.some((m) => m.status === 'suspicious')) {
    tone = 'watch';
    title = 'Something looks unusual';
    text = 'One check looked suspicious. An alert opens only if it happens in 2 of the last 3 checks, so one odd moment does not raise a false alarm.';
  } else if (machines.some((m) => m.windows > 0)) {
    tone = 'ok';
    title = 'Everything looks normal';
    text = 'No computer is behaving like ransomware right now.';
  }
  return (
    <div role="status" className={cx('rounded-2xl border px-4 py-3', BANNER[tone])}>
      <div className="text-lg font-semibold">{title}</div>
      <div className="text-sm opacity-90">{text}</div>
    </div>
  );
}

function HowTo() {
  return (
    <details open className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-300">
      <summary className="cursor-pointer font-semibold text-slate-100">How to read this page (30 seconds)</summary>
      <ol className="mt-2 list-decimal space-y-1.5 pl-5">
        <li><b className="text-slate-100">Ransomware</b> is a program that locks a computer’s files and asks for money. This page shows how a detector could spot one early.</li>
        <li>Every <b className="text-slate-100">5 seconds</b> each computer reports how it behaves: how many files change, how random the saved data looks, how many folders are touched, how much data is sent out. One report is called a <b className="text-slate-100">check</b>.</li>
        <li>The detector turns each check into a <b className="text-slate-100">danger score</b> from 0 (normal) to 1 (looks like ransomware). The yellow dashed line is the <b className="text-slate-100">alert line</b>.</li>
        <li>If the score is above the line in <b className="text-slate-100">2 of the last 3 checks</b>, an <b className="text-slate-100">incident</b> (an alert) opens and lists the reasons.</li>
        <li>You then <b className="text-slate-100">acknowledge</b> it, “<b className="text-slate-100">isolate</b>” the computer and <b className="text-slate-100">close</b> it. Isolation is only a simulation: it records your decision and changes nothing real.</li>
      </ol>
      <p className="mt-2 text-slate-400">Try it: choose a computer, then press <b className="text-slate-200">Show a ransomware attack</b>. The first 8 seconds are normal, then the simulated attack starts.</p>
    </details>
  );
}

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

  const startSim = (fam) => act(`/security/machines/${mid}/simulate`, { family: fam, tick: 1, lead_in: 8 });

  async function rotate() {
    const r = await act(`/security/machines/${mid}/token`, {});
    if (r?.token) setTokenInfo({ name: machine.name, token: r.token, note: r.token_note });
  }

  async function clearDemo() {
    if (!window.confirm('Delete all checks and incidents of the simulated computers? Real computers (agents) are not touched.')) return;
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
              Watches computers for behaviour that looks like ransomware. Everything here is <b className="text-slate-200">simulated</b>:
              nothing real is blocked or changed, and the detector was trained on synthetic data.
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
            <StatusBanner machines={machines} />
            <HowTo />

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Tile label="Active alerts" value={overview.open_incidents}
                sub={['critical', 'high', 'medium', 'low'].filter((k) => risk[k]).map((k) => `${risk[k]} ${RISK[k].label.toLowerCase()}`).join(' · ') || 'no alerts right now'} />
              <Tile label="Computers watched" value={machines.length} sub={`${machines.filter((m) => m.kind === 'agent').length} real · ${machines.filter((m) => m.kind === 'simulated').length} simulated`} />
              <Tile label="Checks done" value={totalWindows} sub={`one check every ${overview.window_seconds} seconds`} />
              <Tile label="Alert line" value={overview.threshold != null ? Number(overview.threshold).toFixed(2) : '—'} sub="danger score that counts as suspicious" />
            </div>

            <Panel title="Computers being watched" action={
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
                <Panel title={`Live view · ${machine.name}`} className="min-w-0 lg:col-span-3">
                  <ScoreChart windows={windows} threshold={overview.threshold} />

                  <div className="mt-4 flex flex-wrap items-end gap-2">
                    {machine.kind === 'simulated' ? (
                      machine.simulation ? (
                        <>
                          <p className="flex-1 text-sm text-slate-300">
                            Playing: <b className="text-slate-100">{familyLabel(machine.simulation.family)}</b> · check {machine.simulation.window} of {machine.simulation.total}
                          </p>
                          <Btn variant="danger" disabled={busy} onClick={() => act(`/security/machines/${mid}/simulate/stop`, {})}>Stop</Btn>
                        </>
                      ) : (
                        <>
                          <Btn variant="primary" disabled={busy || !machine.is_active || !overview.available} onClick={() => startSim('benign')}>▶ Show normal activity</Btn>
                          <Btn variant="danger" disabled={busy || !machine.is_active || !overview.available} onClick={() => startSim('fast_encryptor')}>▶ Show a ransomware attack</Btn>
                          <details className="w-full text-xs text-slate-400">
                            <summary className="cursor-pointer">Other kinds of simulated attack</summary>
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <select aria-label="Kind of simulated attack" className={darkField.replace('w-full', 'min-w-[14rem] flex-1')} value={family} onChange={(e) => setFamily(e.target.value)}>
                                {FAMILIES.filter(([k]) => k !== 'benign').map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                              </select>
                              <Btn disabled={busy || !machine.is_active || !overview.available} onClick={() => startSim(family)}>▶ Start this attack</Btn>
                            </div>
                          </details>
                        </>
                      )
                    ) : (
                      <p className="flex-1 text-sm text-slate-400">This machine sends its own telemetry with its token ({machine.status === 'offline' ? 'no data for 30 seconds' : 'one window every 5 seconds'}).</p>
                    )}
                    {machine.kind === 'agent' && <Btn disabled={busy} onClick={rotate}>New token</Btn>}
                    <Btn disabled={busy} onClick={() => act(`/security/machines/${mid}/active`, { is_active: !machine.is_active }, 'PATCH')}>
                      {machine.is_active ? 'Disable' : 'Enable'}
                    </Btn>
                  </div>

                  <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-500">Latest checks (newest first)</h3>
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full min-w-[36rem] text-left text-xs">
                      <thead className="text-slate-500">
                        <tr className="align-bottom">
                          <th className="py-1 pr-3 font-medium" title="Check number">Check</th>
                          <th className="pr-3 font-medium">Time</th>
                          <th className="pr-3 font-medium" title="0 = normal, 1 = looks like ransomware">Danger score</th>
                          <th className="pr-3 font-medium" title="ALERT marks the check that opened an incident: above the alert line in 2 of the last 3 checks">Verdict</th>
                          <th className="pr-3 font-medium" title="Files created, changed or renamed per second">Files changed per second</th>
                          <th className="pr-3 font-medium" title="Share of saved data that looks random, which is what encrypted files look like">Random-looking data</th>
                          <th className="pr-3 font-medium" title="Different folders touched in this check">Folders touched</th>
                          <th className="pr-3 font-medium" title="Data sent out of the computer, in megabytes per second">Data sent out (MB/s)</th>
                          {machine.kind === 'simulated' && <th className="font-medium" title="Known only because this is a simulation">Simulator is doing</th>}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 text-slate-300">
                        {recent.length === 0 && <tr><td colSpan={9} className="py-3 text-slate-500">No checks yet. {machine.kind === 'simulated' ? 'Press one of the buttons above.' : 'Waiting for the agent to report.'}</td></tr>}
                        {recent.map((w) => (
                          <tr key={w.seq}>
                            <td className="py-1 pr-3 text-slate-500">{w.seq}</td><td className="whitespace-nowrap pr-3">{fmtTime(w.ts)}</td><td className="pr-3">{w.score.toFixed(2)}</td>
                            <td className={cx('pr-3', w.alert ? 'font-semibold text-rose-300' : w.above ? 'text-amber-300' : 'text-emerald-300')}>{w.alert ? 'ALERT' : w.above ? 'Suspicious' : 'Normal'}</td>
                            <td className="pr-3">{w.features.files_modified_per_s.toFixed(1)}</td><td className="pr-3">{Math.round(w.features.high_entropy_write_ratio * 100)}%</td>
                            <td className="pr-3">{Math.round(w.features.distinct_dirs_touched)}</td><td className="pr-3">{w.features.bytes_out_mb_per_s.toFixed(2)}</td>
                            {machine.kind === 'simulated' && <td className="whitespace-nowrap text-slate-500">{PHASE_LABEL[w.phase] || '—'}</td>}
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
