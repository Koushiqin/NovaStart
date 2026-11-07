import { BrowserRouter, Route, Routes } from "react-router-dom"
import HomePage from "@/pages/HomePage"
import FocusPage from "@/pages/FocusPage"
import SettlePage from "@/pages/SettlePage"
import RecordsPage from "@/pages/RecordsPage"
import AccountSwitcher from "@/features/AccountSwitcher"

// 路由骨架：/ /focus /settle /records 四个占位页；顶部常驻演示账号切换器
function App() {
  return (
    <BrowserRouter>
      <header className="flex justify-end border-b bg-background px-4 py-2">
        <AccountSwitcher />
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/focus" element={<FocusPage />} />
        <Route path="/settle" element={<SettlePage />} />
        <Route path="/records" element={<RecordsPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
