import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { useLoad } from '../hooks.js';
import Avatar from './Avatar.jsx';
import { Alert, Button, Card, Input, Loading, fmtDate } from './ui.jsx';

export default function PatientSearch() {
  const [q, setQ] = useState('');
  const [applied, setApplied] = useState('');
  const [page, setPage] = useState(1);
  const { data, loading, error } = useLoad(
    () => api(`/patients?q=${encodeURIComponent(applied)}&page=${page}&per_page=10`),
    [applied, page]
  );

  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;
  return (
    <Card title="Patients">
      <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); setPage(1); setApplied(q.trim()); }}>
        <Input placeholder="Search by name or Health ID (e.g. HB-2026-000001)" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button>Search</Button>
      </form>
      {loading && <Loading />}
      <Alert>{error}</Alert>
      {data && data.patients.length === 0 && <p className="py-4 text-sm text-slate-400">No patients found.</p>}
      <ul className="divide-y divide-slate-100">
        {data?.patients.map((p) => (
          <li key={p.id} className="flex items-center gap-3 py-3">
            <Avatar patientId={p.id} name={p.name} hasPhoto={p.has_photo} size={40} />
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-slate-900">{p.name}</div>
              <div className="text-xs text-slate-400">{p.health_id} · {p.sex || 'sex not set'} · DOB {fmtDate(p.dob)}</div>
            </div>
            <Link to={`/staff/patients/${p.id}`} className="rounded-lg px-3 py-1.5 text-sm font-medium text-teal-700 hover:bg-teal-50">Open</Link>
          </li>
        ))}
      </ul>
      {data && data.total > data.per_page && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
          <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
          <span>Page {page} of {pages} · {data.total} patients</span>
          <Button variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      )}
      <p className="mt-4 text-xs text-slate-400">Opening a patient is recorded in the audit log.</p>
    </Card>
  );
}
