import { NavLink, Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth'

export function Shell() {
  const { user, loading, logout } = useAuth()
  if (loading) return <div className="page">جارٍ التحميل…</div>
  if (!user) return <Navigate to="/login" replace />
  const staff = user.roles.includes('REVIEW_EMPLOYEE') || user.roles.includes('SYSTEM_ADMIN')
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">صَدى<small>SADA / DIGITAL BANKING</small></div>
          <nav className="nav">
            <NavLink to="/" end>الرئيسية</NavLink>
            <NavLink to="/transfers">التحويلات</NavLink>
            <NavLink to="/support">تذاكر الدعم</NavLink>
            {staff && <NavLink to="/review">قائمة المراجعة</NavLink>}
          </nav>
          <div className="who">
            <strong>{user.full_name}</strong>
            <span>{staff ? user.roles.join(' · ') : 'حساب شخصي · SAR'}</span>
          </div>
          <button className="btn secondary" onClick={logout}>خروج</button>
        </div>
      </header>
      <main className="page"><Outlet /></main>
      <footer className="footer">صدى © 2026 · منصة مصرفية رقمية · نموذج أولي أكاديمي</footer>
    </>
  )
}

export function Chip({ s }: { s: string }) {
  const ar: Record<string, string> = {
    COMPLETED: 'مكتمل', HELD: 'معلّق', CANCELLED: 'ملغى', PENDING_REVIEW: 'قيد المراجعة', SUBMITTED: 'مُرسل',
    APPROVED: 'مقبول', REJECTED: 'مرفوض', OPEN: 'مفتوحة', IN_REVIEW: 'قيد المراجعة', ACCEPTED: 'مقبولة', UNAVAILABLE: 'غير متاح',
  }
  return <span className={`chip ${s}`}>{s} · {ar[s] ?? s}</span>
}

export function AuthHero() {
  return (
    <aside className="auth-hero">
      <h2>مصرفك أقرب.<br />وثقتك أولاً.</h2>
      <p>تجربة مصرفية هادئة، وتحويلات واضحة، وحماية تضع الإنسان في قلب القرار.</p>
      <div className="box">
        <strong>حماية متعددة الطبقات</strong>
        <ol>
          <li>01 تحقق آمن من العمليات الحساسة</li>
          <li>02 إشارات مخاطر قابلة للتفسير</li>
          <li>03 مراجعة بشرية عند الحاجة</li>
        </ol>
      </div>
    </aside>
  )
}
