import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { useAuth } from '../context/AuthContext.jsx';
import { useIsDesktop } from '../hooks.js';
import DocumentPageViewer from '../components/DocumentPageViewer.jsx';
import { ClinicianSummary, PatientReport, VisitBanner } from '../components/ReportView.jsx';
import { Alert, Badge, Button, Card, Field, Input, Loading, Select, Tabs, cx, fmtDateTime } from '../components/ui.jsx';

const FLAG = { '': '—', H: 'High', L: 'Low' };
const STATUS_TONE = { normal: 'green', low: 'amber', high: 'amber', not_assessed: 'slate' };

function useJob(jobId) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const timer = useRef(null);
  const load = useCallback(async () => {
    try {
      const r = await api(`/analysis/${jobId}`);
      setJob(r.analysis_job);
      setError('');
      if (['queued', 'running'].includes(r.analysis_job.status)) timer.current = setTimeout(load, 1500);
    } catch (e) {
      setError(e.message);
    }
  }, [jobId]);
  useEffect(() => { load(); return () => clearTimeout(timer.current); }, [load]);
  return { job, setJob, error, reload: load };
}

const initialLab = (r) => ({ value: String(r.value), unit: r.unit || '', reference: r.reference?.text || '', flag: r.printed_flag || '', accepted: false, remove: false });
const initialRx = (it) => ({ medicine: it.medicine.printed || '', strength: it.strength.printed || '', dose: it.dose.printed || '', route: it.route.printed || '',
  frequency: it.frequency.printed || '', duration: it.duration.printed || '', accepted: false, remove: false });
const RX_FIELDS = ['medicine', 'strength', 'dose', 'route', 'frequency', 'duration'];

function LabRow({ r, draft, onChange, onLocate, selected, readOnly }) {
  const i = r.interpretation || {};
  const flagged = r.needs_review && !draft.accepted;
  return (
    <article className={cx('rounded-xl border p-3', draft.remove ? 'opacity-50' : '', selected ? 'border-rose-400 ring-2 ring-rose-200' : flagged ? 'border-amber-300 bg-amber-50/50' : 'border-slate-200 bg-white')}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium text-slate-900">{r.test}{r.manual && <span className="ml-2 text-xs text-slate-400">(added by hand)</span>}</div>
        <div className="flex items-center gap-1.5">
          <Badge tone={STATUS_TONE[i.status] || 'slate'}>{i.status === 'normal' ? 'normal' : i.status === 'not_assessed' ? 'not assessed' : `${i.status}${i.severity ? ' · ' + i.severity : ''}`}</Badge>
          {r.source && <Badge tone={r.confidence >= 0.9 ? 'slate' : 'amber'}>{Math.round(r.confidence * 100)}% sure</Badge>}
        </div>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Field label="Value"><Input inputMode="decimal" disabled={readOnly || draft.remove} value={draft.value} onChange={(e) => onChange({ value: e.target.value })} /></Field>
        <Field label="Unit"><Input disabled={readOnly || draft.remove} value={draft.unit} onChange={(e) => onChange({ unit: e.target.value })} /></Field>
        <Field label="Normal range"><Input disabled={readOnly || draft.remove} value={draft.reference} onChange={(e) => onChange({ reference: e.target.value })} /></Field>
        <Field label="Flag on report">
          <Select disabled={readOnly || draft.remove} value={draft.flag} onChange={(e) => onChange({ flag: e.target.value })}>
            {Object.entries(FLAG).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </Field>
      </div>
      {r.value_alternative != null && <p className="mt-2 text-sm text-amber-800">A second reading gave <b>{r.value_alternative}</b>. Check which one is on the document.</p>}
      {r.issues.length > 0 && !draft.accepted && <ul className="mt-2 ml-5 list-disc text-sm text-amber-800">{r.issues.map((x) => <li key={x}>{x}</li>)}</ul>}
      {r.acknowledged_issues?.length > 0 && <p className="mt-2 text-xs text-slate-400">You accepted this value despite: {r.acknowledged_issues.join(' ')}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-3">
        {r.source && <Button variant="ghost" onClick={() => onLocate({ page: r.source.page, bbox: r.source.bbox })}>Show on the document</Button>}
        {!readOnly && r.needs_review && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={draft.accepted} onChange={(e) => onChange({ accepted: e.target.checked })} />
            This matches the original document
          </label>
        )}
        {!readOnly && <Button variant="ghost" onClick={() => onChange({ remove: !draft.remove })}>{draft.remove ? 'Keep this row' : 'Remove row'}</Button>}
      </div>
    </article>
  );
}

function RxRow({ it, draft, onChange, onLocate, readOnly }) {
  const flagged = it.needs_review && !draft.accepted;
  const missing = (f) => it[f].status !== 'ok' && f !== 'route';
  return (
    <article className={cx('rounded-xl border p-3', draft.remove ? 'opacity-50' : '', flagged ? 'border-amber-300 bg-amber-50/50' : 'border-slate-200 bg-white')}>
      <div className="flex items-center justify-between">
        <div className="font-medium text-slate-900">{it.medicine.printed || 'Medicine'}{it.manual && <span className="ml-2 text-xs text-slate-400">(added by hand)</span>}</div>
        <Badge tone="blue">draft</Badge>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {RX_FIELDS.map((f) => (
          <Field key={f} label={f[0].toUpperCase() + f.slice(1) + (missing(f) && !draft[f] ? ' (not detected)' : '')} className={f === 'medicine' ? 'col-span-2 sm:col-span-1' : ''}>
            <Input disabled={readOnly || draft.remove} value={draft[f]} onChange={(e) => onChange({ [f]: e.target.value })}
              className={missing(f) && !draft[f] ? 'border-amber-400' : ''} />
          </Field>
        ))}
      </div>
      {it.issues.length > 0 && !draft.accepted && <ul className="mt-2 ml-5 list-disc text-sm text-amber-800">{it.issues.map((x) => <li key={x}>{x}</li>)}</ul>}
      <div className="mt-2 flex flex-wrap items-center gap-3">
        {it.source && <Button variant="ghost" onClick={() => onLocate({ page: it.source.page, bbox: it.source.bbox })}>Show on the document</Button>}
        {!readOnly && it.needs_review && (
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.accepted} onChange={(e) => onChange({ accepted: e.target.checked })} /> This matches the original document</label>
        )}
        {!readOnly && <Button variant="ghost" onClick={() => onChange({ remove: !draft.remove })}>{draft.remove ? 'Keep this row' : 'Remove row'}</Button>}
      </div>
    </article>
  );
}

