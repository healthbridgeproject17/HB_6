import { useState } from 'react';
import { api } from '../../api/client.js';
import { useAuth } from '../../context/AuthContext.jsx';
import { useLoad } from '../../hooks.js';
import PatientSearch from '../../components/PatientSearch.jsx';
import { Alert, Badge, Button, Card, Field, Input, Loading, Select, Tabs, fmtDateTime } from '../../components/ui.jsx';

function CreateDoctor({ onCreated }) {
  const [form, setForm] = useState({ name: '', email: '', password: '', specialty: '', license_no: '' });
  const [msg, setMsg] = useState({ kind: 'error', text: '' });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setMsg({ kind: 'error', text: '' });
    try {
      const r = await api('/admin/doctors', { method: 'POST', body: form });
      setMsg({ kind: 'success', text: `Doctor account created for ${r.user.email}.` });
      setForm({ name: '', email: '', password: '', specialty: '', license_no: '' });
      onCreated();
    } catch (err) {
      setMsg({ kind: 'error', text: err.message });
    }
  }
  return (
    <Card title="Create doctor account">
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name"><Input required value={form.name} onChange={set('name')} /></Field>
        <Field label="Email"><Input type="email" required value={form.email} onChange={set('email')} /></Field>
        <Field label="Temporary password" hint="At least 8 characters, with a letter and a number."><Input type="password" required autoComplete="new-password" value={form.password} onChange={set('password')} /></Field>
        <Field label="Specialty"><Input value={form.specialty} onChange={set('specialty')} /></Field>
        <Field label="License no. (optional)"><Input value={form.license_no} onChange={set('license_no')} /></Field>
        <div className="space-y-3 sm:col-span-2">
          <Alert kind={msg.kind}>{msg.text}</Alert>
          <Button>Create doctor</Button>
        </div>
      </form>
    </Card>
  );
}

function Users({ reloadKey }) {
  const { user: me } = useAuth();
  const [role, setRole] = useState('');
  const { data, loading, error, reload } = useLoad(() => api(`/admin/users${role ? `?role=${role}` : ''}`).then((r) => r.users), [role, reloadKey]);
  const [actionError, setActionError] = useState('');

  async function toggle(u) {
    setActionError('');
    try {
      await api(`/admin/users/${u.id}/active`, { method: 'PATCH', body: { is_active: !u.is_active } });
      reload();
    } catch (err) {
      setActionError(err.message);
    }
  }
  return (
    <Card title="Accounts" action={
      <Select value={role} onChange={(e) => setRole(e.target.value)}>
        <option value="">All roles</option><option value="patient">Patients</option><option value="doctor">Doctors</option><option value="admin">Admins</option>
      </Select>}>
      {loading && <Loading />}
      <Alert>{error || actionError}</Alert>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-400"><tr><th className="py-2">Name</th><th>Email</th><th>Role</th><th>Status</th><th /></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {data?.map((u) => (
              <tr key={u.id}>
                <td className="py-2 font-medium">{u.name}</td>
                <td className="text-slate-500">{u.email}</td>
                <td><Badge tone="teal">{u.role}</Badge></td>
                <td><Badge tone={u.is_active ? 'green' : 'red'}>{u.is_active ? 'Active' : 'Disabled'}</Badge></td>
                <td className="text-right">
                  {u.id !== me.id && <Button variant="ghost" onClick={() => toggle(u)}>{u.is_active ? 'Disable' : 'Enable'}</Button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function AuditLog() {
  const [filters, setFilters] = useState({ action: '', since: '', until: '' });
  const [page, setPage] = useState(1);
  const actions = useLoad(() => api('/admin/audit-logs/actions').then((r) => r.actions), []);
  const qs = new URLSearchParams({ page, per_page: 15 });
  Object.entries(filters).forEach(([k, v]) => v && qs.set(k, v));
  const { data, loading, error } = useLoad(() => api(`/admin/audit-logs?${qs}`), [page, filters.action, filters.since, filters.until]);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;
  const set = (key) => (e) => { setPage(1); setFilters({ ...filters, [key]: e.target.value }); };

  return (
    <Card title="Audit log">
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Field label="Action">
          <Select value={filters.action} onChange={set('action')}>
            <option value="">All actions</option>
            {actions.data?.map((a) => <option key={a} value={a}>{a}</option>)}
          </Select>
        </Field>
        <Field label="From"><Input type="date" value={filters.since} onChange={set('since')} /></Field>
        <Field label="To"><Input type="date" value={filters.until} onChange={set('until')} /></Field>
      </div>
      {loading && <Loading />}
      <Alert>{error}</Alert>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-400"><tr><th className="py-2">Time</th><th>User</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {data?.logs.map((l) => (
              <tr key={l.id} className="align-top">
                <td className="whitespace-nowrap py-2 text-slate-500">{fmtDateTime(l.created_at)}</td>
                <td>{l.user_name || '—'} {l.user_role && <Badge>{l.user_role}</Badge>}</td>
                <td className="font-medium">{l.action}</td>
                <td className="text-slate-500">{l.target_type ? `${l.target_type} #${l.target_id ?? ''}` : '—'}</td>
                <td className="max-w-xs break-words text-xs text-slate-500">{l.detail || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
          <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
          <span>Page {page} of {pages} · {data.total} entries</span>
          <Button variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      )}
    </Card>
  );
}

export default function AdminDashboard() {
  const [tab, setTab] = useState('users');
  const [reloadKey, setReloadKey] = useState(0);
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Admin dashboard</h1>
        <p className="text-sm text-slate-500">Manage accounts and review activity. Admins cannot write clinical entries.</p>
      </div>
      <Tabs active={tab} onChange={setTab} tabs={[['users', 'Accounts', '👥'], ['doctor', 'Add doctor', '🩺'], ['patients', 'Patients', '🧑'], ['audit', 'Audit log', '🛡️']]} />
      {tab === 'users' && <Users reloadKey={reloadKey} />}
      {tab === 'doctor' && <CreateDoctor onCreated={() => setReloadKey((k) => k + 1)} />}
      {tab === 'patients' && <PatientSearch />}
      {tab === 'audit' && <AuditLog />}
    </div>
  );
}
