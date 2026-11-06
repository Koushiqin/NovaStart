import { BrowserRouter, Route, Routes } from "react-router-dom"
import HomePage from "@/pages/HomePage"
import FocusPage from "@/pages/FocusPage"
import SettlePage from "@/pages/SettlePage"
import RecordsPage from "@/pages/RecordsPage"

// 路由骨架：/ /focus /settle /records 四个占位页
function App() {
  return (
    <BrowserRouter>
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
