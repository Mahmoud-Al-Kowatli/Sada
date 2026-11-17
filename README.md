# صدى (Sada) — منصة مصرفية رقمية مزوّدة بكشف التزييف الصوتي

نموذج أولي لمشروع فصلي: مصرف رقمي (حسابات، دفتر أستاذ بقيد مزدوج، تحويلات، محرك مخاطر، تذاكر دعم حساسة، مراجعة بشرية، تدقيق) مع خدمة ذكاء اصطناعي منفصلة لتقييم التسجيلات الصوتية.

```
sada/
├── backend/      Sada Platform API  — FastAPI + SQLAlchemy + PostgreSQL   (منفذ 8000)
├── ai-service/   Sada AI            — FastAPI + numpy/soundfile (+ PyTorch اختياري) (منفذ 8100)
├── frontend/     تطبيق الويب        — React + TypeScript + Vite, RTL, خط Cairo  (منفذ 5173)
└── docker-compose.yml
```

## التشغيل السريع (Docker)

```bash
docker compose up --build
```
ثم افتح http://localhost:5173 . قاعدة البيانات تُهيأ تلقائياً (Alembic) وتُزرع ببيانات تجريبية.

## التشغيل اليدوي (Windows / بدون Docker)

PostgreSQL و Redis يجب أن يكونا شغّالين، أو استخدم SQLite للتجربة السريعة كما في الأمثلة أدناه.

```powershell
# 1) خدمة الذكاء الاصطناعي
cd ai-service
python -m venv .venv; .\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8100

# 2) الـ backend (نافذة ثانية)
cd backend
python -m venv .venv; .\.venv\Scripts\activate
pip install -r requirements.txt
$env:SADA_DATABASE_URL = "sqlite:///./var/dev.db"      # أو رابط PostgreSQL من .env.example
python -m scripts.seed                                  # يطبع حسابات الدخول التجريبية
uvicorn app.main:app --port 8000 --reload

# 3) الواجهة (نافذة ثالثة)
cd frontend
npm install
npm run dev
```

مع PostgreSQL استبدل `python -m scripts.seed` بـ `alembic upgrade head` ثم `python -m scripts.seed`.

## حسابات الدخول التجريبية

| الدور | البريد | كلمة المرور |
|---|---|---|
| عميل (أحمد المنصوري) | ahmad.mansouri@example.com | Customer#2026 |
| عميل (نورة العتيبي، مستفيد) | noura.otaibi@example.com | Customer#2026 |
| موظف مراجعة (مريم القحطاني) | maryam.review@sada.example | Reviewer#2026 |
| مدير نظام (عبدالله الشهري) | abdullah.admin@sada.example | Admin#2026 |

رمز OTP يُعرض في الواجهة في بيئة التطوير (`SADA_OTP_DEV_ECHO=true`).

## سيناريو العرض

1. دخول كعميل → الرئيسية (الرصيد المتاح 24,850، المجمّد 5,000، الحد اليومي 20,000).
2. تحويل 1,250 إلى حساب `100058329017` → OTP → **200 مكتمل** (قيد مزدوج مرحّل).
3. تحويل 5,000 → **202 معلّق**: المبلغ يُجمَّد، تُفتح حالة `REV-…`، لا قيود محاسبية بعد.
4. طلب دعم حساس «رفع حد التحويل» مع ملف WAV → خدمة Sada AI تعيد درجة اشتباه + جودة + إصدار النموذج؛ محرك المخاطر يقرر `SUBMITTED` أو `PENDING_REVIEW`. إذا كانت الخدمة متوقفة، يُسجَّل `UNAVAILABLE` ويستمر الطلب.
5. دخول كموظف مراجعة → قائمة المراجعة → استلام الحالة → الاستماع للتسجيل → قبول (ينفّذ التحويل من المجمّد) أو رفض (يعيد المبلغ). كل خطوة في سجل التدقيق.

## الاختبارات

```bash
cd backend && python -m pytest -q      # 15 اختباراً: UC-01, UC-02, UC-04، توازن القيد المزدوج، OTP، الصلاحيات
cd ai-service && python -m pytest -q   # 5 اختبارات: الجودة، إعادة أخذ العينات، تنظيف الملف المؤقت
```

## واجهة الـ API (مختصر)

| الطريقة | المسار | الوصف |
|---|---|---|
| POST | /api/v1/auth/register, /login, GET /me | المصادقة (JWT) |
| GET | /api/v1/accounts, /accounts/{id}/transfers, /accounts/lookup/{no} | الحسابات |
| POST | /api/v1/transfers/precheck → /transfers | UC-01: فحص + OTP ثم تنفيذ (200) أو تعليق (202) |
| POST/GET | /api/v1/tickets | UC-02: طلب حساس بملف صوتي |
| GET/POST | /api/v1/cases, /{id}/claim, /{id}, /{id}/audio, /{id}/decision | UC-04 (موظفون) |
| GET/PUT | /api/v1/admin/settings, /users, /audit, /ledger, /ledger/{id}/reverse | الإدارة |
| POST | AI: /v1/assessments | UC-03: تقييم تسجيل |

التوثيق التفاعلي: http://localhost:8000/docs و http://localhost:8100/docs

## قرارات تصميم تستحق الذكر في المناقشة

- **الدفتر هو الحقيقة**: الأرصدة تُحدَّث فقط داخل `services/ledger.py` بقيود متوازنة وقفل صفوف بترتيب ثابت؛ التصحيح بقيد عكسي (`reversal_of_id`) لا بالتعديل.
- **الرصيد المجمّد** منفصل عن المتاح: التعليق لا يرحّل قيوداً؛ القبول يرحّلها من المجمّد، والرفض يعيده.
- **الذكاء الاصطناعي ميزة لا أساس**: `ai_client.py` يحوّل أي فشل إلى `UNAVAILABLE` وتبقى قواعد المخاطر فعّالة.
- **لا درجة لصوت رديء**: خدمة AI تعيد `INSUFFICIENT_QUALITY` بدل رقم مضلل، وتحذف الملف المؤقت في كل مسار.
- **المصنّف قابل للاستبدال**: `SADA_AI_CLASSIFIER=stub` الآن؛ `lfcc_resnet18` يحمّل checkpoint من دفتر التدريب بنفس تعريف الشبكة (`models/lfcc_resnet18.py`) ونفس خصائص LFCC (`audio/features.py`).
- **الملفات الصوتية خارج قاعدة البيانات**: نسخة مشفّرة (Fernet) في `var/evidence`، تُبث عبر الـ API بعد التحقق من الصلاحية وتُحذف عند صدور القرار.

## ما لم يُنفَّذ بعد (الدفعة القادمة)

- التسجيل المباشر من المتصفح ومكالمة WebRTC حية (حالياً رفع ملف).
- شاشات الإدارة الكاملة (الإعدادات، المستخدمون، دفتر العمليات والعكس، تقييم النماذج) — الـ API جاهزة.
- تدريب النموذج الأساسي B0 ودفتر التجارب (Kaggle) وتصدير checkpoint.
- Webhooks موقّعة بـ HMAC، وطابور Redis لعمال التحليل.
