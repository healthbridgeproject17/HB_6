import { useState } from 'react';
import { api } from '../api/client.js';
import { useLoad } from '../hooks.js';
import { Alert, Badge, Button, Card, Field, Input, Loading, Select, TextArea, fmtDateTime } from './ui.jsx';

const typeTone = { diagnosis: 'red', note: 'blue', visit: 'green' };

function NewRecordForm({ patientId, onDone }) {
  const [form, setForm] = useState({ record_type: 'diagnosis', title: '', details: '' });
  const [error, setError] = useState('');
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError('');
    try {
      await api(`/patients/${patientId}/records`, { method: 'POST', body: form });
      setForm({ record_type: 'diagnosis', title: '', details: '' });
      onDone();
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <form onSubmit={submit} className="mb-5 grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-3">
      <Field label="Type">
        <Select value={form.record_type} onChange={set('record_type')}>
          <option value="diagnosis">Diagnosis</option>
          <option value="note">Clinical note</option>
          <option value="visit">Visit</option>
        </Select>
      </Field>
      <Field label="Title" className="sm:col-span-2"><Input required value={form.title} onChange={set('title')} /></Field>
      <Field label="Details" className="sm:col-span-3"><TextArea value={form.details} onChange={set('details')} /></Field>
      <div className="sm:col-span-3"><Alert>{error}</Alert></div>
      <div className="sm:col-span-3"><Button>Add record</Button></div>
    </form>
  );
}

function Amend({ record, onDone, onCancel }) {
  const [form, setForm] = useState({ title: record.title, details: record.details || '', reason: '' });
  const [error, setError] = useState('');
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError('');
    try {
      await api(`/records/${record.id}/amend`, { method: 'POST', body: form });
      onDone();
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
      <p className="text-xs text-amber-700">The original stays on file. Your correction is saved as a new version with the reason below.</p>
      <Field label="Title"><Input value={form.title} onChange={set('title')} /></Field>
      <Field label="Details"><TextArea value={form.details} onChange={set('details')} /></Field>
      <Field label="Reason for amendment (required)"><Input required minLength={5} value={form.reason} onChange={set('reason')} /></Field>
      <Alert>{error}</Alert>
      <div className="space-x-2"><Button>Save amendment</Button><Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button></div>
    </form>
  );
}

function History({ recordId }) {
  const { data, loading, error } = useLoad(() => api(`/records/${recordId}/history`).then((r) => r.history), [recordId]);
  if (loading) return <Loading />;
  if (error) return <Alert>{error}</Alert>;
  return (
    <ol className="mt-3 space-y-2 border-l-2 border-slate-200 pl-4 text-sm">
      {data.map((v) => (
        <li key={v.id}>
          <span className="font-medium">{v.superseded ? 'Earlier version' : 'Current version'}</span>
          <span className="text-slate-400"> · {fmtDateTime(v.created_at)}</span>
          <div className="text-slate-600">{v.title}{v.details ? ` — ${v.details}` : ''}</div>
          {v.amendment_reason && <div className="text-xs text-amber-700">Reason: {v.amendment_reason}</div>}
        </li>
      ))}
    </ol>
  );
}

export default function RecordsPanel({ patientId, canCreate, canAmend }) {
  const { data, loading, error, reload } = useLoad(() => api(`/patients/${patientId}/records`).then((r) => r.records), [patientId]);
  const [amending, setAmending] = useState(null);
  const [history, setHistory] = useState(null);

  return (
    <Card title="Medical records">
      {canCreate && <NewRecordForm patientId={patientId} onDone={reload} />}
      {loading && <Loading />}
      <Alert>{error}</Alert>
      {data && data.length === 0 && <p className="py-4 text-sm text-slate-400">No medical records yet.</p>}
      <div className="space-y-3">
        {data?.map((r) => (
          <article key={r.id} className="rounded-xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={typeTone[r.record_type] || 'slate'}>{r.record_type}</Badge>
              <h3 className="font-medium text-slate-900">{r.title}</h3>
              {r.amended_from_id && <Badge tone="amber">Amended</Badge>}
            </div>
            {r.details && <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">{r.details}</p>}
            <p className="mt-2 text-xs text-slate-400">{r.doctor ? `By ${r.doctor} · ` : ''}{fmtDateTime(r.created_at)}</p>
            {r.amendment_reason && <p className="text-xs text-amber-700">Amendment reason: {r.amendment_reason}</p>}
            <div className="mt-2 space-x-2">
              {r.amended_from_id || history === r.id ? (
                <Button variant="ghost" onClick={() => setHistory(history === r.id ? null : r.id)}>{history === r.id ? 'Hide history' : 'View history'}</Button>
              ) : null}
              {canAmend && <Button variant="ghost" onClick={() => setAmending(amending === r.id ? null : r.id)}>Amend</Button>}
            </div>
            {history === r.id && <History recordId={r.id} />}
            {amending === r.id && <Amend record={r} onCancel={() => setAmending(null)} onDone={() => { setAmending(null); reload(); }} />}
          </article>
        ))}
      </div>
    </Card>
  );
}
