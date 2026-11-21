import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, api, fmtDate, fmtMoney } from '../api/client'
import { useAuth } from '../auth'
import { Chip } from '../components/Layout'
import { REQUEST_AR } from './Home'
import { RULE_AR } from './Transfers'

interface CaseRow {
  case_id: string; reference: string; status: string; subject_type: 'TRANSFER' | 'TICKET'; subject_reference: string
  customer_name: string; triggered_rules: string[]; spoof_score: string | null; assessment_status: string | null
  assigned_reviewer_id: string | null; created_at: string
}
interface CaseDetail extends CaseRow {
  customer_email: string; account_number: string; available_balance: string; frozen_balance: string
  transfer: { reference: string; amount: string; status: string; destination_name: string | null; destination_account_number: string } | null
  ticket: { reference: string; request_type: string; description: string; status: string } | null
  assessment: { status: string; spoof_score: string | null; threshold: string | null; quality_status: string; model_version: string; processing_time_ms: number } | null
  audio_available: boolean; decision: string | null; decision_rationale: string | null
  timeline: { at: string; event: string; actor: string; details: string }[]
}

export function ReviewQueue() {
  const [rows, setRows] = useState<CaseRow[]>([])
  const [stats, setStats] = useState<Record<string, number>>({})
  useEffect(() => {
    api<CaseRow[]>('/cases').then(({ data }) => setRows(data))
    api<Record<string, number>>('/admin/stats').then(({ data }) => setStats(data))
  }, [])
  return (
    <>
      <div className="crumbs">مساحة العمليات / قائمة المراجعة</div>
      <h1>المراجعة تبدأ بسياق واضح</h1>
      <p className="lead">رتّب الأولويات، راجع الأدلة، ثم وثّق قرارك.</p>
      <div className="grid grid-4">
        <div className="card"><div className="kpi-label">حالات مفتوحة</div><div className="kpi num" style={{ color: 'var(--amber)' }}>{stats.open_cases ?? '–'}</div></div>
        <div className="card"><div className="kpi-label">قيد المراجعة</div><div className="kpi num" style={{ color: 'var(--royal)' }}>{stats.in_review ?? '–'}</div></div>
        <div className="card"><div className="kpi-label">مقبولة اليوم</div><div className="kpi num" style={{ color: 'var(--emerald)' }}>{stats.accepted_today ?? '–'}</div></div>
        <div className="card"><div className="kpi-label">مرفوضة اليوم</div><div className="kpi num" style={{ color: 'var(--crimson)' }}>{stats.rejected_today ?? '–'}</div></div>
      </div>
      <div className="card" style={{ marginTop: 24 }}>
        <table>
          <thead><tr><th>الحالة / الكيان</th><th>العميل</th><th>قواعد المخاطر</th><th>مؤشر الصوت</th><th>حالة المراجعة</th><th>الإجراء</th></tr></thead>
          <tbody>
            {rows.map(c => (
              <tr key={c.case_id}>
                <td><span className="mono">{c.reference}</span><div className="hint">{c.subject_type === 'TRANSFER' ? 'تحويل' : 'دعم'} · <span className="mono">{c.subject_reference}</span></div></td>
                <td>{c.customer_name}</td>
                <td className="hint">{c.triggered_rules.map(r => RULE_AR[r] ?? r).join(' · ') || '—'}</td>
                <td>{c.spoof_score ? <span className={`chip ${Number(c.spoof_score) >= 0.65 ? 'REJECTED' : 'COMPLETED'}`}>{Number(c.spoof_score).toFixed(2)}</span> : <span className="chip UNAVAILABLE">{c.assessment_status ?? 'غير منطبق'}</span>}</td>
                <td><Chip s={c.status} /></td>
                <td><Link className="btn secondary" to={`/review/${c.case_id}`}>{c.status === 'OPEN' ? 'استلام ومراجعة' : 'عرض الحالة'}</Link></td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={6} className="hint">لا توجد حالات.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="card soft" style={{ marginTop: 16 }}><strong>المؤشر الصوتي ليس حكماً على العميل</strong><p className="hint">تعذر التقييم لا يعني الاحتيال. تبقى قواعد المخاطر المصرفية فعالة، ويصدر القرار من الموظف بعد فحص الأدلة.</p></div>
    </>
  )
}

export function CaseReview() {
  const { id } = useParams()
  const { user } = useAuth()
  const nav = useNavigate()
  const [c, setC] = useState<CaseDetail | null>(null)
  const [rationale, setRationale] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [audio, setAudio] = useState<string | null>(null)

  const load = () => api<CaseDetail>(`/cases/${id}`).then(({ data }) => setC(data))
  useEffect(() => { load() }, [id])

  const claim = async () => { setBusy(true); try { await api(`/cases/${id}/claim`, { method: 'POST' }); await load() } catch (ex) { setErr(ex instanceof ApiError ? ex.message : 'خطأ') } finally { setBusy(false) } }
  const decide = async (decision: 'ACCEPTED' | 'REJECTED') => {
    setErr(''); setBusy(true)
    try { await api(`/cases/${id}/decision`, { method: 'POST', body: JSON.stringify({ decision, rationale }) }); nav('/review') }
    catch (ex) { setErr(ex instanceof ApiError ? ex.message : 'خطأ') } finally { setBusy(false) }
  }
  const play = async () => {
    const res = await fetch(`/api/v1/cases/${id}/audio`, { headers: { Authorization: `Bearer ${localStorage.getItem('sada.token')}` } })
    setAudio(URL.createObjectURL(await res.blob()))
  }

  if (!c) return <p>جارٍ التحميل…</p>
  const mine = c.assigned_reviewer_id === user?.user_id
  const score = c.assessment?.spoof_score ? Number(c.assessment.spoof_score) : null
  const closed = c.status === 'ACCEPTED' || c.status === 'REJECTED'

  return (
    <>
      <div className="crumbs">قائمة المراجعة / <span className="mono">{c.reference}</span></div>
      <h1>{c.subject_type === 'TRANSFER' ? 'مراجعة تحويل داخلي' : `مراجعة ${c.ticket ? REQUEST_AR[c.ticket.request_type] : 'طلب'}`} <Chip s={c.status} /></h1>
      <p className="lead">{c.assigned_reviewer_id ? (mine ? 'مسندة إليك' : 'مسندة إلى مراجع آخر') : 'غير مسندة بعد'} · فُتحت {fmtDate(c.created_at)}</p>
      <div className="grid grid-main">
        <div>
          <div className="card">
            <h3>{c.customer_name}</h3>
            <div className="hint">{c.customer_email} · حساب <span className="mono">{c.account_number}</span></div>
            <div className="grid grid-2" style={{ marginTop: 12 }}>
              <div><div className="kpi-label">الرصيد المتاح</div><div className="num" style={{ fontWeight: 800 }}>{fmtMoney(c.available_balance)}</div></div>
              <div><div className="kpi-label">الرصيد المجمّد</div><div className="num" style={{ fontWeight: 800, color: 'var(--amber)' }}>{fmtMoney(c.frozen_balance)}</div></div>
            </div>
          </div>
          {c.transfer && <div className="card" style={{ marginTop: 16 }}><h3>التحويل المرتبط · <span className="mono">{c.transfer.reference}</span></h3><p>المستفيد: {c.transfer.destination_name} <span className="mono hint">{c.transfer.destination_account_number}</span> · المبلغ: <strong className="num">{fmtMoney(c.transfer.amount)}</strong> · الحالة: <Chip s={c.transfer.status} /></p></div>}
          {c.ticket && <div className="card" style={{ marginTop: 16 }}><h3>تذكرة الدعم · <span className="mono">{c.ticket.reference}</span></h3><p>الطلب: {REQUEST_AR[c.ticket.request_type]}</p><p className="hint">{c.ticket.description}</p></div>}
          <div className="card" style={{ marginTop: 16 }}>
            <h3>محرك المخاطر وتقييم صدى AI</h3>
            <p className="hint">القواعد المفعّلة: {c.triggered_rules.map(r => RULE_AR[r] ?? r).join(' · ') || '—'}</p>
            <div className="card soft" style={{ padding: 10, fontSize: 13 }}>مؤشر مساعد للمراجعة البشرية وليس قراراً نهائياً</div>
            {score !== null ? (
              <>
                <div className="kpi num" style={{ color: score >= 0.65 ? 'var(--crimson)' : 'var(--emerald)' }}>{score.toFixed(2)} <span style={{ fontSize: 13, color: 'var(--muted)' }}>درجة الاشتباه الصوتي</span></div>
                <div className="score"><i style={{ left: `${score * 100}%` }} /><i style={{ left: `${Number(c.assessment?.threshold ?? 0.65) * 100}%`, background: 'var(--muted)' }} /></div>
                <div className="hint">العتبة {c.assessment?.threshold} · الجودة {c.assessment?.quality_status} · {c.assessment?.model_version} · {c.assessment?.processing_time_ms} ms</div>
              </>
            ) : <div className="card" style={{ background: '#f8fafc' }}><strong>التقييم الصوتي غير متاح · {c.assessment?.status ?? 'غير منطبق'}</strong><p className="hint">القواعد المصرفية فعّالة. لا تُحتسب درجة افتراضية ولا يصدر رفض تلقائي.</p></div>}
          </div>
          {c.ticket && <div className="card" style={{ marginTop: 16 }}><h3>التسجيل المحتفظ به</h3>{c.audio_available ? (audio ? <audio controls src={audio} style={{ width: '100%' }} /> : <button className="btn secondary" onClick={play}>استماع (يُسجَّل في سجل التدقيق)</button>) : <p className="hint">التسجيل غير متاح أو حُذف وفق سياسة الاحتفاظ.</p>}</div>}
        </div>
        <aside>
          <div className="card">
            <h3>القرار البشري</h3>
            {closed ? <p>القرار: <Chip s={c.status} /><br /><span className="hint">{c.decision_rationale}</span></p> : !mine ? (
              <button className="btn block" disabled={busy || c.status === 'IN_REVIEW'} onClick={claim}>{c.status === 'IN_REVIEW' ? 'مستلمة من مراجع آخر' : 'استلام الحالة'}</button>
            ) : (
              <>
                <div className="field"><label>سبب القرار *</label><textarea rows={4} value={rationale} onChange={e => setRationale(e.target.value)} placeholder="اكتب الأدلة التي استندت إليها، وسبب قبول أو رفض الطلب…" /></div>
                {err && <p className="error">{err}</p>}
                <div className="actions">
                  <button className="btn accept" style={{ flex: 1 }} disabled={busy || rationale.trim().length < 5} onClick={() => decide('ACCEPTED')}>قبول</button>
                  <button className="btn reject" style={{ flex: 1 }} disabled={busy || rationale.trim().length < 5} onClick={() => decide('REJECTED')}>رفض</button>
                </div>
                <p className="hint">القبول ينفّذ التحويل المعلّق من المبلغ المجمّد؛ الرفض يعيد المبلغ إلى الرصيد المتاح. كلاهما في معاملة ذرية واحدة.</p>
              </>
            )}
          </div>
          <div className="card" style={{ marginTop: 16 }}>
            <h3>سجل الحالة غير القابل للتعديل</h3>
            {c.timeline.map((e, i) => <div key={i} style={{ borderInlineStart: '2px solid var(--line)', paddingInlineStart: 12, marginBottom: 10 }}><div className="hint">{fmtDate(e.at)}</div><strong className="mono" style={{ fontSize: 12 }}>{e.event}</strong><div className="hint">{e.actor}</div></div>)}
          </div>
        </aside>
      </div>
    </>
  )
}
