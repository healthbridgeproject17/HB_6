import { Navigate, Route, Routes } from 'react-router-dom';
import { RequireRole, Shell } from './components/Layout.jsx';
import Landing from './pages/Landing.jsx';
import Login from './pages/Login.jsx';
import Register from './pages/Register.jsx';
import PatientDashboard from './pages/patient/PatientDashboard.jsx';
import DoctorHome from './pages/staff/DoctorHome.jsx';
import PatientDetail from './pages/staff/PatientDetail.jsx';
import AdminDashboard from './pages/admin/AdminDashboard.jsx';
import ChangePassword from './pages/ChangePassword.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login/:portal" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<Shell />}>
        <Route path="/change-password" element={<RequireRole roles={['patient', 'doctor', 'admin']} allowPending><ChangePassword /></RequireRole>} />
        <Route path="/patient" element={<RequireRole roles={['patient']}><PatientDashboard /></RequireRole>} />
        <Route path="/doctor" element={<RequireRole roles={['doctor']}><DoctorHome /></RequireRole>} />
        <Route path="/admin" element={<RequireRole roles={['admin']}><AdminDashboard /></RequireRole>} />
        <Route path="/staff/patients/:id" element={<RequireRole roles={['doctor', 'admin']}><PatientDetail /></RequireRole>} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
