import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, createTheme, CssBaseline, useMediaQuery } from '@mui/material';
import { useAuthStore } from './store/authStore';
import { useCurrentUser } from './features/auth/api';
import { AuthGuard, RoleGuard, PermissionGuard } from './components/guards';
import Layout from './components/layout/Layout';
import LoginPage from './features/auth/components/LoginPage';
import DashboardPage from './features/auth/components/DashboardPage';
import ProfilePage from './features/auth/components/ProfilePage';
import UsersPage from './features/users/components/UsersPage';
import RolesPage from './features/roles/components/RolesPage';
import PermissionsPage from './features/permissions/components/PermissionsPage';
import AuthorizationExamples from './pages/AuthorizationExamples';
import AuditLogsPage from './features/audit/components/AuditLogsPage';
import ForbiddenPage from './pages/ForbiddenPage';
import NotFoundPage from './pages/NotFoundPage';
import LoadingScreen from './components/ui/LoadingScreen';

// ── Theme Hook ────────────────────────────────────────────────────────────────
function AppTheme({ children }: { children: React.ReactNode }) {
  const prefersDark = useMediaQuery('(prefers-color-scheme: dark)');
  const theme = createTheme({
    palette: {
      mode: prefersDark ? 'dark' : 'light',
      primary: { main: '#1976d2' },
      secondary: { main: '#dc004e' },
      background: {
        default: prefersDark ? '#121212' : '#f5f5f5',
        paper: prefersDark ? '#1e1e1e' : '#ffffff',
      },
    },
    typography: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    },
  });

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}

// ── Query Client ──────────────────────────────────────────────────────────────
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// ── Protected Route ───────────────────────────────────────────────────────────
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore();
  const { data: user, isLoading: userLoading } = useCurrentUser();
  const location = useLocation();

  if (isLoading || userLoading) return <LoadingScreen />;
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

// ── Guest Route (redirects to dashboard if already authenticated) ─────────────
function GuestRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore();
  const { data: user, isLoading: userLoading } = useCurrentUser();

  if (isLoading || userLoading) return <LoadingScreen />;
  if (isAuthenticated && user) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppTheme>
        <BrowserRouter>
          <Routes>
            <Route
              path="/login"
              element={
                <GuestRoute>
                  <LoginPage />
                </GuestRoute>
              }
            />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="profile" element={<ProfilePage />} />

              {/* Role-based route example: Only ADMIN and SUPERADMIN can access users */}
              <Route
                path="users"
                element={
                  <RoleGuard allowedRoles={['ADMIN', 'SUPERADMIN']} fallback={<ForbiddenPage />}>
                    <UsersPage />
                  </RoleGuard>
                }
              />

              {/* Permission-based route example: Only users with 'accounts.add_user' permission */}
              <Route
                path="users/create"
                element={
                  <PermissionGuard requiredPermissions="accounts.add_user" fallback={<ForbiddenPage />}>
                    <UsersPage />
                  </PermissionGuard>
                }
              />

              <Route
                path="roles"
                element={
                  <RoleGuard allowedRoles={['ADMIN', 'SUPERADMIN']} fallback={<ForbiddenPage />}>
                    <RolesPage />
                  </RoleGuard>
                }
              />

              {/* Legacy administration route (uses same new component) */}
              <Route
                path="administration/roles"
                element={
                  <RoleGuard allowedRoles={['ADMIN', 'SUPERADMIN']} fallback={<ForbiddenPage />}>
                    <RolesPage />
                  </RoleGuard>
                }
              />

              <Route
                path="permissions"
                element={
                  <RoleGuard allowedRoles={['SUPERADMIN']} fallback={<ForbiddenPage />}>
                    <PermissionsPage />
                  </RoleGuard>
                }
              />

              <Route path="forbidden" element={<ForbiddenPage />} />
              <Route path="auth-examples" element={<AuthorizationExamples />} />
              <Route path="audit-log" element={<AuditLogsPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </BrowserRouter>
      </AppTheme>
    </QueryClientProvider>
  );
}
