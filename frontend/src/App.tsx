import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom"
import HomePage from "@/pages/HomePage"
import FocusPage from "@/pages/FocusPage"
import SettlePage from "@/pages/SettlePage"
import RecordsPage from "@/pages/RecordsPage"
import LoginPage from "@/pages/LoginPage"
import RegisterPage from "@/pages/RegisterPage"
import AccountSwitcher from "@/features/AccountSwitcher"
import { useAppStore } from "@/store/app"

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const userId = useAppStore((s) => s.userId)
  if (userId == null) return <Navigate to="/login" replace />
  return <>{children}</>
}

// 首页是编辑式全屏首屏：顶栏只保留右侧账号控件；其余路由沿用带品牌与导航的顶栏
function AppHeader() {
  const userId = useAppStore((s) => s.userId)
  const location = useLocation()
  const isHome = location.pathname === "/"

  if (isHome) {
    return (
      <header className="absolute inset-x-0 top-0 z-40">
        <div className="mx-auto flex h-20 w-full max-w-[1200px] items-center justify-end px-6 sm:px-10">
          <AccountSwitcher />
        </div>
      </header>
    )
  }

  return (
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
  )
}

function AppShell() {
  return (
    <>
      <AppHeader />
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
          path="/records"
          element={
            <ProtectedRoute>
              <RecordsPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}

export default App
