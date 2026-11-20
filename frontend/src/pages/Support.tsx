import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, api, fmtDate, type Account, type Ticket } from '../api/client'
import { Chip } from '../components/Layout'
import { REQUEST_AR } from './Home'

export function TicketsList() {
  const [rows, setRows] = useState<Ticket[]>([])
  useEffect(() => { api<Ticket[]>('/tickets').then(({ data }) => setRows(data)) }, [])
  return (
    <>
      <div className="crumbs">الرئيسية / تذاكر الدعم</div>
      <h1>تذاكر الدعم</h1>
      <p className="lead">طلباتك الحساسة وتحديثاتها في مكان واحد.</p>
      <Link to="/support/new" className="btn">طلب دعم حساس جديد</Link>
      <div className="card" style={{ marginTop: 24 }}>
        <table>
          <thead><tr><th>رقم التذكرة</th><th>نوع الطلب</th><th>الحالة</th><th>التقييم الصوتي</th><th>آخر تحديث</th></tr></thead>
          <tbody>
            {rows.map(t => <tr key={t.ticket_id}><td className="mono">{t.reference}</td><td>{REQUEST_AR[t.request_type] ?? t.request_type}</td><td><Chip s={t.status} />{t.case_reference && <div className="hint mono">{t.case_reference}</div>}</td><td className="hint">{t.assessment_status ?? '—'}</td><td>{fmtDate(t.created_at)}</td></tr>)}
            {!rows.length && <tr><td colSpan={5} className="hint">لا توجد طلبات بعد.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="card soft" style={{ marginTop: 16 }}>
        <strong>كل طلب يُتابع برقم مرجعي واضح</strong>
        <p className="hint">حالة «مُرسل» تعني أن طلبك وصل. حالة «قيد المراجعة» تعني أن موظفاً مختصاً يراجع الأدلة قبل اعتماد أي تغيير.</p>
      </div>
    </>
  )
}

export function NewTicket() {
  const nav = useNavigate()
  const [acc, setAcc] = useState<Account | null>(null)
  const [type, setType] = useState('RAISE_LIMIT')
  const [desc, setDesc] = useState('أرغب في رفع حد التحويل اليومي إلى 30,000 ر.س لتغطية التزامات شخصية قادمة.')
  const [file, setFile] = useState<File | null>(null)
  const [agree, setAgree] = useState(false)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<Ticket | null>(null)

  useEffect(() => { api<Account[]>('/accounts').then(({ data }) => setAcc(data[0])) }, [])

  const submit = async (e: FormEvent) => {
    e.preventDefault(); if (!acc || !file) return
    setErr(''); setBusy(true)
    const fd = new FormData()
    fd.append('account_id', acc.account_id); fd.append('request_type', type); fd.append('description', desc); fd.append('file', file)
    try { setDone((await api<Ticket>('/tickets', { method: 'POST', body: fd })).data) }
    catch (ex) { setErr(ex instanceof ApiError ? ex.message : 'تعذر الاتصال بالخادم') } finally { setBusy(false) }
  }

  if (done) return (
    <div className="card result" style={{ maxWidth: 640, margin: '40px auto' }}>
      <Chip s={done.status} />
      <h1 style={{ marginTop: 12 }}>تم حفظ طلبك وتسجيلك الصوتي</h1>
      <div className="hint">رقم التذكرة</div>
      <div className="ref mono">{done.reference}</div>
      <div className="card warn" style={{ textAlign: 'start' }}>
        <strong>ماذا يحدث الآن؟</strong>
        <p>{done.status === 'PENDING_REVIEW' ? 'طلبك يحتاج إلى مراجعة إضافية من موظف مختص قبل تطبيقه. سنعلمك عند تحديث الحالة.' : 'طلبك وصل وسيُعالج ضمن مسار الدعم المعتاد.'}</p>
        <p className="hint">التقييم الصوتي: {done.assessment_status ?? '—'}. المؤشر الصوتي مساعد للمراجعة البشرية وليس حكماً نهائياً.</p>
      </div>
      <div className="actions" style={{ justifyContent: 'center' }}>
        <button className="btn" onClick={() => nav('/support')}>متابعة التذكرة</button>
        <Link className="btn secondary" to="/">العودة للرئيسية</Link>
      </div>
    </div>
  )

  return (
    <>
      <div className="crumbs">الرئيسية / تذاكر الدعم</div>
      <h1>طلب دعم حساس</h1>
      <p className="lead">أكّد طلبك صوتياً لحماية التغييرات المهمة على حسابك.</p>
      <div className="grid grid-main">
        <form className="card" onSubmit={submit}>
          <h3>تفاصيل الطلب</h3>
          <div className="field"><label>نوع الطلب</label>
            <select value={type} onChange={e => setType(e.target.value)}>{Object.entries(REQUEST_AR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          </div>
          <div className="field"><label>وصف الطلب</label><textarea rows={4} value={desc} onChange={e => setDesc(e.target.value)} required minLength={5} /></div>
          <h3>التأكيد الصوتي</h3>
          <div className="field">
            <label>رفع ملف WAV / FLAC</label>
            <input type="file" accept=".wav,.flac,audio/wav,audio/flac" onChange={e => setFile(e.target.files?.[0] ?? null)} required />
            <span className="hint">من 3 إلى 60 ثانية · حتى 10 MB. اقرأ: «أنا {acc ? 'صاحب الحساب' : ''}، أؤكد طلب {REQUEST_AR[type]} لدى صدى».</span>
          </div>
          <label style={{ fontSize: 13, display: 'flex', gap: 8, marginBottom: 16 }}>
            <input type="checkbox" checked={agree} onChange={e => setAgree(e.target.checked)} /> أوافق على استخدام التسجيل للتحقق من طلبي والاحتفاظ به وفق سياسة الخصوصية
          </label>
          {err && <p className="error">{err}</p>}
          <button className="btn block" disabled={busy || !agree || !file}>إرسال الطلب بأمان</button>
        </form>
        <aside>
          <div className="card"><h3>صوتك لتأكيد طلبك فقط</h3><p className="hint">نسجّل موافقتك على الطلب الحساس ونستخدم إشارات مساعدة لفحص سلامة التسجيل. عند الحاجة، يراجع موظف مختص طلبك.</p>
            <strong style={{ fontSize: 13 }}>للحصول على تسجيل واضح</strong>
            <ul className="hint"><li>اختر مكاناً هادئاً وتحدث بصوت طبيعي.</li><li>لا تذكر كلمة المرور أو رمز التحقق.</li></ul>
          </div>
          <div className="card warn" style={{ marginTop: 16 }}><strong>التسجيل المباشر من المتصفح</strong><p className="hint">يُضاف في الدفعة القادمة (WebRTC)؛ حالياً ارفع ملفاً صوتياً.</p></div>
        </aside>
      </div>
    </>
  )
}
