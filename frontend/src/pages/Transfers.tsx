import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api, fmtDate, fmtMoney, type Account, type Precheck, type Transfer } from '../api/client'
import { Chip } from '../components/Layout'

// ------------------------------------------------------------ list page ---
export function TransfersList() {
  const [rows, setRows] = useState<Transfer[]>([])
  useEffect(() => {
    api<Account[]>('/accounts').then(async ({ data }) => data[0] && setRows((await api<Transfer[]>(`/accounts/${data[0].account_id}/transfers`)).data))
  }, [])
  return (
    <>
      <div className="crumbs">الرئيسية / التحويلات</div>
      <h1>التحويلات</h1>
      <p className="lead">كل تحويل يُتابع برقم مرجعي واضح.</p>
      <Link to="/transfers/new" className="btn">← تحويل داخلي جديد</Link>
      <div className="card" style={{ marginTop: 24 }}>
        <table>
          <thead><tr><th>المرجع</th><th>المستفيد</th><th>المبلغ</th><th>الحالة</th><th>التاريخ</th><th>ملاحظة</th></tr></thead>
          <tbody>
            {rows.map(t => <tr key={t.transfer_id}><td className="mono">{t.reference}</td><td>{t.destination_name}<br /><span className="hint mono">{t.destination_account_number}</span></td><td className="num">{fmtMoney(t.amount)}</td><td><Chip s={t.status} />{t.case_reference && <div className="hint mono">{t.case_reference}</div>}</td><td>{fmtDate(t.created_at)}</td><td>{t.note}</td></tr>)}
            {!rows.length && <tr><td colSpan={6} className="hint">لا توجد تحويلات بعد.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ------------------------------------------------------- new transfer (UC-01) ---
type Step = 'details' | 'otp' | 'done'

export function NewTransfer() {
  const [acc, setAcc] = useState<Account | null>(null)
  const [dest, setDest] = useState('100058329017')
  const [destName, setDestName] = useState('')
  const [amount, setAmount] = useState('1250.00')
  const [note, setNote] = useState('')
  const [step, setStep] = useState<Step>('details')
  const [pre, setPre] = useState<Precheck | null>(null)
  const [code, setCode] = useState(['', '', '', '', '', ''])
  const [result, setResult] = useState<{ status: number; t: Transfer } | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const inputs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => { api<Account[]>('/accounts').then(({ data }) => setAcc(data[0])) }, [])

  // beneficiary name confirmation while typing (UI: "تم التحقق من الحساب")
  useEffect(() => {
    if (dest.length < 6) { setDestName(''); return }
    const h = setTimeout(() => api<{ display_name: string }>(`/accounts/lookup/${dest}`).then(({ data }) => setDestName(data.display_name)).catch(() => setDestName('')), 300)
    return () => clearTimeout(h)
  }, [dest])

  const precheck = async (e: FormEvent) => {
    e.preventDefault(); if (!acc) return
    setErr(''); setBusy(true)
    try {
      const { data } = await api<Precheck>('/transfers/precheck', { method: 'POST', body: JSON.stringify({ source_account_id: acc.account_id, destination_account_number: dest, amount, note: note || null }) })
      setPre(data); setStep('otp'); setCode(['', '', '', '', '', ''])
      setTimeout(() => inputs.current[0]?.focus(), 50)
    } catch (ex) { setErr(ex instanceof ApiError ? ex.message : 'تعذر الاتصال بالخادم') } finally { setBusy(false) }
  }

  const execute = async () => {
    if (!acc || !pre) return
    setErr(''); setBusy(true)
    try {
      const r = await api<Transfer>('/transfers', { method: 'POST', body: JSON.stringify({ source_account_id: acc.account_id, destination_account_number: dest, amount, note: note || null, otp_id: pre.otp_id, otp_code: code.join('') }) })
      setResult({ status: r.status, t: r.data }); setStep('done')
    } catch (ex) {
      if (ex instanceof ApiError && ex.code === 'INVALID_OTP') setErr(ex.message)
      else { setErr(ex instanceof ApiError ? ex.message : 'تعذر الاتصال بالخادم'); setStep('details') }
    } finally { setBusy(false) }
  }

  const onCode = (i: number, v: string) => {
    const d = v.replace(/\D/g, '').slice(-1)
    const next = [...code]; next[i] = d; setCode(next)
    if (d && i < 5) inputs.current[i + 1]?.focus()
  }

  if (step === 'done' && result) return <Result status={result.status} t={result.t} />

  return (
    <>
      <div className="crumbs">الرئيسية / التحويلات / تحويل داخلي</div>
      <h1>تحويل داخلي جديد</h1>
      <p className="lead">حوّل بين حسابات صدى دون رسوم، مع تأكيد إضافي لحمايتك.</p>
      <div className="grid grid-main">
        <div className="card">
          <div className="steps">
            <span className={step === 'details' ? 'on' : ''}>01 بيانات التحويل</span>
            <div className="bar"><i style={{ width: step === 'details' ? '50%' : '100%' }} /></div>
            <span className={step === 'otp' ? 'on' : ''}>02 التحقق والتأكيد</span>
          </div>

          {step === 'details' && (
            <form onSubmit={precheck}>
              <div className="field">
                <label>رقم حساب المستفيد</label>
                <input className="mono" value={dest} onChange={e => setDest(e.target.value.replace(/\s/g, ''))} required minLength={6} />
                <span className="hint" style={{ color: destName ? 'var(--emerald)' : undefined }}>{destName ? `${destName} · تم التحقق من الحساب` : 'أدخل رقم الحساب للتحقق من اسم المستفيد'}</span>
              </div>
              <div className="field">
                <label>المبلغ (ريال سعودي)</label>
                <input className="mono" type="number" step="0.01" min="1" value={amount} onChange={e => setAmount(e.target.value)} required />
                {acc && <span className="hint">المتاح: {fmtMoney(acc.available_balance)} · المتبقي من الحد: {fmtMoney(Number(acc.daily_limit) - Number(acc.daily_used))}</span>}
              </div>
              <div className="field"><label>ملاحظة للمستفيد (اختياري)</label><input value={note} onChange={e => setNote(e.target.value)} maxLength={140} placeholder="دفعة شخصية" /></div>
              {err && <p className="error">{err}</p>}
              <button className="btn block" disabled={busy || !destName}>متابعة للتحقق</button>
              <p className="hint" style={{ textAlign: 'center', marginTop: 8 }}>لن يُخصم أي مبلغ قبل إتمام التحقق.</p>
            </form>
          )}

          {step === 'otp' && pre && (
            <div>
              <h3>أدخل رمز التحقق</h3>
              <p className="hint">أرسلنا رمزاً من 6 أرقام إلى رقم هاتفك المسجّل. صالح لمدة 5 دقائق.</p>
              {pre.dev_otp_code && <div className="card warn" style={{ padding: 12, marginBottom: 16 }}>بيئة تطوير: الرمز هو <strong className="mono">{pre.dev_otp_code}</strong> (لا يُعرض في الإنتاج)</div>}
              <div className="otp">{code.map((c, i) => <input key={i} ref={el => { inputs.current[i] = el }} inputMode="numeric" value={c} onChange={e => onCode(i, e.target.value)} onKeyDown={e => { if (e.key === 'Backspace' && !c && i > 0) inputs.current[i - 1]?.focus() }} />)}</div>
              {err && <p className="error" style={{ textAlign: 'center' }}>{err}</p>}
              <div className="actions">
                <button className="btn" style={{ flex: 1 }} disabled={busy || code.join('').length < 6} onClick={execute}>تأكيد التحويل {fmtMoney(amount)}</button>
                <button className="btn secondary" onClick={() => setStep('details')}>رجوع</button>
              </div>
            </div>
          )}
        </div>

        <aside>
          {acc && (
            <div className="card">
              <h3>ملخص حسابك</h3>
              <table><tbody>
                <tr><td>الرصيد المتاح</td><td className="num">{fmtMoney(acc.available_balance)}</td></tr>
                <tr><td>الرصيد المجمّد</td><td className="num">{fmtMoney(acc.frozen_balance)}</td></tr>
                <tr><td>الرسوم</td><td className="num">0.00 ر.س</td></tr>
              </tbody></table>
              <p className="hint">الأموال المجمّدة لا تُخصم نهائياً؛ تُحجز مؤقتاً حتى يصدر قرار المراجعة البشرية.</p>
            </div>
          )}
          <div className="card soft" style={{ marginTop: 16 }}>
            <h3>قبل أن تتابع</h3>
            <p className="hint">تحقق من اسم المستفيد ورقم الحساب. لن يطلب منك موظف صدى مشاركة كلمة المرور أو رمز التحقق في مكالمة.</p>
          </div>
        </aside>
      </div>
    </>
  )
}

function Result({ status, t }: { status: number; t: Transfer }) {
  const held = status === 202
  return (
    <div className="card result" style={{ maxWidth: 640, margin: '40px auto' }}>
      <Chip s={t.status} />
      <h1 style={{ marginTop: 12 }}>{held ? 'تحويلك قيد المراجعة' : 'تم التحويل بنجاح'}</h1>
      <div className="hint">رقم المرجع</div>
      <div className="ref mono">{t.reference}</div>
      <p><strong className="num">{fmtMoney(t.amount)}</strong> إلى {t.destination_name} <span className="mono hint">{t.destination_account_number}</span></p>
      {held ? (
        <div className="card warn" style={{ textAlign: 'start' }}>
          <strong>ماذا يحدث الآن؟</strong>
          <p>حُجز المبلغ من رصيدك المتاح ولم يُخصم. سيراجع موظف مختص العملية ويصدر قراره، وستصلك النتيجة في تذاكر الدعم.</p>
          <p className="hint">المؤشرات: {t.triggered_rules.map(r => RULE_AR[r] ?? r).join('، ')} · الحالة <span className="mono">{t.case_reference}</span></p>
        </div>
      ) : <p className="hint">اكتمل القيد المحاسبي وتحدّث رصيدك فوراً. {t.completed_at && fmtDate(t.completed_at)}</p>}
      <div className="actions" style={{ justifyContent: 'center' }}>
        <Link className="btn" to="/transfers">عرض التحويلات</Link>
        <Link className="btn secondary" to="/">العودة للرئيسية</Link>
      </div>
    </div>
  )
}

export const RULE_AR: Record<string, string> = {
  LARGE_AMOUNT: 'مبلغ مرتفع', NEW_DESTINATION: 'مستفيد جديد', REPEATED_ATTEMPTS: 'محاولات متكررة',
  AUDIO_HIGH_SUSPICION: 'اشتباه صوتي مرتفع', AUDIO_SUSPICION: 'اشتباه صوتي', AUDIO_UNAVAILABLE: 'التقييم الصوتي غير متاح',
  AUDIO_INSUFFICIENT_QUALITY: 'جودة تسجيل غير كافية', AUDIO_INVALID_AUDIO: 'ملف صوتي غير صالح',
  SENSITIVE_REQUEST_TYPE: 'طلب حساس', OPEN_CASE_EXISTS: 'حالة مفتوحة سابقة',
}
