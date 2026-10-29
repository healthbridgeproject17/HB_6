import { useState } from 'react';
import { api } from '../api/client.js';
import { useLoad } from '../hooks.js';
import { Alert, Badge, Button, Card, Field, Input, Loading, fmtDate } from './ui.jsx';

const statusTone = { confirmed: 'green', draft: 'amber', discontinued: 'slate' };
const EMPTY = { medicine: '', strength: '', dose: '', route: '', frequency: '', duration: '', start_date: '', end_date: '' };

function RxForm({ initial, submitLabel, onSubmit, onCancel, extra }) {
  const [form, setForm] = useState({ ...EMPTY, ...initial });
  const [error, setError] = useState('');
  const [asDraft, setAsDraft] = useState(false);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError('');
    try {
      await onSubmit(form, asDraft);
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <form onSubmit={submit} className="mb-5 grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-3">
      <Field label="Medicine" className="sm:col-span-3"><Input required value={form.medicine} onChange={set('medicine')} /></Field>
      <Field label="Strength"><Input placeholder="e.g. 500 mg" value={form.strength} onChange={set('strength')} /></Field>
      <Field label="Dose"><Input placeholder="e.g. 1 tablet" value={form.dose} onChange={set('dose')} /></Field>
      <Field label="Route"><Input placeholder="e.g. oral" value={form.route} onChange={set('route')} /></Field>
      <Field label="Frequency"><Input placeholder="e.g. twice daily" value={form.frequency} onChange={set('frequency')} /></Field>
      <Field label="Duration"><Input placeholder="e.g. 5 days" value={form.duration} onChange={set('duration')} /></Field>
      <span />
      <Field label="Start date"><Input type="date" value={form.start_date} onChange={set('start_date')} /></Field>
      <Field label="End date"><Input type="date" value={form.end_date} onChange={set('end_date')} /></Field>
      <span />
      {extra && (
        <label className="flex items-center gap-2 text-sm text-slate-600 sm:col-span-3">
          <input type="checkbox" checked={asDraft} onChange={(e) => setAsDraft(e.target.checked)} />
          Save as draft (needs your confirmation before it counts as a prescription)
        </label>
      )}
      <div className="sm:col-span-3"><Alert>{error}</Alert></div>
      <div className="space-x-2 sm:col-span-3">
        <Button>{submitLabel}</Button>
        {onCancel && <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  );
}

export default function PrescriptionsPanel({ patientId, canWrite }) {
  const { data, loading, error, reload } = useLoad(() => api(`/patients/${patientId}/prescriptions`).then((r) => r.prescriptions), [patientId]);
  const [editing, setEditing] = useState(null);
  const [actionError, setActionError] = useState('');

  async function act(promise) {
    setActionError('');
    try { await promise; reload(); } catch (err) { setActionError(err.message); }
  }

  return (
    <Card title="Prescriptions">
      {canWrite && (
        <RxForm
          initial={{}} submitLabel="Add prescription" extra
          onSubmit={async (form, asDraft) => {
            await api(`/patients/${patientId}/prescriptions`, { method: 'POST', body: { ...form, status: asDraft ? 'draft' : 'confirmed' } });
            reload();
          }}
        />
      )}
      {loading && <Loading />}
      <Alert>{error || actionError}</Alert>
      {data && data.length === 0 && <p className="py-4 text-sm text-slate-400">No prescriptions yet.</p>}
      <div className="space-y-3">
        {data?.map((rx) => (
          <article key={rx.id} className="rounded-xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-medium text-slate-900">{rx.medicine}</h3>
              <Badge tone={statusTone[rx.status]}>{rx.status}</Badge>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-5">
              {[['Strength', rx.strength], ['Dose', rx.dose], ['Route', rx.route], ['Frequency', rx.frequency], ['Duration', rx.duration]].map(([k, v]) => (
                <div key={k}><dt className="text-xs text-slate-400">{k}</dt><dd>{v || '—'}</dd></div>
              ))}
            </dl>
            <p className="mt-2 text-xs text-slate-400">
              {rx.start_date ? `${fmtDate(rx.start_date)} → ${fmtDate(rx.end_date)}` : 'No dates set'}
              {rx.doctor ? ` · Dr ${rx.doctor.replace(/^Dr\.? /, '')}` : ''}
            </p>
            {rx.status === 'draft' && <p className="mt-1 text-xs text-amber-700">Draft: not yet verified by a doctor.</p>}
            {canWrite && rx.status !== 'discontinued' && (
              <div className="mt-2 space-x-2">
                {rx.status === 'draft' && <Button variant="ghost" onClick={() => act(api(`/prescriptions/${rx.id}/confirm`, { method: 'PUT' }))}>Confirm</Button>}
                <Button variant="ghost" onClick={() => setEditing(editing === rx.id ? null : rx.id)}>Edit</Button>
                <Button variant="ghost" onClick={() => window.confirm('Discontinue this prescription?') && act(api(`/prescriptions/${rx.id}`, { method: 'PUT', body: { status: 'discontinued' } }))}>Discontinue</Button>
              </div>
            )}
            {editing === rx.id && (
              <div className="mt-3">
                <RxForm
                  initial={{ medicine: rx.medicine, strength: rx.strength || '', dose: rx.dose || '', route: rx.route || '', frequency: rx.frequency || '', duration: rx.duration || '', start_date: rx.start_date || '', end_date: rx.end_date || '' }}
                  submitLabel="Save changes" onCancel={() => setEditing(null)}
                  onSubmit={async (form) => {
                    await api(`/prescriptions/${rx.id}`, { method: 'PUT', body: form });
                    setEditing(null);
                    reload();
                  }}
                />
              </div>
            )}
          </article>
        ))}
      </div>
    </Card>
  );
}
