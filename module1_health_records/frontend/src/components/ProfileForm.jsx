import { useRef, useState } from 'react';
import { api } from '../api/client.js';
import { Alert, Button, Card, Field, Input, Select, TextArea } from './ui.jsx';
import Avatar from './Avatar.jsx';

// Profile details plus photo controls. canEdit / canPhoto come from the role;
// the backend enforces the same rules.
export default function ProfileForm({ patient, canEdit, canPhoto, onChanged }) {
  const [form, setForm] = useState({
    name: patient.name || '',
    dob: patient.dob || '',
    sex: patient.sex || '',
    phone: patient.phone || '',
    emergency_contact: patient.emergency_contact || '',
    allergies: patient.allergies || '',
  });
  const [msg, setMsg] = useState({ kind: '', text: '' });
  const [busy, setBusy] = useState(false);
  const [photoVersion, setPhotoVersion] = useState(0);
  const fileRef = useRef(null);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setMsg({ kind: '', text: '' });
    try {
      await api(`/patients/${patient.id}`, { method: 'PUT', body: form });
      setMsg({ kind: 'success', text: 'Profile saved.' });
      onChanged();
    } catch (err) {
      setMsg({ kind: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  }

  async function upload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setMsg({ kind: '', text: '' });
    if (file.size > 2 * 1024 * 1024) {
      setMsg({ kind: 'error', text: 'Photo must be smaller than 2 MB.' });
      e.target.value = '';
      return;
    }
    const data = new FormData();
    data.append('photo', file);
    try {
      await api(`/patients/${patient.id}/photo`, { method: 'POST', form: data });
      setPhotoVersion((v) => v + 1);
      setMsg({ kind: 'success', text: 'Photo updated.' });
      onChanged();
    } catch (err) {
      setMsg({ kind: 'error', text: err.message });
    }
    e.target.value = '';
  }

  async function removePhoto() {
    try {
      await api(`/patients/${patient.id}/photo`, { method: 'DELETE' });
      setPhotoVersion((v) => v + 1);
      onChanged();
    } catch (err) {
      setMsg({ kind: 'error', text: err.message });
    }
  }

  return (
    <Card title="Profile">
      <div className="mb-5 flex items-center gap-4">
        <Avatar patientId={patient.id} name={patient.name} hasPhoto={patient.has_photo} version={photoVersion} size={80} />
        {canPhoto && (
          <div className="space-x-2">
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={upload} />
            <Button variant="secondary" onClick={() => fileRef.current?.click()}>{patient.has_photo ? 'Replace photo' : 'Upload photo'}</Button>
            {patient.has_photo && <Button variant="ghost" onClick={removePhoto}>Remove</Button>}
            <p className="mt-1 text-xs text-slate-400">JPG, PNG or WEBP, up to 2 MB.</p>
          </div>
        )}
      </div>

      <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name"><Input disabled={!canEdit} value={form.name} onChange={set('name')} /></Field>
        <Field label="Health ID"><Input disabled value={patient.health_id} readOnly /></Field>
        <Field label="Date of birth"><Input type="date" disabled={!canEdit} value={form.dob} onChange={set('dob')} /></Field>
        <Field label="Sex">
          <Select disabled={!canEdit} value={form.sex} onChange={set('sex')}>
            <option value="">Not specified</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
          </Select>
        </Field>
        <Field label="Phone"><Input disabled={!canEdit} value={form.phone} onChange={set('phone')} /></Field>
        <Field label="Emergency contact"><Input disabled={!canEdit} value={form.emergency_contact} onChange={set('emergency_contact')} /></Field>
        <Field label="Allergies" className="sm:col-span-2"><TextArea disabled={!canEdit} value={form.allergies} onChange={set('allergies')} /></Field>
        <div className="space-y-3 sm:col-span-2">
          <Alert kind={msg.kind || 'error'}>{msg.text}</Alert>
          {canEdit ? <Button disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</Button> : (
            <p className="text-xs text-slate-400">Doctors can view profiles but cannot edit them.</p>
          )}
        </div>
      </form>
    </Card>
  );
}
