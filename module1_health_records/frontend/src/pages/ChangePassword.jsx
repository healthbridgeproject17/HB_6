import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { homeFor, useAuth } from '../context/AuthContext.jsx';
import { Alert, Button, Card, Field, Input } from '../components/ui.jsx';

export default function ChangePassword() {
  const { user, changePassword } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ current: '', next: '', confirm: '' });
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const forced = user.must_change_password;

  async function submit(e) {
    e.preventDefault();
    setError('');
    if (form.next !== form.confirm) { setError('The new passwords do not match.'); return; }
    setBusy(true);
    try {
      await changePassword(form.current, form.next);
      setDone(true);
      setTimeout(() => navigate(homeFor(user.role), { replace: true }), forced ? 0 : 1200);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <Card title={forced ? 'Choose a new password' : 'Change password'}>
        {forced && <p className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Your account was created with a temporary password. Set your own password to continue.</p>}
        <form onSubmit={submit} className="space-y-4">
          <Field label="Current password"><Input type="password" required autoComplete="current-password" value={form.current} onChange={set('current')} /></Field>
          <Field label="New password" hint="8-72 characters, with a letter and a number."><Input type="password" required autoComplete="new-password" value={form.next} onChange={set('next')} /></Field>
          <Field label="Confirm new password"><Input type="password" required autoComplete="new-password" value={form.confirm} onChange={set('confirm')} /></Field>
          <Alert>{error}</Alert>
          <Alert kind="success">{done && !forced ? 'Password changed. Other devices were signed out.' : ''}</Alert>
          <Button disabled={busy}>{busy ? 'Saving…' : 'Save new password'}</Button>
        </form>
      </Card>
    </div>
  );
}
