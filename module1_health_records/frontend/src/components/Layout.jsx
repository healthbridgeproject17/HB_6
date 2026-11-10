import { Link, Navigate, Outlet } from 'react-router-dom';
import { homeFor, useAuth } from '../context/AuthContext.jsx';
import { Badge, Button, Loading } from './ui.jsx';

export function Shell() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-teal-50">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-3 py-3 sm:px-4">
          <Link to={homeFor(user?.role)} className="flex items-center gap-2 text-lg font-bold text-teal-700">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-600 text-white">+</span>
            HealthBridge
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="hidden text-right text-sm sm:block">
              <div className="font-medium text-slate-800">{user?.name}</div>
              <div className="text-xs text-slate-400">{user?.email}</div>
            </div>
            <Badge tone="teal">{user?.role}</Badge>
            <Link to="/change-password" className="hidden text-sm text-slate-500 hover:text-teal-700 md:inline">Password</Link>
            <Link to="/account/security" className="hidden text-sm text-slate-500 hover:text-teal-700 md:inline">Two-factor</Link>
            <Button variant="secondary" onClick={logout}>Log out</Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-3 py-4 pb-24 sm:px-4 sm:py-6 sm:pb-6">
        <Outlet />
      </main>
    </div>
  );
}

// Keeps pages behind login AND the right role. (The backend checks again on
// every request; this only decides which screens are shown.)
export function RequireRole({ roles, allowPending, children }) {
  const { user, booting } = useAuth();
  if (booting) return <Loading />;
  if (!user) return <Navigate to="/" replace />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  if (user.must_change_password && !allowPending) return <Navigate to="/change-password" replace />;
  return children;
}
