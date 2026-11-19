import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth'
import { Shell } from './components/Layout'
import { Login, Register } from './pages/Auth'
import { Home } from './pages/Home'
import { CaseReview, ReviewQueue } from './pages/Review'
import { NewTicket, TicketsList } from './pages/Support'
import { NewTransfer, TransfersList } from './pages/Transfers'
import './styles/global.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<Shell />}>
            <Route path="/" element={<Home />} />
            <Route path="/transfers" element={<TransfersList />} />
            <Route path="/transfers/new" element={<NewTransfer />} />
            <Route path="/support" element={<TicketsList />} />
            <Route path="/support/new" element={<NewTicket />} />
            <Route path="/review" element={<ReviewQueue />} />
            <Route path="/review/:id" element={<CaseReview />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>,
)
