import { useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { homeFor, useAuth } from '../context/AuthContext.jsx';
import { Alert, Button, Card, Field, Input } from '../components/ui.jsx';

const PORTALS = ['patient', 'doctor', 'admin'];

export default function Login() {
  const { portal } = useParams();
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (!PORTALS.includes(portal)) return <Navigate to="/" replace />;
  if (user) return <Navigate to={homeFor(user.role)} replace />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const u = await login(portal, form.email, form.password);
      navigate(homeFor(u.role), { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-sky-50 via-white to-teal-50 px-4">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-4 inline-block text-sm text-teal-700 hover:underline">← All portals</Link>
        <Card title={`${portal[0].toUpperCase()}${portal.slice(1)} login`}>
          <form onSubmit={submit} className="space-y-4">
            <Field label="Email"><Input type="email" required autoComplete="username" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
            <Field label="Password"><Input type="password" required autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
            <Alert>{error}</Alert>
            <Button className="w-full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</Button>
          </form>
          {portal === 'patient' && (
            <p className="mt-4 text-center text-sm text-slate-500">
              No account? <Link to="/register" className="font-medium text-teal-700 hover:underline">Register</Link>
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
