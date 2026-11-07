export const cx = (...parts) => parts.filter(Boolean).join(' ');

export function fmtDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}
export function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString([], { dateStyle: 'medium' });
}

export function Card({ title, action, children, className }) {
  return (
    <section className={cx('rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5', className)}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

const buttonStyles = {
  primary: 'bg-teal-600 text-white hover:bg-teal-700 disabled:bg-teal-300',
  secondary: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50',
  danger: 'bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-300',
  ghost: 'text-teal-700 hover:bg-teal-50 disabled:opacity-50',
};
export function Button({ variant = 'primary', className, ...props }) {
  return (
    <button
      className={cx('min-h-[40px] rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed', buttonStyles[variant], className)}
      {...props}
    />
  );
}

export const inputCls =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base text-slate-800 sm:text-sm placeholder-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-100 disabled:bg-slate-100';

export function Field({ label, hint, children, className }) {
  return (
    <label className={cx('block', className)}>
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  );
}
export const Input = (props) => <input className={inputCls} {...props} />;
export const TextArea = (props) => <textarea rows={3} className={inputCls} {...props} />;
export const Select = ({ children, ...props }) => (
  <select className={inputCls} {...props}>{children}</select>
);

export function Alert({ kind = 'error', children }) {
  if (!children) return null;
  const tone = kind === 'error' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700';
  return <div className={cx('rounded-lg border px-3 py-2 text-sm', tone)}>{children}</div>;
}

const badgeTones = {
  slate: 'bg-slate-100 text-slate-600',
  teal: 'bg-teal-50 text-teal-700',
  green: 'bg-emerald-50 text-emerald-700',
  amber: 'bg-amber-50 text-amber-700',
  red: 'bg-rose-50 text-rose-700',
  blue: 'bg-sky-50 text-sky-700',
};
export function Badge({ tone = 'slate', children }) {
  return <span className={cx('inline-block rounded-full px-2.5 py-0.5 text-xs font-medium', badgeTones[tone])}>{children}</span>;
}

// tabs: [key, label, icon]. Desktop: tab bar under the header. Phones: a fixed
// bottom navigation bar (easy to reach with a thumb), like a normal app.
export function Tabs({ tabs, active, onChange }) {
  return (
    <>
      <div className="hidden gap-1 overflow-x-auto overflow-y-hidden border-b border-slate-200 sm:flex">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            onClick={() => onChange(key)}
            className={cx(
              '-mb-px whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium',
              active === key ? 'border-teal-600 text-teal-700' : 'border-transparent text-slate-500 hover:text-slate-700'
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <nav
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-slate-200 bg-white/95 backdrop-blur sm:hidden"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        {tabs.map(([key, label, icon]) => (
          <button
            key={key}
            onClick={() => onChange(key)}
            aria-label={label}
            className={cx(
              'flex min-w-0 flex-1 flex-col items-center gap-0.5 px-1 py-2 text-[11px] font-medium',
              active === key ? 'text-teal-700' : 'text-slate-400'
            )}
          >
            <span className="text-lg leading-none" aria-hidden="true">{icon || '•'}</span>
            <span className="w-full truncate text-center">{label}</span>
          </button>
        ))}
      </nav>
    </>
  );
}

// Slides up from the bottom on phones, centred card on larger screens.
export function Modal({ title, onClose, children, wide }) {
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-slate-900/50 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        className={cx('max-h-[92vh] w-full overflow-auto rounded-t-2xl bg-white p-4 shadow-xl sm:rounded-2xl sm:p-5', wide ? 'sm:max-w-3xl' : 'sm:max-w-lg')}
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="truncate text-base font-semibold text-slate-900">{title}</h2>
          <button onClick={onClose} className="rounded-lg px-3 py-1.5 text-sm text-slate-500 hover:bg-slate-100">Close</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export const fmtSize = (bytes) => (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round((bytes || 0) / 1024))} KB`);

export const Loading = ({ text = 'Loading…' }) => <p className="py-6 text-center text-sm text-slate-400">{text}</p>;
