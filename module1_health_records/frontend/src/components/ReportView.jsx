import { useState } from 'react';
import { Badge, Button, Card, cx } from './ui.jsx';

export const LEVEL_STYLE = {
  routine: { box: 'border-emerald-200 bg-emerald-50 text-emerald-900', icon: '✅', tone: 'green' },
  consult_soon: { box: 'border-amber-200 bg-amber-50 text-amber-900', icon: '🟡', tone: 'amber' },
  consult_promptly: { box: 'border-orange-300 bg-orange-50 text-orange-900', icon: '🟠', tone: 'amber' },
  urgent: { box: 'border-rose-300 bg-rose-50 text-rose-900', icon: '🚨', tone: 'red' },
};
const SEVERITY_TONE = { critical: 'red', marked: 'amber', moderate: 'amber', mild: 'blue', borderline: 'slate' };

export function VisitBanner({ visit, provisional, reviewNote }) {
  if (!visit || !visit.level) return null;
  const s = LEVEL_STYLE[visit.level];
  return (
    <div className={cx('rounded-2xl border-2 p-4', s.box)} role="status">
      <div className="flex items-start gap-3">
        <span className="text-2xl" aria-hidden="true">{s.icon}</span>
        <div>
          <h2 className="text-lg font-bold">{visit.label}{visit.timeframe ? ` (${visit.timeframe})` : ''}</h2>
          <p className="mt-1 text-sm">{visit.advice}</p>
          {provisional && <p className="mt-2 rounded-lg bg-white/70 p-2 text-sm font-medium">Provisional: {reviewNote || 'some values need checking.'}</p>}
        </div>
      </div>
    </div>
  );
}

function Concern({ c, onLocate }) {
  const [open, setOpen] = useState(c.severity === 'critical' || c.severity === 'marked');
  return (
    <article className="rounded-xl border border-slate-200 bg-white">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between gap-2 p-4 text-left" aria-expanded={open}>
        <span className="font-medium text-slate-900">{c.headline}</span>
        <span className="flex shrink-0 items-center gap-2">
          {c.needs_review && <Badge tone="amber">check</Badge>}
          <Badge tone={SEVERITY_TONE[c.severity] || 'slate'}>{c.severity}</Badge>
        </span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-slate-100 p-4 text-sm">
          {c.measures && <p><span className="text-slate-400">What it is: </span>{c.measures}</p>}
          <p><span className="text-slate-400">What it means: </span>{c.meaning}</p>
          {[['How it may affect you', c.may_affect], ['What you can do', c.self_care], ['See a doctor sooner if', c.see_doctor_sooner_if]].map(([label, list]) => list && list.length > 0 && (
            <div key={label}>
              <div className="font-medium text-slate-700">{label}</div>
              <ul className="ml-5 list-disc space-y-0.5 text-slate-600">{list.map((x) => <li key={x}>{x}</li>)}</ul>
            </div>
          ))}
          {onLocate && c.evidence && <Button variant="ghost" onClick={() => onLocate(c.evidence)}>Show on the document</Button>}
        </div>
      )}
    </article>
  );
}

export function PatientReport({ report, onLocate }) {
  if (!report) return null;
  return (
    <div className="space-y-4">
      <p className="text-base font-medium text-slate-800">{report.headline}</p>
      {report.notes?.map((n) => <p key={n} className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{n}</p>)}

      {report.type === 'lab_report' && (
        <>
          {report.good_news.length > 0 && (
            <Card title="Good news">
              <ul className="space-y-1 text-sm text-slate-700">{report.good_news.map((g) => <li key={g}>✔ {g}</li>)}</ul>
            </Card>
          )}
          {report.concerns.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-semibold text-slate-900">Results to pay attention to</h3>
              {report.concerns.map((c) => <Concern key={c.test_key} c={c} onLocate={onLocate} />)}
            </div>
          )}
          {report.patterns.length > 0 && (
            <Card title="Putting the results together">
              <ul className="space-y-2 text-sm">{report.patterns.map((p) => <li key={p.id}><b>{p.label}.</b> {p.explanation}</li>)}</ul>
            </Card>
          )}
          {report.questions_for_doctor.length > 0 && (
            <Card title="Questions to ask your doctor">
              <ul className="ml-5 list-disc space-y-1 text-sm text-slate-700">{report.questions_for_doctor.map((q) => <li key={q}>{q}</li>)}</ul>
            </Card>
          )}
          {report.visit.see_a_doctor_sooner_if.length > 0 && (
            <Card title="Get medical help sooner if">
              <ul className="ml-5 list-disc space-y-1 text-sm text-slate-700">{report.visit.see_a_doctor_sooner_if.map((x) => <li key={x}>{x}</li>)}</ul>
            </Card>
          )}
        </>
      )}

      {report.type === 'prescription' && (
        <>
          <p className="rounded-lg bg-sky-50 p-3 text-sm text-sky-900">{report.confirm}</p>
          <div className="space-y-2">
            {report.items.map((i, n) => (
              <article key={n} className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium text-slate-900">{i.instructions}</p>
                  {i.needs_review && <Badge tone="amber">check</Badge>}
                </div>
                <p className="mt-1 text-slate-500">Generally used for: {i.purpose}</p>
                {i.issues.length > 0 && <ul className="mt-2 ml-5 list-disc text-amber-800">{i.issues.map((x) => <li key={x}>{x}</li>)}</ul>}
              </article>
            ))}
          </div>
          <ul className="ml-5 list-disc space-y-1 text-sm text-slate-600">{report.reminders.map((r) => <li key={r}>{r}</li>)}</ul>
        </>
      )}

      <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm font-medium text-slate-800">{report.medicines}</p>
      <p className="text-xs text-slate-400">{report.disclaimer}</p>
    </div>
  );
}

export function ClinicianSummary({ data }) {
  if (!data?.findings && !data?.items) return null;
  return (
    <Card title="Clinician summary">
      {data.findings && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400"><tr><th className="py-1">Test</th><th>Value</th><th>Range</th><th>Status</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {data.findings.map((f) => (
                <tr key={f.test} className={f.needs_review ? 'bg-amber-50' : ''}>
                  <td className="py-1.5">{f.test}</td><td>{f.value} {f.unit}</td><td className="text-slate-500">{f.range}</td>
                  <td>{f.status !== 'normal' && f.status !== 'not_assessed' ? <Badge tone={SEVERITY_TONE[f.severity]}>{f.status} · {f.severity}</Badge> : f.status}{f.needs_review ? ' · check' : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data.reasons?.length > 0 && <ul className="mt-3 ml-5 list-disc text-sm text-slate-700">{data.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
      {data.items && data.items.map((i, n) => <p key={n} className="text-sm">{i.medicine} · {i.strength || '?'} · {i.dose || '?'} · {i.route || '-'} · {i.frequency || '?'} · {i.duration || '?'}{i.needs_review ? ' · check' : ''}</p>)}
    </Card>
  );
}
