import { useEffect, useRef } from 'react';
import { cx } from '../ui.jsx';

// Shared pieces of the dark Security page.

export const RISK = {
  low: { label: 'Low', cls: 'bg-sky-500/15 text-sky-300 ring-sky-500/40' },
  medium: { label: 'Medium', cls: 'bg-amber-500/15 text-amber-300 ring-amber-500/40' },
  high: { label: 'High', cls: 'bg-orange-500/15 text-orange-300 ring-orange-500/40' },
  critical: { label: 'Critical', cls: 'bg-rose-500/20 text-rose-300 ring-rose-500/50' },
};

export const MACHINE_STATUS = {
  no_data: { label: 'No data yet', dot: 'bg-slate-500' },
  normal: { label: 'Normal', dot: 'bg-emerald-400' },
  suspicious: { label: 'Suspicious', dot: 'bg-amber-400' },
  incident: { label: 'Incident open', dot: 'bg-rose-500 animate-pulse' },
  offline: { label: 'Offline', dot: 'bg-slate-500' },
  disabled: { label: 'Disabled', dot: 'bg-slate-600' },
};

export const INCIDENT_STATUS = { open: 'Open', acknowledged: 'Acknowledged', resolved: 'Resolved', false_positive: 'False alarm' };

export const GROUP_LABELS = {
  encryption: 'File encryption behaviour',
  backup_tampering: 'Backup or recovery tampering',
  spread: 'Spreading to other machines',
  outside_contact: 'Suspicious outside contact',
};

export const FAMILIES = [
  ['benign', 'Normal activity only'],
  ['fast_encryptor', 'Fast encryptor'],
  ['slow_drip', 'Slow drip (sleeps between bursts)'],
  ['network_spreader', 'Network spreader'],
  ['double_extortion', 'Data thief that also encrypts'],
];

export const familyLabel = (key) => (FAMILIES.find(([k]) => k === key) || [key, key])[1];

export const fmtTime = (iso) => {
  const d = iso ? new Date(iso) : null;
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
};

export function RiskBadge({ level }) {
  const r = RISK[level] || RISK.low;
  return <span className={cx('inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset', r.cls)}>{r.label} risk</span>;
}

export function Panel({ title, action, children, className }) {
  return (
    <section className={cx('rounded-2xl border border-slate-800 bg-slate-900 p-4 sm:p-5', className)}>
      {(title || action) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

const btn = {
  primary: 'bg-teal-500 text-slate-950 hover:bg-teal-400 disabled:bg-teal-900 disabled:text-slate-500',
  danger: 'bg-rose-500 text-white hover:bg-rose-400 disabled:bg-rose-950 disabled:text-slate-500',
  ghost: 'border border-slate-700 text-slate-200 hover:bg-slate-800 disabled:text-slate-600 disabled:hover:bg-transparent',
};
export function Btn({ variant = 'ghost', className, ...props }) {
  return (
    <button
      className={cx('min-h-[40px] rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed', btn[variant], className)}
      {...props}
    />
  );
}

export const darkField =
  'w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-base text-slate-100 sm:text-sm placeholder-slate-500 focus:border-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-900';

export function DarkAlert({ children }) {
  if (!children) return null;
  return <div role="alert" className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{children}</div>;
}

// Calls `fn` every `ms` milliseconds (skipping while the tab is hidden or the previous call is still running).
export function usePoll(fn, ms, deps = []) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    let busy = false;
    const tick = async () => {
      if (busy || document.hidden) return;
      busy = true;
      try { await ref.current(); } finally { busy = false; }
    };
    tick();
    const timer = setInterval(tick, ms);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, ...deps]);
}
