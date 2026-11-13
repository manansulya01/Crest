import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from './lib/theme';
import { ToastProvider } from './lib/toast';
import { AppLayout } from './components/AppLayout';
import { PublicLayout } from './components/PublicLayout';
import { LandingPage } from './pages/LandingPage';
import { DocsPage } from './pages/DocsPage';
import { SecurityPage } from './pages/SecurityPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { DashboardPage } from './pages/DashboardPage';
import { TasksPage } from './pages/TasksPage';
import { NewTaskPage } from './pages/NewTaskPage';
import { TaskDetailPage } from './pages/TaskDetailPage';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { AutonomyPage } from './pages/AutonomyPage';
import { ProvidersPage } from './pages/ProvidersPage';
import { RoutingPage } from './pages/RoutingPage';
import { EvidencePage } from './pages/EvidencePage';
import { AuditPage } from './pages/AuditPage';
import { BudgetsPage } from './pages/BudgetsPage';
import { DemosPage } from './pages/DemosPage';
import { SettingsPage } from './pages/SettingsPage';
import { SystemPage } from './pages/SystemPage';

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<PublicLayout />}>
              <Route path="/" element={<LandingPage />} />
              <Route path="/docs" element={<DocsPage />} />
              <Route path="/security" element={<SecurityPage />} />
            </Route>
            <Route path="/app" element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="tasks" element={<TasksPage />} />
              <Route path="tasks/new" element={<NewTaskPage />} />
              <Route path="tasks/:taskId" element={<TaskDetailPage />} />
              <Route path="approvals" element={<ApprovalsPage />} />
              <Route path="autonomy" element={<AutonomyPage />} />
              <Route path="providers" element={<ProvidersPage />} />
              <Route path="routing" element={<RoutingPage />} />
              <Route path="evidence" element={<EvidencePage />} />
              <Route path="audit" element={<AuditPage />} />
              <Route path="budgets" element={<BudgetsPage />} />
              <Route path="demos" element={<DemosPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="system" element={<SystemPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  );
}
