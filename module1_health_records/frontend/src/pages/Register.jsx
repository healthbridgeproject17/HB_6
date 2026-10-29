import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { homeFor, useAuth } from '../context/AuthContext.jsx';
import { Alert, Button, Card, Field, Input, Select } from '../components/ui.jsx';

export default function Register() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', password: '', dob: '', sex: '', phone: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const u = await register(form);
      navigate(homeFor(u.role), { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-sky-50 via-white to-teal-50 px-4 py-8">
      <div className="w-full max-w-md">
        <Link to="/" className="mb-4 inline-block text-sm text-teal-700 hover:underline">← Back</Link>
        <Card title="Create patient account">
          <form onSubmit={submit} className="space-y-4">
            <Field label="Full name"><Input required value={form.name} onChange={set('name')} /></Field>
            <Field label="Email"><Input type="email" required value={form.email} onChange={set('email')} /></Field>
            <Field label="Password" hint="At least 8 characters, with a letter and a number."><Input type="password" required autoComplete="new-password" value={form.password} onChange={set('password')} /></Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Date of birth"><Input type="date" value={form.dob} onChange={set('dob')} /></Field>
              <Field label="Sex">
                <Select value={form.sex} onChange={set('sex')}>
                  <option value="">Prefer not to say</option>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                  <option value="other">Other</option>
                </Select>
              </Field>
            </div>
            <Field label="Phone (optional)"><Input value={form.phone} onChange={set('phone')} /></Field>
            <Alert>{error}</Alert>
            <Button className="w-full" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
