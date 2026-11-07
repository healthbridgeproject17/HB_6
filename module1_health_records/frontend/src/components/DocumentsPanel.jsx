import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client.js';
import { useLoad } from '../hooks.js';
import CameraCapture from './CameraCapture.jsx';
import { LEVEL_STYLE } from './ReportView.jsx';
import { Alert, Badge, Button, Card, Field, Loading, Modal, Select, fmtDateTime, fmtSize } from './ui.jsx';

const TYPE_LABEL = { prescription: 'Prescription', lab_report: 'Lab / medical report', other: 'Other document' };
const TYPE_TONE = { prescription: 'blue', lab_report: 'teal', other: 'slate' };
const MAX_BYTES = 10 * 1024 * 1024;

function Viewer({ doc, onClose }) {
  const [state, setState] = useState({ url: null, error: '' });
  useEffect(() => {
    let url = null;
    let alive = true;
    api(`/documents/${doc.id}/file`, { raw: true })
      .then((blob) => { if (alive) { url = URL.createObjectURL(blob); setState({ url, error: '' }); } })
      .catch((e) => alive && setState({ url: null, error: e.message }));
    return () => { alive = false; if (url) URL.revokeObjectURL(url); };
  }, [doc.id]);

  const isPdf = doc.mime_type === 'application/pdf';
  return (
    <Modal title={doc.original_name} onClose={onClose} wide>
      <Alert>{state.error}</Alert>
      {!state.url && !state.error && <Loading />}
      {state.url && isPdf && (
        <>
          <iframe title={doc.original_name} src={state.url} className="h-[65vh] w-full rounded-lg border border-slate-200" />
          <a href={state.url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-sm text-teal-700 hover:underline">Open PDF in a new tab</a>
        </>
      )}
      {state.url && !isPdf && <img src={state.url} alt={doc.original_name} className="mx-auto max-h-[70vh] rounded-lg" />}
    </Modal>
  );
}

// Upload a report, prescription or other document: choose a file or take a photo.
export default function DocumentsPanel({ patientId }) {
  const navigate = useNavigate();
  const { data, loading, error, reload } = useLoad(() => api(`/patients/${patientId}/documents`).then((r) => r.documents), [patientId]);
  const analyses = useLoad(() => api(`/patients/${patientId}/analyses`).then((r) => r.analyses), [patientId]);
  const latest = {};
  (analyses.data || []).forEach((a) => { if (!latest[a.document_id]) latest[a.document_id] = a; });
  const [docType, setDocType] = useState('lab_report');
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [msg, setMsg] = useState({ kind: 'error', text: '' });
  const [busy, setBusy] = useState(false);
  const [camera, setCamera] = useState(false);
  const [viewing, setViewing] = useState(null);
  const fileRef = useRef(null);
  const cameraRef = useRef(null);

  useEffect(() => {
    if (file && file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file);
      setPreview(url);
      return () => URL.revokeObjectURL(url);
    }
    setPreview(null);
    return undefined;
  }, [file]);

  function pick(f) {
    setMsg({ kind: 'error', text: '' });
    if (!f) return;
    if (f.size > MAX_BYTES) {
      setMsg({ kind: 'error', text: 'That file is larger than 10 MB. Choose a smaller file or a lower photo resolution.' });
      return;
    }
    setFile(f);
  }

  // Phones/tablets: open the native camera. Computers: use the webcam dialog.
  function takePhoto() {
    const touch = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
    if (touch) cameraRef.current?.click();
    else setCamera(true);
  }

  async function upload() {
    if (!file) return;
    setBusy(true);
    setMsg({ kind: 'error', text: '' });
    const form = new FormData();
    form.append('file', file);
    form.append('doc_type', docType);
    try {
      await api(`/patients/${patientId}/documents`, { method: 'POST', form });
      setFile(null);
      setMsg({ kind: 'success', text: 'Uploaded. The document is saved to the patient record.' });
      reload();
    } catch (err) {
      setMsg({ kind: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  }

  async function analyse(doc) {
    setMsg({ kind: 'error', text: '' });
    try {
      const r = await api(`/documents/${doc.id}/analyze`, { method: 'POST' });
      navigate(`/analysis/${r.job.id}`);
    } catch (err) {
      if (err.status === 409 && latest[doc.id]) navigate(`/analysis/${latest[doc.id].id}`);
      else setMsg({ kind: 'error', text: err.message });
    }
  }

  async function remove(doc) {
    if (!window.confirm(`Delete "${doc.original_name}"?`)) return;
    try {
      await api(`/documents/${doc.id}`, { method: 'DELETE' });
      reload();
    } catch (err) {
      setMsg({ kind: 'error', text: err.message });
    }
  }

  return (
    <div className="space-y-5">
      <Card title="Upload a document">
        <div className="space-y-4">
          <Field label="What are you uploading?">
            <Select value={docType} onChange={(e) => setDocType(e.target.value)}>
              {Object.entries(TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </Field>

          <div className="flex flex-wrap gap-2">
            <input ref={fileRef} type="file" accept="application/pdf,image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ''; }} />
            <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ''; }} />
            <Button variant="secondary" onClick={() => fileRef.current?.click()}>Choose file</Button>
            <Button variant="secondary" onClick={takePhoto}>📷 Take photo</Button>
          </div>
          <p className="text-xs text-slate-400">PDF, JPG, PNG or WEBP, up to 10 MB. For photos: good light, page flat, text sharp.</p>

          {file && (
            <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
              {preview ? <img src={preview} alt="Preview" className="h-20 w-20 rounded-lg object-cover" /> : <div className="flex h-20 w-20 items-center justify-center rounded-lg bg-white text-sm font-semibold text-slate-400">PDF</div>}
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{file.name}</div>
                <div className="text-xs text-slate-400">{fmtSize(file.size)}</div>
              </div>
              <Button variant="ghost" onClick={() => setFile(null)}>Remove</Button>
            </div>
          )}

          <Alert kind={msg.kind}>{msg.text}</Alert>
          <Button onClick={upload} disabled={!file || busy}>{busy ? 'Uploading…' : 'Upload'}</Button>
        </div>
      </Card>

      <Card title="Uploaded documents">
        {loading && <Loading />}
        <Alert>{error}</Alert>
        {data && data.length === 0 && <p className="py-4 text-sm text-slate-400">No documents uploaded yet.</p>}
        <ul className="divide-y divide-slate-100">
          {data?.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-3 py-3">
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-slate-900">{d.original_name}</div>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-400">
                  <Badge tone={TYPE_TONE[d.doc_type]}>{TYPE_LABEL[d.doc_type]}</Badge>
                  <span>{fmtSize(d.size_bytes)}</span>
                  <span>{fmtDateTime(d.uploaded_at)}</span>
                  {d.uploaded_by && <span>by {d.uploaded_by}</span>}
                </div>
                {latest[d.id] && (
                  <Link to={`/analysis/${latest[d.id].id}`} className="mt-1 inline-flex items-center gap-2 text-xs text-teal-700 hover:underline">
                    {latest[d.id].status === 'failed' ? 'Analysis failed' : ['queued', 'running'].includes(latest[d.id].status) ? 'Analysing…'
                      : `Analysed${latest[d.id].level ? ' · ' + latest[d.id].level.replace('_', ' ') : ''} · ${latest[d.id].review_status === 'confirmed' ? 'confirmed' : 'needs your review'}`}
                    {latest[d.id].level && <span aria-hidden="true">{LEVEL_STYLE[latest[d.id].level]?.icon}</span>}
                  </Link>
                )}
              </div>
              <div className="space-x-1">
                <Button variant="ghost" onClick={() => analyse(d)}>{latest[d.id] ? 'Analyse again' : 'Analyse'}</Button>
                <Button variant="ghost" onClick={() => setViewing(d)}>View</Button>
                {d.can_delete && <Button variant="ghost" onClick={() => remove(d)}>Delete</Button>}
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-slate-400">“Analyse” reads the document, checks the values, and prepares a plain-language report. You review and correct it before anything is saved.</p>
      </Card>

      {camera && <CameraCapture onClose={() => setCamera(false)} onCapture={(f) => { setCamera(false); pick(f); }} />}
      {viewing && <Viewer doc={viewing} onClose={() => setViewing(null)} />}
    </div>
  );
}
