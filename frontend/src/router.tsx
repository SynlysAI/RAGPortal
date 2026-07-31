import { createBrowserRouter, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import Layout from '@/components/Layout'
import LoginPage from '@/pages/LoginPage'
import SsoPage from '@/pages/SsoPage'
import UploadPage from '@/pages/UploadPage'
import MyUploadsPage from '@/pages/MyUploadsPage'
import DashboardPage from '@/pages/admin/DashboardPage'
import UploadsAdminPage from '@/pages/admin/UploadsAdminPage'

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isInitialized } = useAuthStore()
  if (!isInitialized) {
    return <div className="min-h-screen flex items-center justify-center bg-slate-50 text-sm text-slate-500">加载中...</div>
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AdminGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore()
  if (user?.role !== 'admin') return <Navigate to="/upload" replace />
  return <>{children}</>
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/sso', element: <SsoPage /> },
  {
    element: <Layout />,
    children: [
      {
        path: '/upload',
        element: <AuthGuard><UploadPage /></AuthGuard>,
      },
      {
        path: '/my-uploads',
        element: <AuthGuard><MyUploadsPage /></AuthGuard>,
      },
      {
        path: '/admin',
        element: <Navigate to="/admin/dashboard" replace />,
      },
      {
        path: '/admin/dashboard',
        element: <AuthGuard><AdminGuard><DashboardPage /></AdminGuard></AuthGuard>,
      },
      {
        path: '/admin/uploads',
        element: <AuthGuard><AdminGuard><UploadsAdminPage /></AdminGuard></AuthGuard>,
      },
      { path: '*', element: <Navigate to="/upload" replace /> },
    ],
  },
])
