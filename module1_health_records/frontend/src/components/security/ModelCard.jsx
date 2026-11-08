import { Panel, familyLabel } from './parts.jsx';

const pct = (v) => `${Math.round(v * 100)}%`;

// The honest summary of how the detector was tested. The caveats come from the backend and are always shown.
export default function ModelCard({ state }) {
  if (state.loading) return <Panel title="Detection model"><p className="text-sm text-slate-400">Loading…</p></Panel>;
  if (state.error) return <Panel title="Detection model"><p className="text-sm text-amber-300">{state.error}</p></Panel>;
  const s = state.summary;
  const seen = s.seen_families;
  const unseen = Object.entries(s.unseen_families || {});
  const hours = seen.false_alarms_per_machine_hour > 0 ? Math.round(1 / seen.false_alarms_per_machine_hour) : null;
  const slow = unseen.reduce((worst, cur) => (!worst || cur[1].detection_rate < worst[1].detection_rate ? cur : worst), null);
  return (
    <Panel title="How well does the detector work?" action={<span className="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-semibold text-amber-300 ring-1 ring-inset ring-amber-500/40">Tested on simulated data</span>}>
      <div className="mb-4 rounded-xl border border-slate-700 bg-slate-950 p-3 text-sm text-slate-200">
        <div className="mb-1 font-semibold text-slate-100">In plain words</div>
        <ul className="list-disc space-y-1 pl-5">
          <li>In the tests, it caught <b>{pct(seen.detection_rate)}</b> of the attacks it had been taught about (the true figure could be as low as {pct(seen.detection_ci95[0])}), and raised the alert about <b>{seen.median_delay_seconds} seconds</b> after the attack began.</li>
          <li>On normal activity it gave a false alarm about <b>{hours ? `once every ${hours} hours` : 'rarely'}</b>. This is uncertain, because only {seen.benign_hours} hours of normal activity were tested.</li>
          {slow && <li>A sneaky attack it had <b>never seen</b> ({familyLabel(slow[0]).toLowerCase()}) was caught only <b>{pct(slow[1].detection_rate)}</b> of the time, and later (about {slow[1].median_delay_seconds} seconds).</li>}
          <li>All of this uses <b>simulated</b> data. It shows the method works, not how it would do on real hospital computers.</li>
        </ul>
      </div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">The details</h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
        <div><dt className="text-xs text-slate-500">Model</dt><dd className="font-medium text-slate-100">{s.model.replace(/_/g, ' ')}</dd></div>
        <div><dt className="text-xs text-slate-500">Alert line (danger score)</dt><dd className="font-medium text-slate-100">{Number(s.threshold).toFixed(2)}</dd></div>
        <div><dt className="text-xs text-slate-500">Alert rule</dt><dd className="font-medium text-slate-100">{s.alert_rule.k} of the last {s.alert_rule.m} checks</dd></div>
        <div><dt className="text-xs text-slate-500">One check covers</dt><dd className="font-medium text-slate-100">{s.window_seconds} seconds</dd></div>
        <div><dt className="text-xs text-slate-500">Known attack families caught</dt><dd className="font-medium text-slate-100">{pct(seen.detection_rate)} <span className="text-xs text-slate-500">({pct(seen.detection_ci95[0])}–{pct(seen.detection_ci95[1])})</span></dd></div>
        <div><dt className="text-xs text-slate-500">Median time to alert</dt><dd className="font-medium text-slate-100">{seen.median_delay_seconds}s</dd></div>
        <div><dt className="text-xs text-slate-500">False alarms / machine-hour</dt><dd className="font-medium text-slate-100">{seen.false_alarms_per_machine_hour} <span className="text-xs text-slate-500">(up to {seen.false_alarms_upper95_per_machine_hour})</span></dd></div>
        <div><dt className="text-xs text-slate-500">Normal activity tested</dt><dd className="font-medium text-slate-100">{seen.benign_hours} h simulated</dd></div>
      </dl>

      {unseen.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Attack family left out of training (never seen), one at a time</h3>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-500"><tr><th className="py-1 font-medium">Family</th><th className="font-medium">Caught</th><th className="font-medium">Median delay</th></tr></thead>
            <tbody className="divide-y divide-slate-800">
              {unseen.map(([name, v]) => (
                <tr key={name}><td className="py-1 text-slate-200">{familyLabel(name)}</td><td>{pct(v.detection_rate)}</td><td>{v.median_delay_seconds}s</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ul className="mt-4 space-y-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100/90">
        {s.caveats.map((c) => <li key={c}>• {c}</li>)}
      </ul>
    </Panel>
  );
}
