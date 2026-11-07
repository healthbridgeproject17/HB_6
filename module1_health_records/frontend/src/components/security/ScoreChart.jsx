// Model score of the newest windows of one machine, drawn as a plain SVG line chart.
// For SIMULATED machines the background shows what the simulator was really doing (known only because it is a simulation).
const W = 640;
const H = 200;
const PAD = { l: 32, r: 8, t: 8, b: 8 };
const SLOTS = 60;

const PHASE_FILL = {
  recon: 'rgba(251,191,36,0.14)',
  encrypt: 'rgba(244,63,94,0.18)',
  exfil: 'rgba(244,63,94,0.18)',
  sleep: 'rgba(148,163,184,0.14)',
};

export default function ScoreChart({ windows, threshold }) {
  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const step = innerW / (SLOTS - 1);
  const x = (i) => PAD.l + i * step;
  const y = (s) => PAD.t + (1 - Math.min(Math.max(s, 0), 1)) * innerH;
  const points = windows.map((w, i) => `${x(i).toFixed(1)},${y(w.score).toFixed(1)}`).join(' ');
  const last = windows[windows.length - 1];
  const summary = last
    ? `Model score over the last ${windows.length} windows. Latest score ${last.score.toFixed(2)}${threshold != null ? `, alert threshold ${threshold}` : ''}.`
    : 'No windows yet.';

  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={summary}>
        {[0, 0.5, 1].map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} stroke="#1e293b" />
            <text x={4} y={y(v) + 4} fontSize="11" fill="#64748b">{v.toFixed(1)}</text>
          </g>
        ))}
        {windows.map((w, i) => PHASE_FILL[w.phase] && (
          <rect key={`p${w.seq}`} x={x(i) - step / 2} y={PAD.t} width={step} height={innerH} fill={PHASE_FILL[w.phase]} />
        ))}
        {threshold != null && (
          <line x1={PAD.l} x2={W - PAD.r} y1={y(threshold)} y2={y(threshold)} stroke="#fbbf24" strokeDasharray="5 4" />
        )}
        {windows.length > 1 && <polyline points={points} fill="none" stroke="#38bdf8" strokeWidth="2" strokeLinejoin="round" />}
        {windows.map((w, i) => (
          <circle key={w.seq} cx={x(i)} cy={y(w.score)} r={w.alert ? 4.5 : 2.5} fill={w.alert ? '#f43f5e' : w.above ? '#fbbf24' : '#34d399'} />
        ))}
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-400" />normal window</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-400" />score above threshold</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-rose-500" />alert (2 of last 3 windows)</span>
        <span><span className="mr-1 inline-block h-0 w-4 border-t border-dashed border-amber-400 align-middle" />threshold</span>
        <span>Shaded: what the simulator was doing (recon / attack / sleep)</span>
      </figcaption>
    </figure>
  );
}
