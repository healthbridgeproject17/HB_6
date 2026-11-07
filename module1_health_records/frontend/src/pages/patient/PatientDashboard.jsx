import { useState } from 'react';
import { api } from '../../api/client.js';
import { useLoad } from '../../hooks.js';
import { Alert, Loading, Tabs } from '../../components/ui.jsx';
import PatientHeader from '../../components/PatientHeader.jsx';
import ProfileForm from '../../components/ProfileForm.jsx';
import RecordsPanel from '../../components/RecordsPanel.jsx';
import PrescriptionsPanel from '../../components/PrescriptionsPanel.jsx';
import MedicationPanel from '../../components/MedicationPanel.jsx';
import DocumentsPanel from '../../components/DocumentsPanel.jsx';
import LabResultsPanel from '../../components/LabResultsPanel.jsx';

export default function PatientDashboard() {
  const { data: patient, loading, error, reload } = useLoad(() => api('/patients/me').then((r) => r.patient), []);
  const [tab, setTab] = useState('medication');

  if (loading && !patient) return <Loading />;
  if (error) return <Alert>{error}</Alert>;
  if (!patient) return null;

  return (
    <div className="space-y-5">
      <PatientHeader patient={patient} />
      <Tabs
        active={tab} onChange={setTab}
        tabs={[['medication', 'Medicines', '💊'], ['prescriptions', 'Prescriptions', '📄'], ['records', 'Records', '📋'], ['documents', 'Documents', '📎'], ['results', 'Results', '🧪'], ['profile', 'Profile', '👤']]}
      />
      {tab === 'medication' && <MedicationPanel patientId={patient.id} canLog />}
      {tab === 'prescriptions' && <PrescriptionsPanel patientId={patient.id} canWrite={false} />}
      {tab === 'records' && <RecordsPanel patientId={patient.id} canCreate={false} canAmend={false} />}
      {tab === 'documents' && <DocumentsPanel patientId={patient.id} />}
      {tab === 'results' && <LabResultsPanel patientId={patient.id} />}
      {tab === 'profile' && <ProfileForm key={patient.id} patient={patient} canEdit canPhoto onChanged={reload} />}
    </div>
  );
}
