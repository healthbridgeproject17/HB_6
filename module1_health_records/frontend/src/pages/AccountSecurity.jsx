import { useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import { api } from '../api/client.js';
import { Alert, Button, Card, Field, Input } from '../components/ui.jsx';

export default function AccountSecurity() {
  const { user, refreshUser } = useAuth();
  const [setup, setSetup] = useState(null);       // { secret, otpauth_uri } while turning on
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [backupCodes, setBackupCodes] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function run(fn) {
    setBusy(true);
    setError('');
    try { await fn(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  const start = () => run(async () => { setSetup(await api('/auth/2fa/setup', { method: 'POST' })); setCode(''); });
  const enable = (e) => { e.preventDefault(); run(async () => {
    const r = await api('/auth/2fa/enable', { method: 'POST', body: { code } });
    setBackupCodes(r.backup_codes);
    setSetup(null);
    setCode('');
    await refreshUser();
  }); };
  const disable = (e) => { e.preventDefault(); run(async () => {
    await api('/auth/2fa/disable', { method: 'POST', body: { password, code } });
    setPassword('');
    setCode('');
    setBackupCodes(null);
    await refreshUser();
  }); };

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <Card title="Two-factor login">
        <p className="mb-4 text-sm text-slate-600">
          Status: <strong className={user.two_factor_enabled ? 'text-emerald-700' : 'text-slate-700'}>{user.two_factor_enabled ? 'ON' : 'OFF'}</strong>.
          With two-factor login, a stolen password is not enough: you also need a 6-digit code from an authenticator app on your phone (Google Authenticator, Microsoft Authenticator, Authy and similar).
          {user.role === 'admin' && ' Admins should turn this on.'}
        </p>

        {backupCodes && (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-medium">Save these backup codes now. They are shown only once.</p>
            <p className="mt-1">Each one works one time if you lose your phone. Keep them somewhere private, not on the same phone.</p>
            <ul className="mt-2 grid grid-cols-2 gap-1 font-mono text-sm">{backupCodes.map((c) => <li key={c}>{c}</li>)}</ul>
            <Button variant="secondary" className="mt-3" onClick={() => setBackupCodes(null)}>I have saved them</Button>
          </div>
        )}

        {!user.two_factor_enabled && !setup && <Button onClick={start} disabled={busy}>Turn on two-factor login</Button>}

        {!user.two_factor_enabled && setup && (
          <form onSubmit={enable} className="space-y-4">
            <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-700">
              <li>In your authenticator app choose <em>Add account</em>, then <em>Enter a setup key</em>.</li>
              <li>Account: HealthBridge. Key (spaces do not matter):
                <div className="mt-1 break-all rounded-lg bg-slate-100 px-3 py-2 font-mono text-base tracking-wider">{setup.secret}</div>
              </li>
              <li>Type the 6-digit code the app shows to finish.</li>
            </ol>
            <Field label="6-digit code"><Input inputMode="numeric" autoComplete="one-time-code" required value={code} onChange={(e) => setCode(e.target.value)} /></Field>
            <Alert>{error}</Alert>
            <div className="flex gap-2">
              <Button disabled={busy}>Confirm and turn on</Button>
              <Button type="button" variant="secondary" onClick={() => { setSetup(null); setError(''); }}>Cancel</Button>
            </div>
          </form>
        )}

        {user.two_factor_enabled && (
          <form onSubmit={disable} className="space-y-4 border-t border-slate-100 pt-4">
            <p className="text-sm text-slate-600">To turn it off, enter your password and a current code (or a backup code).</p>
            <Field label="Password"><Input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
            <Field label="Code"><Input inputMode="numeric" required value={code} onChange={(e) => setCode(e.target.value)} /></Field>
            <Alert>{error}</Alert>
            <Button variant="danger" disabled={busy}>Turn off two-factor login</Button>
          </form>
        )}
        {!setup && !user.two_factor_enabled && <div className="mt-3"><Alert>{error}</Alert></div>}
      </Card>
    </div>
  );
}
