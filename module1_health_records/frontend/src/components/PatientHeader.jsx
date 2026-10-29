import { useState } from 'react';
import Avatar from './Avatar.jsx';
import { Badge, Button, Card } from './ui.jsx';

export default function PatientHeader({ patient }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try { await navigator.clipboard.writeText(patient.health_id); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* ignore */ }
  }
  return (
    <Card className="flex flex-wrap items-center gap-4">
      <Avatar patientId={patient.id} name={patient.name} hasPhoto={patient.has_photo} size={72} />
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-xl font-bold text-slate-900">{patient.name}</h1>
        <p className="text-sm text-slate-500">{patient.email}</p>
        <div className="mt-2 flex items-center gap-2">
          <Badge tone="teal">Health ID</Badge>
          <code className="rounded bg-slate-100 px-2 py-0.5 text-sm">{patient.health_id}</code>
          <Button variant="ghost" onClick={copy}>{copied ? 'Copied' : 'Copy'}</Button>
        </div>
      </div>
    </Card>
  );
}
