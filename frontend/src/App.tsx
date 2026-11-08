import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom"
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
  const userId = useAppStore((s) => s.userId)
  return (
    <BrowserRouter>
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-glow shadow-[0_0_12px_var(--glow)]" />
            <span className="text-sm font-semibold tracking-wide">NovaStart</span>
          </Link>
          <div className="flex items-center gap-4">
            {userId != null && (
              <nav className="hidden items-center gap-4 sm:flex">
                <Link
                  to="/mailbox"
                  className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:text-foreground"
                >
                  信箱
                </Link>
                <Link
                  to="/records"
                  className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:text-foreground"
                >
                  记录
                </Link>
              </nav>
            )}
            <AccountSwitcher />
          </div>
        </div>
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
