import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client.js';
import { Alert, Button, Loading } from './ui.jsx';

// Shows the page picture the computer actually read, with boxes drawn where
// values were found. Boxes use percentages, so they stay in place at any size.
export default function DocumentPageViewer({ jobId, pages, selected, flagged = [] }) {
  const [page, setPage] = useState(1);
  const [url, setUrl] = useState(null);
  const [error, setError] = useState('');
  const boxRef = useRef(null);
  const meta = pages.find((p) => p.page === page) || pages[0];

  useEffect(() => {
    if (selected && selected.page !== page) setPage(selected.page);
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let alive = true;
    let made = null;
    setUrl(null);
    setError('');
    api(`/analysis/${jobId}/pages/${page}/image`, { raw: true })
      .then((blob) => { if (alive) { made = URL.createObjectURL(blob); setUrl(made); } })
      .catch(() => alive && setError('The page picture is not available.'));
    return () => { alive = false; if (made) URL.revokeObjectURL(made); };
  }, [jobId, page]);

  useEffect(() => {
    boxRef.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
  }, [selected, url]);

  const box = (b, className, ref) => (
    <div
      ref={ref}
      className={className}
      style={{ left: `${(b.bbox[0] / meta.width) * 100}%`, top: `${(b.bbox[1] / meta.height) * 100}%`,
        width: `${((b.bbox[2] - b.bbox[0]) / meta.width) * 100}%`, height: `${((b.bbox[3] - b.bbox[1]) / meta.height) * 100}%` }}
    />
  );
  const here = (b) => b && b.bbox && b.page === page;

  return (
    <div>
      {pages.length > 1 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {pages.map((p) => <Button key={p.page} variant={p.page === page ? 'primary' : 'secondary'} onClick={() => setPage(p.page)}>Page {p.page}</Button>)}
        </div>
      )}
      <Alert>{error}</Alert>
      {!url && !error && <Loading text="Loading the page…" />}
      {url && (
        <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white">
          <img src={url} alt={`Page ${page} of the document`} className="block w-full" />
          {flagged.filter(here).map((b, i) => <div key={i}>{box(b, 'pointer-events-none absolute rounded-sm border-2 border-amber-400 bg-amber-300/20')}</div>)}
          {here(selected) && box(selected, 'pointer-events-none absolute rounded-sm border-[3px] border-rose-500 bg-rose-400/25 shadow-[0_0_0_4px_rgba(244,63,94,0.25)]', boxRef)}
        </div>
      )}
      <p className="mt-2 text-xs text-slate-400">
        {meta?.method === 'ocr' ? `Read by the computer with ${Math.round(meta.mean_confidence * 100)}% average confidence. ` : 'Digital document: text read exactly. '}
        Yellow boxes mark values that need checking; the red box shows the selected value.
        {meta?.quality?.issues?.length ? ` Picture problems: ${meta.quality.issues.join(', ')}.` : ''}
      </p>
      {url && <a href={url} target="_blank" rel="noreferrer" className="text-sm text-teal-700 hover:underline">Open this page full size</a>}
    </div>
  );
}