export default function AnalysisReview() {
  const { jobId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const desktop = useIsDesktop();
  const { job, setJob, error, reload } = useJob(jobId);
  const [tab, setTab] = useState('values');
  const [selected, setSelected] = useState(null);
  const [labDrafts, setLabDrafts] = useState([]);
  const [rxDrafts, setRxDrafts] = useState([]);
  const [addedLabs, setAddedLabs] = useState([]);
  const [addedRx, setAddedRx] = useState([]);
  const [tests, setTests] = useState([]);
  const [msg, setMsg] = useState({ kind: 'error', text: '' });
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState(false);
  const [idOk, setIdOk] = useState(false);
  const [showClinician, setShowClinician] = useState(false);

  const a = job?.analysis;
  useEffect(() => {
    if (a) {
      setLabDrafts(a.lab_results.map(initialLab));
      setRxDrafts(a.prescription_items.map(initialRx));
    }
  }, [a]);
  useEffect(() => { api('/analysis/tests').then((r) => setTests(r.tests)).catch(() => {}); }, []);

  const readOnly = !job || job.review_status === 'confirmed' || user.role === 'admin';
  const canConfirm = user.role === 'patient' || user.role === 'doctor';

  const edits = useMemo(() => {
    if (!a) return {};
    const out = { lab_results: {}, prescription_items: {}, add_lab_results: addedLabs.filter((x) => x.test && x.value !== ''), add_prescription_items: addedRx.filter((x) => x.medicine) };
    a.lab_results.forEach((r, i) => {
      const d = labDrafts[i];
      if (!d) return;
      const e = {};
      if (d.remove) e.remove = true;
      else {
        if (d.value !== String(r.value)) e.value = d.value;
        if (d.unit !== (r.unit || '')) e.unit = d.unit;
        if (d.reference !== (r.reference?.text || '')) e.reference = d.reference;
        if (d.flag !== (r.printed_flag || '')) e.flag = d.flag;
        if (d.accepted) e.accepted = true;
      }
      if (Object.keys(e).length) out.lab_results[i] = e;
    });
    a.prescription_items.forEach((it, i) => {
      const d = rxDrafts[i];
      if (!d) return;
      const e = {};
      if (d.remove) e.remove = true;
      else {
        RX_FIELDS.forEach((f) => { if (d[f] !== (it[f].printed || '')) e[f] = d[f]; });
        if (d.accepted) e.accepted = true;
      }
      if (Object.keys(e).length) out.prescription_items[i] = e;
    });
    return out;
  }, [a, labDrafts, rxDrafts, addedLabs, addedRx]);
  const hasEdits = Object.keys(edits.lab_results || {}).length + Object.keys(edits.prescription_items || {}).length + (edits.add_lab_results || []).length + (edits.add_prescription_items || []).length > 0;

  async function send(confirm) {
    setBusy(true);
    setMsg({ kind: 'error', text: '' });
    try {
      const r = await api(`/analysis/${jobId}/review`, { method: 'PUT', body: { edits, confirm, acknowledge_identity: idOk } });
      setJob(r.analysis_job);
      setAddedLabs([]);
      setAddedRx([]);
      setMsg({ kind: 'success', text: confirm ? 'Confirmed and saved to the record.' : 'Corrections saved. The assessment was recalculated.' });
    } catch (err) {
      setMsg({ kind: 'error', text: err.message });
      if (err.message && hasEdits) reload();
    } finally {
      setBusy(false);
    }
  }

  const locate = (evidence) => { setSelected(evidence); if (!desktop) setTab('document'); };
  const patch = (setter, i) => (change) => setter((list) => list.map((d, n) => (n === i ? { ...d, ...change } : d)));

  if (error && !job) return <div className="space-y-3"><Alert>{error}</Alert><Link className="text-sm text-teal-700" to={-1}>← Back</Link></div>;
  if (!job) return <Loading />;
  if (['queued', 'running'].includes(job.status)) {
    return (
      <Card title="Reading your document…">
        <div className="flex items-center gap-3 py-4"><span className="h-5 w-5 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
          <p className="text-sm text-slate-600">The computer is reading <b>{job.document_name}</b>. This usually takes under a minute. You can stay on this page.</p></div>
      </Card>
    );
  }
  if (job.status === 'failed') {
    return (
      <div className="space-y-3">
        <Alert>{job.error || 'The analysis failed.'}</Alert>
        <p className="text-sm text-slate-600">Try again with a clearer picture or the original PDF. You can still read the document yourself in the Documents tab.</p>
        <Button variant="secondary" onClick={() => navigate(-1)}>Back</Button>
      </div>
    );
  }

  const flaggedBoxes = [...a.lab_results, ...a.prescription_items].filter((x) => x.needs_review && x.source).map((x) => ({ page: x.source.page, bbox: x.source.bbox }));
  const waiting = [...a.lab_results, ...a.prescription_items].filter((x) => x.needs_review).length;
  const identityBad = a.identity && a.identity.status !== 'match';
  const triage = a.triage;
  const visit = a.report.patient.visit;
  const tabs = [['values', 'Check values', '✏️'], ...(desktop ? [] : [['document', 'Document', '🖼️']]), ['report', 'Report', '📋']];
  const showValues = tab === 'values' || (desktop && tab === 'document');
  const showReport = tab === 'report';

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link className="text-sm text-teal-700 hover:underline" to={-1}>← Back</Link>
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <span className="max-w-[16rem] truncate">{job.document_name}</span>
          {job.review_status === 'confirmed'
            ? <Badge tone="green">Confirmed by {job.confirmed_by_role} · {fmtDateTime(job.confirmed_at)}</Badge>
            : <Badge tone="amber">Not confirmed yet</Badge>}
        </div>
      </div>

      {identityBad && <Alert>{a.identity.message}</Alert>}
      {a.warnings.filter((w) => !w.includes('does NOT match')).slice(0, 3).map((w) => <p key={w} className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{w}</p>)}
      {a.document_type === 'lab_report' && triage && <VisitBanner visit={visit} provisional={triage.provisional} reviewNote={triage.review_note} />}
      {user.role === 'admin' && <p className="rounded-lg bg-slate-100 p-3 text-sm text-slate-600">Admins can read analyses but cannot change or confirm them.</p>}

      <Tabs tabs={tabs} active={tab === 'document' && desktop ? 'values' : tab} onChange={setTab} />

      <div className={cx('grid gap-4', desktop && showValues ? 'lg:grid-cols-2' : '')}>
        {(tab === 'document' || (desktop && showValues)) && (
          <div className={desktop ? 'lg:sticky lg:top-4 lg:self-start' : ''}>
            <Card title="The document"><DocumentPageViewer jobId={job.id} pages={a.pages} selected={selected} flagged={flaggedBoxes} /></Card>
          </div>
        )}

        {showValues && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              {readOnly ? 'These are the saved values.' : `Check each value against the document. ${waiting ? `${waiting} item(s) are marked for checking.` : 'Everything was read with good confidence, but please still check.'}`}
            </p>
            {a.lab_results.map((r, i) => labDrafts[i] && (
              <LabRow key={i} r={r} draft={labDrafts[i]} onChange={patch(setLabDrafts, i)} onLocate={locate} readOnly={readOnly}
                selected={selected && r.source && selected.bbox === r.source.bbox} />
            ))}
            {a.prescription_items.map((it, i) => rxDrafts[i] && <RxRow key={i} it={it} draft={rxDrafts[i]} onChange={patch(setRxDrafts, i)} onLocate={locate} readOnly={readOnly} />)}
            {a.lab_results.length + a.prescription_items.length === 0 && <Alert>Nothing could be read from this document. You can add the values by hand below.</Alert>}

            {a.unrecognized_rows.length > 0 && (
              <Card title="Rows the computer did not understand">
                <ul className="space-y-1 text-sm text-slate-600">{a.unrecognized_rows.map((u, i) => <li key={i}>• {u.name_as_printed}: {u.value} {u.unit_as_printed || ''} <span className="text-slate-400">(add it below if it matters)</span></li>)}</ul>
              </Card>
            )}

            {!readOnly && (
              <Card title="Something missing? Add it by hand">
                <div className="space-y-3">
                  {addedLabs.map((x, i) => (
                    <div key={i} className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <Field label="Test" className="col-span-2 sm:col-span-1">
                        <Input list="known-tests" value={x.test} onChange={(e) => setAddedLabs(addedLabs.map((y, n) => (n === i ? { ...y, test: e.target.value } : y)))} />
                      </Field>
                      <Field label="Value"><Input inputMode="decimal" value={x.value} onChange={(e) => setAddedLabs(addedLabs.map((y, n) => (n === i ? { ...y, value: e.target.value } : y)))} /></Field>
                      <Field label="Unit"><Input value={x.unit} onChange={(e) => setAddedLabs(addedLabs.map((y, n) => (n === i ? { ...y, unit: e.target.value } : y)))} /></Field>
                      <Field label="Normal range"><Input placeholder="12.0 - 15.5" value={x.reference} onChange={(e) => setAddedLabs(addedLabs.map((y, n) => (n === i ? { ...y, reference: e.target.value } : y)))} /></Field>
                    </div>
                  ))}
                  {addedRx.map((x, i) => (
                    <div key={i} className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                      {RX_FIELDS.map((f) => <Field key={f} label={f[0].toUpperCase() + f.slice(1)}><Input value={x[f] || ''} onChange={(e) => setAddedRx(addedRx.map((y, n) => (n === i ? { ...y, [f]: e.target.value } : y)))} /></Field>)}
                    </div>
                  ))}
                  <datalist id="known-tests">{tests.map((t) => <option key={t.key} value={t.label} />)}</datalist>
                  <div className="space-x-2">
                    <Button variant="secondary" onClick={() => setAddedLabs([...addedLabs, { test: '', value: '', unit: '', reference: '' }])}>+ Lab result</Button>
                    <Button variant="secondary" onClick={() => setAddedRx([...addedRx, { medicine: '' }])}>+ Medicine</Button>
                  </div>
                </div>
              </Card>
            )}

            {!readOnly && canConfirm && (
              <Card title="Save">
                <div className="space-y-3">
                  <p className="text-sm text-slate-600">
                    {user.role === 'doctor'
                      ? 'As a doctor, confirming makes the prescriptions active in this patient’s record and saves the lab values.'
                      : 'Confirming saves the lab values to your record. Prescriptions are saved as DRAFTS: a doctor must confirm them before they count.'}
                  </p>
                  {identityBad && <label className="flex items-start gap-2 text-sm"><input className="mt-1" type="checkbox" checked={idOk} onChange={(e) => setIdOk(e.target.checked)} /> I confirm this document belongs to this patient.</label>}
                  <label className="flex items-start gap-2 text-sm"><input className="mt-1" type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} /> I have checked these values against the original document.</label>
                  <Alert kind={msg.kind}>{msg.text}</Alert>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" disabled={busy || !hasEdits} onClick={() => send(false)}>Save corrections</Button>
                    <Button disabled={busy || !checked} onClick={() => send(true)}>Confirm and save to record</Button>
                  </div>
                </div>
              </Card>
            )}
            {job.review_status === 'confirmed' && (
              <Alert kind="success">
                Confirmed and saved to the record. Lab values are in the Results tab. Prescriptions are in the Prescriptions tab
                {job.confirmed_by_role === 'patient' ? ' as drafts until a doctor confirms them.' : '.'}
              </Alert>
            )}
          </div>
        )}

        {showReport && (
          <div className="space-y-4">
            {a.report.patient.type === 'lab_report' && <VisitBanner visit={visit} provisional={triage?.provisional} reviewNote={triage?.review_note} />}
            <PatientReport report={a.report.patient} onLocate={locate} />
            {a.report.clinician && (
              <div>
                <Button variant="secondary" onClick={() => setShowClinician(!showClinician)}>{showClinician ? 'Hide' : 'Show'} clinician summary</Button>
                {showClinician && <div className="mt-3"><ClinicianSummary data={a.report.clinician} /></div>}
              </div>
            )}
            <Button variant="secondary" onClick={() => window.print()}>Print this report</Button>
          </div>
        )}
      </div>
    </div>
  );
}
