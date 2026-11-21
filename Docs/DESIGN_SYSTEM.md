# UI design system (from the Figma kit "SadaUI_UX", 23 screens)

## Foundations
- Font **Cairo** (Google Fonts), Arabic-first RTL; numerals and ids LTR (`.num`, `.mono`).
- Colours: Navy `#1F4E79` (brand, primary text on hero) · Royal blue `#2B6CB0` (primary buttons) · Emerald `#10B981` (accept / completed) · Amber `#F59E0B` (held / pending) · Crimson `#EF4444` (reject / alert) · Slate `#64748B` (muted).
- Spacing 8 px grid; 12-column layout at 1440; cards radius 12 px, 1 px `#E2E8F0` border, soft shadow.
- Buttons: primary (royal), secondary (white/navy border), accept (teal-green), reject (red), disabled (slate).
- Status chips show **code + Arabic label + colour** (never colour alone): COMPLETED·مكتمل, HELD·معلّق, PENDING_REVIEW·قيد المراجعة, SUBMITTED·مُرسل, REJECTED·مرفوض, UNAVAILABLE·غير متاح.
- Audio quality states: SUFFICIENT (green), INSUFFICIENT_QUALITY (amber), INVALID_AUDIO (red), UNAVAILABLE (grey).
- Tone of copy: calm, specific, no alarm. The AI indicator is always labelled "مؤشر مساعد للمراجعة البشرية وليس قراراً نهائياً".

## Screens → routes → status
| # | Screen | Route | Status |
|---|---|---|---|
| 01 | تسجيل الدخول | /login | done |
| 02 | إنشاء حساب | /register | done |
| 03 | الرئيسية | / | done |
| 04 | تحويل داخلي (step 1) | /transfers/new | done |
| 05 | التحقق برمز OTP (step 2) | /transfers/new | done |
| 06 | تحويل مكتمل | /transfers/new (result) | done |
| 07 | تحويل قيد المراجعة | /transfers/new (result) | done |
| 08 | أخطاء التحويل | inline errors | done (422 codes mapped) |
| 09 | تأكيد صوتي مباشر (recording) | /support/new | **todo** (MediaRecorder) |
| 10 | رفع ملف صوتي | /support/new | done |
| 11 | تأكيد طلب الدعم | /support/new (result) | done |
| 12 | قائمة المراجعة | /review | done |
| 13 | فحص الحالة واتخاذ القرار | /review/:id | done |
| 14 | تعذر التقييم الصوتي | /review/:id (UNAVAILABLE state) | done |
| 15 | إدارة النظام | /admin | **todo** |
| 16 | تقييم النماذج | /admin/models | **todo** |
| 17 | دفتر العمليات والعكس | /admin/ledger | **todo** |
| 18–20 | جوال (home, transfer, support) | responsive | partial |
| 21 | نظام الواجهة والحالات | styles/global.css | done |
| 22 | الملف الشخصي | /profile | **todo** |
| 23 | تذاكر الدعم | /support | done |

The PNG mock-ups are in the user's `prototype` folder (SadaUI_UX.zip). Match them closely; when in doubt, copy their wording.
