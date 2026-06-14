import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Chat } from './pages/Chat'
import { Dashboard } from './pages/Dashboard'
import { Discovery } from './pages/Discovery'
import { Episodes } from './pages/Episodes'
import { Logs } from './pages/Logs'
import { RSSSources } from './pages/RSSSources'
import { Subscriptions } from './pages/Subscriptions'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="subscriptions" element={<Subscriptions />} />
          <Route path="episodes" element={<Episodes />} />
          <Route path="discovery" element={<Discovery />} />
          <Route path="rss-sources" element={<RSSSources />} />
          <Route path="logs" element={<Logs />} />
          <Route path="chat" element={<Chat />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
