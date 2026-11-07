import { api } from '../api/client.js';
import { useLoad } from '../hooks.js';
import { Alert, Badge, Card, Loading, fmtDate } from './ui.jsx';

const TONE = { normal: 'green', low: 'amber', high: 'amber' };

// Lab values that a person has checked and confirmed, newest first.
export default function LabResultsPanel({ patientId }) {
  const { data, loading, error } = useLoad(() => api(`/patients/${patientId}/lab-results`).then((r) => r.lab_results), [patientId]);
  const groups = {};
  (data || []).forEach((r) => { (groups[r.collected_on || 'Date not on report'] ||= []).push(r); });
  return (
    <Card title="Confirmed lab results">
      {loading && <Loading />}
      <Alert>{error}</Alert>
      {data && data.length === 0 && <p className="py-4 text-sm text-slate-400">No confirmed lab results yet. Analyse a lab report in the Documents tab and confirm it.</p>}
      <div className="space-y-5">
        {Object.entries(groups).map(([date, rows]) => (
          <section key={date}>
            <h3 className="mb-1 text-sm font-semibold text-slate-700">{date.length === 10 ? fmtDate(date) : date}</h3>
            <div className="divide-y divide-slate-100 rounded-xl border border-slate-200">
              {rows.map((r) => (
                <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
                  <span className="font-medium text-slate-900">{r.test}</span>
                  <span>{r.value} {r.unit || ''} <span className="text-slate-400">({r.reference || 'no range'})</span></span>
                  <Badge tone={TONE[r.status] || 'slate'}>{r.status === 'normal' ? 'normal' : `${r.status}${r.severity ? ' · ' + r.severity : ''}`}</Badge>
                </div>
              ))}
            </div>
            <p className="mt-1 text-xs text-slate-400">Confirmed by {rows[0].confirmed_by_role}.</p>
          </section>
        ))}
      </div>
    </Card>
  );
}
