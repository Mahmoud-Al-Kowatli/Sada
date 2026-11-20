import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDate, fmtMoney, type Account, type Ticket, type Transfer } from '../api/client'
import { useAuth } from '../auth'
import { Chip } from '../components/Layout'

export function Home() {
  const { user } = useAuth()
  const [acc, setAcc] = useState<Account | null>(null)
  const [transfers, setTransfers] = useState<Transfer[]>([])
  const [tickets, setTickets] = useState<Ticket[]>([])

  useEffect(() => {
    api<Account[]>('/accounts').then(async ({ data }) => {
      const a = data[0]; setAcc(a)
      if (a) setTransfers((await api<Transfer[]>(`/accounts/${a.account_id}/transfers`)).data)
    })
    api<Ticket[]>('/tickets').then(({ data }) => setTickets(data))
  }, [])

  if (!acc) return <p>لا يوجد حساب مرتبط بهذا المستخدم.</p>
  const hour = new Date().getHours()
  const greet = hour < 12 ? 'صباح الخير' : 'مساء الخير'

  return (
    <>
      <div className="crumbs">الرئيسية / نظرة عامة</div>
      <h1>{greet}، {user?.full_name.split(' ')[0]}</h1>
      <p className="lead">كل ما تحتاجه لإدارة أموالك، في مكان واحد.</p>

      <div className="grid grid-4">
        <div className="card primary"><div className="kpi-label">الرصيد المتاح</div><div className="kpi num">{Number(acc.available_balance).toLocaleString('en-US', { minimumFractionDigits: 2 })}</div><div className="kpi-sub">ريال سعودي</div></div>
        <div className="card"><div className="kpi-label">الرصيد المجمّد ⓘ</div><div className="kpi num">{Number(acc.frozen_balance).toLocaleString('en-US', { minimumFractionDigits: 2 })}</div><div className="kpi-sub">مخصص لتحويل قيد المراجعة</div></div>
        <div className="card"><div className="kpi-label">الحد اليومي للتحويل</div><div className="kpi num">{Number(acc.daily_used).toLocaleString('en-US')} / {Number(acc.daily_limit).toLocaleString('en-US')}</div><div className="kpi-sub">المتبقي اليوم {fmtMoney(Number(acc.daily_limit) - Number(acc.daily_used))}</div></div>
        <div className="card"><div className="kpi-label">رقم الحساب</div><div className="kpi num" style={{ fontSize: 20 }}>{acc.account_number.replace(/(\d{4})(?=\d)/g, '$1 ')}</div><div className="kpi-sub">حساب جاري · {acc.currency}</div></div>
      </div>

      <div className="actions" style={{ justifyContent: 'flex-start' }}>
        <Link className="btn" to="/transfers/new">← تحويل داخلي جديد</Link>
        <Link className="btn secondary" to="/support/new">طلب دعم حساس</Link>
        <span className="hint" style={{ alignSelf: 'center' }}>حماية تعمل بهدوء: كل إجراء حساس يمر بالتحقق المناسب.</span>
      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <h3>آخر التحويلات وطلبات الدعم</h3>
        <table>
          <thead><tr><th>العملية / المرجع</th><th>المستفيد أو نوع الطلب</th><th>المبلغ</th><th>الحالة</th><th>التاريخ</th></tr></thead>
          <tbody>
            {[...transfers.map(t => ({ k: t.reference, who: t.destination_name ?? t.destination_account_number, amt: fmtMoney(t.amount), st: t.status, at: t.created_at, link: '/transfers' })),
              ...tickets.map(t => ({ k: t.reference, who: REQUEST_AR[t.request_type] ?? t.request_type, amt: '—', st: t.status, at: t.created_at, link: '/support' }))]
              .sort((a, b) => b.at.localeCompare(a.at)).slice(0, 8)
              .map(r => <tr key={r.k}><td><Link to={r.link} className="mono">{r.k}</Link></td><td>{r.who}</td><td className="num">{r.amt}</td><td><Chip s={r.st} /></td><td>{fmtDate(r.at)}</td></tr>)}
            {!transfers.length && !tickets.length && <tr><td colSpan={5} className="hint">لا توجد عمليات بعد.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  )
}

export const REQUEST_AR: Record<string, string> = { RAISE_LIMIT: 'رفع حد التحويل اليومي', RELEASE_HELD: 'تحرير تحويل معلّق', UPDATE_CONTACT: 'تحديث بيانات التواصل' }
