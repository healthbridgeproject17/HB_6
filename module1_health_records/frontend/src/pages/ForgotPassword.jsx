import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { Alert, Button, Card, Field, Input } from '../components/ui.jsx';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const r = await api('/auth/password-reset/request', { method: 'POST', body: { email } });
      setMessage(r.message);
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
        <Card title="Forgot your password?">
          {message ? (
            <div className="space-y-3">
              <Alert kind="success">{message}</Alert>
              <p className="text-sm text-slate-500">Check your inbox and spam folder. You can close this page.</p>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <p className="text-sm text-slate-600">Enter the email of your account and we will send you a link to choose a new password.</p>
              <Field label="Email"><Input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
              <Alert>{error}</Alert>
              <Button className="w-full" disabled={busy}>{busy ? 'Sending…' : 'Send reset link'}</Button>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}
