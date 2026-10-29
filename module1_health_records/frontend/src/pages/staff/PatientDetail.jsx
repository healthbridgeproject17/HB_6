import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../api/client.js';
import { useAuth } from '../../context/AuthContext.jsx';
import { useLoad } from '../../hooks.js';
import { Alert, Loading, Tabs } from '../../components/ui.jsx';
import PatientHeader from '../../components/PatientHeader.jsx';
import ProfileForm from '../../components/ProfileForm.jsx';
import RecordsPanel from '../../components/RecordsPanel.jsx';
import PrescriptionsPanel from '../../components/PrescriptionsPanel.jsx';
import MedicationPanel from '../../components/MedicationPanel.jsx';
import DocumentsPanel from '../../components/DocumentsPanel.jsx';

// Doctor and admin view of one patient. What each role can DO is decided here
// for the screen and enforced again by the backend.
export default function PatientDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const isDoctor = user.role === 'doctor';
  const isAdmin = user.role === 'admin';
  const { data: patient, loading, error, reload } = useLoad(() => api(`/patients/${id}`).then((r) => r.patient), [id]);
  const [tab, setTab] = useState('records');

  if (loading && !patient) return <Loading />;
  if (error) return <div className="space-y-3"><Alert>{error}</Alert><Link className="text-sm text-teal-700" to={isDoctor ? '/doctor' : '/admin'}>← Back</Link></div>;
  if (!patient) return null;

  return (
    <div className="space-y-5">
      <Link className="text-sm text-teal-700 hover:underline" to={isDoctor ? '/doctor' : '/admin'}>← Back to patients</Link>
      <PatientHeader patient={patient} />
      <Tabs
        active={tab} onChange={setTab}
        tabs={[['records', 'Records', '📋'], ['prescriptions', 'Prescriptions', '📄'], ['medication', 'Medicines', '💊'], ['documents', 'Documents', '📎'], ['profile', 'Profile', '👤']]}
      />
      {tab === 'records' && <RecordsPanel patientId={patient.id} canCreate={isDoctor} canAmend={isDoctor || isAdmin} />}
      {tab === 'prescriptions' && <PrescriptionsPanel patientId={patient.id} canWrite={isDoctor} />}
      {tab === 'medication' && <MedicationPanel patientId={patient.id} canLog={false} />}
      {tab === 'documents' && <DocumentsPanel patientId={patient.id} />}
      {tab === 'profile' && <ProfileForm key={patient.id} patient={patient} canEdit={isAdmin} canPhoto={isAdmin} onChanged={reload} />}
    </div>
  );
}
