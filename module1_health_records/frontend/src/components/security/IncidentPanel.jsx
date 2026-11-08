import { useState } from 'react';
import { Alert, Button, Field, Modal, Select, TextArea, fmtDateTime } from '../ui.jsx';
import { Btn, GROUP_LABELS, INCIDENT_STATUS, Panel, RiskBadge, familyLabel } from './parts.jsx';

const ACTION_LABEL = {
  acknowledge: 'Acknowledged',
  isolate_simulated: 'Isolation (SIMULATED)',
  release_simulated: 'Release (SIMULATED)',
  resolved: 'Closed as resolved',
  false_positive: 'Closed as false alarm',
};

// Details of one incident and the things an admin can do about it.
// Every button calls the backend, which records it in the audit log. "Isolate" and "Release" change nothing real.
export default function IncidentPanel({ incident, busy, onAct }) {
  const [dialog, setDialog] = useState(null); // 'isolate' | 'close'
  const [outcome, setOutcome] = useState('resolved');
  const [note, setNote] = useState('');
  const [formError, setFormError] = useState('');

  if (!incident) {
    return (
      <Panel title="Incident details">
        <p className="text-sm text-slate-400">No alert is selected. When the detector raises an alert (an “incident”), it appears here with the reasons it was raised and the actions you can take: acknowledge, isolate (simulated) and close.</p>
      </Panel>
    );
  }

  const open = incident.status === 'open' || incident.status === 'acknowledged';
  const isolated = incident.machine_isolated_simulated;

  async function send(path, body) {
    const ok = await onAct(`/security/incidents/${incident.id}/${path}`, body);
    if (ok) { setDialog(null); setNote(''); setFormError(''); } else if (dialog) setFormError('That did not work. See the message at the top of the page.');
  }

  return (
    <Panel title={`Incident #${incident.id}`} action={<RiskBadge level={incident.risk_level} />}>
      <div className="space-y-4 text-sm">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-slate-300">
          <span className="font-semibold text-slate-100">{incident.machine_name}</span>
          <span>{INCIDENT_STATUS[incident.status]}</span>
          <span className="text-slate-500">opened {fmtDateTime(incident.opened_at)}</span>
          {incident.is_simulated && <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">Simulated: {familyLabel(incident.sim_family)}</span>}
          {isolated && <span className="rounded bg-violet-500/20 px-2 py-0.5 text-xs font-medium text-violet-200">Marked isolated (simulated)</span>}
        </div>

        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">What stood out</h3>
          {incident.reasons.length ? (
            <ul className="list-disc space-y-1 pl-5 text-slate-200">{incident.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          ) : (
            <p className="text-slate-400">The model raised the alert from a mix of small signals that none of the simple rules caught.</p>
          )}
          {incident.groups.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {incident.groups.map((g) => <span key={g} className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-300">{GROUP_LABELS[g] || g}</span>)}
            </div>
          )}
        </div>

        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">How the risk level was reached</h3>
          <ul className="space-y-0.5 text-slate-300">{incident.risk_why.map((r) => <li key={r}>{r}</li>)}</ul>
          <p className="mt-1 text-xs text-slate-500">Peak model score {incident.peak_score.toFixed(2)} · {incident.alert_count} alert(s) · risk only goes up while an incident is open.</p>
        </div>

        {open && (
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs text-slate-400">
            <span className="font-semibold text-slate-300">What a person would do on a real machine:</span> disconnect it from the network (keep it powered on), do not log in with admin accounts from it, check that offline backups are intact, and tell the security contact.
            This page only records the decision — nothing real is changed.
          </div>
        )}

        {open && (
          <div className="flex flex-wrap gap-2">
            {incident.status === 'open' && <Btn disabled={busy} onClick={() => send('acknowledge', {})}>Acknowledge</Btn>}
            {!isolated && <Btn variant="danger" disabled={busy} onClick={() => setDialog('isolate')}>Isolate machine (simulated)</Btn>}
            {isolated && <Btn disabled={busy} onClick={() => send('respond', { action: 'release' })}>Release machine (simulated)</Btn>}
            <Btn variant="primary" disabled={busy} onClick={() => { setOutcome('resolved'); setDialog('close'); }}>Close incident…</Btn>
          </div>
        )}

        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">History</h3>
          {incident.actions?.length ? (
            <ol className="space-y-1.5 border-l border-slate-800 pl-3">
              {incident.actions.map((a) => (
                <li key={a.id} className="text-slate-300">
                  <span className="font-medium text-slate-100">{ACTION_LABEL[a.action] || a.action}</span>
                  <span className="text-slate-500"> · {a.by || 'unknown'} · {fmtDateTime(a.at)}</span>
                  {a.note && <div className="text-xs text-slate-400">“{a.note}”</div>}
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-slate-500">No one has acted on this incident yet.</p>
          )}
          {incident.status !== 'open' && incident.status !== 'acknowledged' && incident.note && (
            <p className="mt-2 text-xs text-slate-400">Closing note: {incident.note}</p>
          )}
        </div>
      </div>

      {dialog === 'isolate' && (
        <Modal title="Isolate machine (simulated)" onClose={() => setDialog(null)}>
          <div className="space-y-3 text-sm text-slate-700">
            <p>This marks <b>{incident.machine_name}</b> as isolated in HealthBridge and writes it to the audit log.</p>
            <Alert kind="success">It is a SIMULATION. No real machine, file or network is changed.</Alert>
            <Field label="Note (optional)"><TextArea maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
            {formError && <Alert>{formError}</Alert>}
            <div className="flex gap-2"><Button variant="danger" disabled={busy} onClick={() => send('respond', { action: 'isolate', note })}>Record isolation</Button><Button variant="secondary" onClick={() => setDialog(null)}>Cancel</Button></div>
          </div>
        </Modal>
      )}

      {dialog === 'close' && (
        <Modal title={`Close incident #${incident.id}`} onClose={() => setDialog(null)}>
          <div className="space-y-3 text-sm">
            <Field label="Outcome">
              <Select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
                <option value="resolved">Resolved — it was a real problem and it was dealt with</option>
                <option value="false_positive">False alarm — nothing was wrong</option>
              </Select>
            </Field>
            <Field label={outcome === 'resolved' ? 'What was done (required)' : 'Why it was a false alarm (optional)'}>
              <TextArea maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} />
            </Field>
            {formError && <Alert>{formError}</Alert>}
            <div className="flex gap-2">
              <Button disabled={busy || (outcome === 'resolved' && !note.trim())} onClick={() => send('close', { outcome, note })}>Close incident</Button>
              <Button variant="secondary" onClick={() => setDialog(null)}>Cancel</Button>
            </div>
          </div>
        </Modal>
      )}
    </Panel>
  );
}
