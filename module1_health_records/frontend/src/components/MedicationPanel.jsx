import { useState } from 'react';
import { api } from '../api/client.js';
import { useLoad } from '../hooks.js';
import { Alert, Badge, Button, Card, Input, Loading, fmtDateTime } from './ui.jsx';

function Logs({ rxId }) {
  const { data, loading, error } = useLoad(() => api(`/prescriptions/${rxId}/logs`).then((r) => r.logs), [rxId]);
  if (loading) return <Loading />;
  if (error) return <Alert>{error}</Alert>;
  if (!data.length) return <p className="mt-2 text-xs text-slate-400">Nothing recorded yet.</p>;
  return (
    <ul className="mt-2 space-y-1 text-sm">
      {data.map((l) => (
        <li key={l.id} className="flex gap-2">
          <Badge tone={l.status === 'taken' ? 'green' : 'amber'}>{l.status}</Badge>
          <span className="text-slate-500">{fmtDateTime(l.logged_at)}</span>
          {l.note && <span className="text-slate-400">— {l.note}</span>}
        </li>
      ))}
    </ul>
  );
}

// "Last taken" shows only what the patient recorded. No entry = "Not recorded".
export default function MedicationPanel({ patientId, canLog }) {
  const { data, loading, error, reload } = useLoad(() => api(`/patients/${patientId}/medication`).then((r) => r.medication), [patientId]);
  const [notes, setNotes] = useState({});
  const [open, setOpen] = useState(null);
  const [actionError, setActionError] = useState('');

  async function record(rxId, status) {
    setActionError('');
    try {
      await api(`/prescriptions/${rxId}/log`, { method: 'POST', body: { status, note: notes[rxId] || '' } });
      setNotes({ ...notes, [rxId]: '' });
      reload();
    } catch (err) {
      setActionError(err.message);
    }
  }

  return (
    <Card title="Medication tracker">
      {loading && <Loading />}
      <Alert>{error || actionError}</Alert>
      {data && data.length === 0 && <p className="py-4 text-sm text-slate-400">No confirmed prescriptions to track.</p>}
      <div className="space-y-3">
        {data?.map((m) => (
          <article key={m.prescription_id} className="rounded-xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-medium text-slate-900">{m.medicine}</h3>
              <Badge tone={m.active ? 'green' : 'slate'}>{m.active ? 'Active' : 'Not active today'}</Badge>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              {[m.strength, m.dose, m.route, m.frequency, m.duration].filter(Boolean).join(' · ') || 'No details'}
            </p>
            <p className="mt-3 text-sm">
              <span className="text-slate-400">Last taken: </span>
              <span className="font-medium">{m.last_taken_at ? fmtDateTime(m.last_taken_at) : 'Not recorded'}</span>
              <span className="ml-3 text-xs text-slate-400">{m.taken_count} taken · {m.skipped_count} skipped</span>
            </p>
            {canLog && m.active && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Input className="max-w-xs" placeholder="Note (optional)" value={notes[m.prescription_id] || ''} onChange={(e) => setNotes({ ...notes, [m.prescription_id]: e.target.value })} />
                <Button onClick={() => record(m.prescription_id, 'taken')}>Mark taken</Button>
                <Button variant="secondary" onClick={() => record(m.prescription_id, 'skipped')}>Skipped</Button>
              </div>
            )}
            <div className="mt-2">
              <Button variant="ghost" onClick={() => setOpen(open === m.prescription_id ? null : m.prescription_id)}>{open === m.prescription_id ? 'Hide history' : 'History'}</Button>
            </div>
            {open === m.prescription_id && <Logs rxId={m.prescription_id} />}
          </article>
        ))}
      </div>
      {canLog && <p className="mt-4 text-xs text-slate-400">Only you can record doses. Your doctor can see this history.</p>}
    </Card>
  );
}
