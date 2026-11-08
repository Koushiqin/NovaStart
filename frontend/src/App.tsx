import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import HomePage from "@/pages/HomePage"
import FocusPage from "@/pages/FocusPage"
import SettlePage from "@/pages/SettlePage"
import RecordsPage from "@/pages/RecordsPage"
import MailboxPage from "@/pages/MailboxPage"
import LoginPage from "@/pages/LoginPage"
import RegisterPage from "@/pages/RegisterPage"
import AccountSwitcher from "@/features/AccountSwitcher"
import { useAppStore } from "@/store/app"

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const userId = useAppStore((s) => s.userId)
  if (userId == null) return <Navigate to="/login" replace />
  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter>
      <header className="flex justify-end border-b bg-background px-4 py-2">
        <AccountSwitcher />
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/focus"
          element={
            <ProtectedRoute>
              <FocusPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settle"
          element={
            <ProtectedRoute>
              <SettlePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/mailbox"
          element={
            <ProtectedRoute>
              <MailboxPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/records"
          element={
            <ProtectedRoute>
              <RecordsPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
