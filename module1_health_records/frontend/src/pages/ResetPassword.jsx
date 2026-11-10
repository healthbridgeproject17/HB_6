import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { Alert, Button, Card, Field, Input } from '../components/ui.jsx';

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [form, setForm] = useState({ next: '', confirm: '' });
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError('');
    if (form.next !== form.confirm) { setError('The two passwords do not match.'); return; }
    setBusy(true);
    try {
      await api('/auth/password-reset/confirm', { method: 'POST', body: { token, new_password: form.next } });
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-sky-50 via-white to-teal-50 px-4">
      <div className="w-full max-w-sm">
        <Card title="Choose a new password">
          {done ? (
            <div className="space-y-3">
              <Alert kind="success">Your password was changed. You were signed out everywhere.</Alert>
              <Link to="/" className="inline-block text-sm font-medium text-teal-700 hover:underline">Go to login</Link>
            </div>
          ) : !token ? (
            <div className="space-y-3">
              <Alert>This link is incomplete. Open the link from your email again, or ask for a new one.</Alert>
              <Link to="/forgot-password" className="inline-block text-sm font-medium text-teal-700 hover:underline">Ask for a new link</Link>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <Field label="New password" hint="8-72 characters, with a letter and a number."><Input type="password" required autoComplete="new-password" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} /></Field>
              <Field label="Confirm new password"><Input type="password" required autoComplete="new-password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} /></Field>
              <Alert>{error}</Alert>
              <Button className="w-full" disabled={busy}>{busy ? 'Saving…' : 'Save new password'}</Button>
              {error && <Link to="/forgot-password" className="block text-center text-sm text-teal-700 hover:underline">Ask for a new link</Link>}
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}
