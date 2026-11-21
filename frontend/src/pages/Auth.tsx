import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../auth'
import { AuthHero } from '../components/Layout'

export function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('ahmad.mansouri@example.com')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try {
      const u = await login(email, password)
      nav(u.roles.includes('CUSTOMER') ? '/' : '/review')
    } catch (ex) { setErr(ex instanceof ApiError ? ex.message : 'تعذر الاتصال بالخادم') } finally { setBusy(false) }
  }

  return (
    <div className="auth">
      <AuthHero />
      <section className="auth-form">
        <h1>أهلاً بك في صَدى</h1>
        <p className="lead">سجّل الدخول لإدارة أموالك وطلباتك بأمان.</p>
        <form onSubmit={submit}>
          <div className="field"><label>البريد الإلكتروني</label><input className="mono" type="email" value={email} onChange={e => setEmail(e.target.value)} required /></div>
          <div className="field"><label>كلمة المرور</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} required /></div>
          {err && <p className="error">{err}</p>}
          <button className="btn block" disabled={busy}>{busy ? '…' : 'تسجيل الدخول'}</button>
        </form>
        <p style={{ textAlign: 'center', marginTop: 16 }}>ليس لديك حساب؟ <Link to="/register">إنشاء حساب</Link></p>
        <div className="card soft" style={{ marginTop: 24, fontSize: 13 }}>
          إنذار الوصول تلقائياً حسب صلاحيات حسابك. لا يمكن اختيار دور الموظف من صفحة الدخول.
        </div>
      </section>
    </div>
  )
}

export function Register() {
  const { register } = useAuth()
  const nav = useNavigate()
  const [form, setForm] = useState({ full_name: '', email: '', password: '' })
  const [agree, setAgree] = useState(false)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try { await register(form.full_name, form.email, form.password); nav('/') }
    catch (ex) { setErr(ex instanceof ApiError ? ex.message : 'تعذر الاتصال بالخادم') } finally { setBusy(false) }
  }

  return (
    <div className="auth">
      <AuthHero />
      <section className="auth-form">
        <h1>حساب جديد، بداية مطمئنة</h1>
        <p className="lead">أدخل بياناتك لبدء تجربة مصرفية أكثر وضوحاً.</p>
        <form onSubmit={submit}>
          <div className="field"><label>الاسم الكامل</label><input value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} required minLength={3} /></div>
          <div className="field"><label>البريد الإلكتروني</label><input className="mono" type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required /></div>
          <div className="field">
            <label>كلمة المرور</label>
            <input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required minLength={8} />
            <span className="hint">8 أحرف على الأقل، مع رقم ورمز خاص.</span>
          </div>
          <label style={{ fontSize: 13, display: 'flex', gap: 8, marginBottom: 16 }}>
            <input type="checkbox" checked={agree} onChange={e => setAgree(e.target.checked)} /> أوافق على الشروط وسياسة الخصوصية
          </label>
          {err && <p className="error">{err}</p>}
          <button className="btn block" disabled={busy || !agree}>إنشاء حساب شخصي</button>
        </form>
        <p style={{ textAlign: 'center', marginTop: 16 }}>لديك حساب؟ <Link to="/login">تسجيل الدخول</Link></p>
      </section>
    </div>
  )
}
