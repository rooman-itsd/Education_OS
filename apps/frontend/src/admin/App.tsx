import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from './lib/router';
import { AuthProvider, useAuth } from './lib/auth';
import { LoginPage } from './pages/LoginPage';
import { AppLayout } from './components/layout/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { UsersPage } from './pages/UsersPage';
import { RolesPage } from './pages/RolesPage';
import { AdmissionsPage } from './pages/AdmissionsPage';
import { AuditPage } from './pages/AuditPage';
import { ModulesPage } from './pages/ModulesPage';
import { ModulePage } from './pages/ModulePage';
import { RoleDashboardsPage } from './pages/RoleDashboardsPage';
import { ProfilePage } from './pages/ProfilePage';
import { AccessPage } from './pages/AccessPage';

/** Waits for the session check; nothing renders until it is known. */
const Gate: React.FC<{ signedIn: boolean; to: string }> = ({ signedIn, to }) => {
  const { status } = useAuth();
  if (status === 'loading') return null;
  return (status === 'signed-in') === signedIn ? <Outlet /> : <Navigate to={to} replace />;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
    <BrowserRouter>
      <Routes>
        {/* Public Login */}
        <Route element={<Gate signedIn={false} to="/dashboard" />}>
          <Route path="/login" element={<LoginPage />} />
        </Route>

        {/* Protected ERP Shell: admins only */}
        <Route element={<Gate signedIn to="/login" />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/admissions" element={<AdmissionsPage />} />

          {/* Administration: platform/identity, platform/audit, module composition */}
          <Route path="/users" element={<UsersPage />} />
          <Route path="/roles" element={<RolesPage />} />
          <Route path="/dashboards" element={<RoleDashboardsPage />} />
          <Route path="/modules" element={<ModulesPage />} />
          <Route path="/modules/:moduleId" element={<ModulePage />} />
          <Route path="/audit-logs" element={<AuditPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/access" element={<AccessPage />} />

          {/* Default fallbacks */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
        </Route>
      </Routes>
    </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
