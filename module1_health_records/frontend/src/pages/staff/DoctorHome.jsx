import PatientSearch from '../../components/PatientSearch.jsx';

export default function DoctorHome() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Doctor dashboard</h1>
        <p className="text-sm text-slate-500">Search a patient to review their record, add notes and prescriptions.</p>
      </div>
      <PatientSearch />
    </div>
  );
}
