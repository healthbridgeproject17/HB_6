import { Link, Navigate } from 'react-router-dom';
import { homeFor, useAuth } from '../context/AuthContext.jsx';
import { Loading } from '../components/ui.jsx';

const portals = [
  ['patient', 'Patient', 'View your records, prescriptions and track your medicines.'],
  ['doctor', 'Doctor', 'Search patients, add clinical notes and prescriptions.'],
  ['admin', 'Admin', 'Manage accounts and review the audit trail.'],
];

export default function Landing() {
  const { user, booting } = useAuth();
  if (booting) return <Loading />;
  if (user) return <Navigate to={homeFor(user.role)} replace />;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-sky-50 via-white to-teal-50 px-4 py-10">
      <div className="mb-8 text-center">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-600 text-2xl text-white">+</div>
        <h1 className="text-3xl font-bold text-slate-900">HealthBridge</h1>
        <p className="mt-1 text-slate-500">Secure digital health records</p>
      </div>
      <div className="grid w-full max-w-3xl gap-4 sm:grid-cols-3">
        {portals.map(([key, title, text]) => (
          <Link key={key} to={`/login/${key}`} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-teal-300 hover:shadow-md">
            <h2 className="font-semibold text-teal-700">{title} login</h2>
            <p className="mt-2 text-sm text-slate-500">{text}</p>
          </Link>
        ))}
      </div>
      <p className="mt-6 text-sm text-slate-500">
        New patient? <Link to="/register" className="font-medium text-teal-700 hover:underline">Create an account</Link>
      </p>
      <p className="mt-8 text-xs text-slate-400">Demonstration system. Uses fictional data only.</p>
    </div>
  );
}
