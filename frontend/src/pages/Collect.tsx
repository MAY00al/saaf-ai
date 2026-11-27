import { useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { proposeCollection, confirmCollection } from '../api/client';

export default function Collect({ setScreen }: { setScreen: (s: string) => void }) {
  const { sessionId, activeFarmId, profile } = useAppStore();
  
  // حساب المخلفات المتوقعة بناءً على ملف المزرعة (35 كجم لكل نخلة)
  const palms = parseInt(profile.palms) || 0;
  const expectedWaste = palms * 35;

  const [step, setStep] = useState(1);
  const [qty, setQty] = useState(expectedWaste > 0 ? Math.min(expectedWaste, 300) : 300); 
  const [draft, setDraft] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<any>(null);

  // خطوات وهمية للتصوير والشركة (لتطابق التصميم)
  const [photo, setPhoto] = useState(false);
  const [company, setCompany] = useState(0);

  const companies = [
    { name: 'شركة شريكة ١', slot: 'أقرب موعد: الخميس' },
    { name: 'شركة شريكة ٢', slot: 'أقرب موعد: السبت' },
    { name: 'شركة شريكة ٣', slot: 'أقرب موعد: الأحد' }
  ];

  const handlePropose = async () => {
    if (!sessionId || !activeFarmId) return;
    
    // تحقق ذكي: هل الكمية تتجاوز مخلفات المزرعة؟
    if (qty > expectedWaste && expectedWaste > 0) {
      setError(`تنبيه: الكمية المطلوبة (${qty} كجم) تتجاوز التقدير السنوي لمزرعتك (${expectedWaste.toLocaleString()} كجم). خفّض الكمية للمتابعة.`);
      return;
    }

    // الخادم يقبل أعداداً صحيحة موجبة فقط (كجم)
    if (!Number.isInteger(qty) || qty <= 0) {
      setError('أدخل كمية صحيحة بالكيلوجرام (رقم صحيح أكبر من صفر).');
      return;
    }

    setLoading(true); setError(null);
    try {
      const res = await proposeCollection(sessionId, activeFarmId, qty);
      if (res.status === 'awaiting_confirmation') {
        setDraft(res.collection.draft);
        setStep(3);
      } else {
        setError(res.answer_ar || 'لم يتم استلام مسودة. قد تكون الكمية غير صالحة.');
      }
    } catch (err: any) { setError(err?.error?.message_ar || 'فشل الاتصال بالخادم.'); }
    finally { setLoading(false); }
  };

  const handleConfirm = async () => {
    if (!sessionId || !draft) return;
    setLoading(true); setError(null);
    try {
      const res = await confirmCollection(sessionId, draft);
      if (res.status === 'ok' && res.collection?.request) {
        setSaved(res.collection.request);
        setStep(4);
      } else {
        setError(res.answer_ar || 'لم يتم تأكيد الطلب. حاول مرة أخرى.');
      }
    } catch (err: any) {
      // مثال: انتهت الجلسة أو سبق تأكيد المسودة (409/404)
      setError(err?.error?.message_ar || 'فشل تأكيد الطلب.');
    } finally { setLoading(false); }
  };

  const stepper = () => (
    <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
      {['تأكيد الكمية', 'اختيار الشركة', 'الموعد والتأكيد'].map((l, i) => {
        const n = i + 1;
        const on = step === n;
        return (
          <div key={i} style={{ flex: 1, padding: 10, borderRadius: 16, background: on ? '#E6F2EC' : '#FFFDF9', border: `1px solid ${on ? '#0B5D3B' : '#E5DCCB'}`, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ width: 30, height: 30, borderRadius: '50%', background: on ? '#0B5D3B' : '#E5DCCB', color: on ? '#fff' : '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>{n}</span>
            <span style={{ fontWeight: on ? 700 : 400 }}>{l}</span>
          </div>
        );
      })}
    </div>
  );

  return (
    <section style={{ maxWidth: 900, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontWeight: 800, fontSize: 32, color: '#0B5D3B', margin: 0 }}>جمع السعف</h1>
        <div style={{ color: '#55615A', fontSize: 15 }}>نربطك بشركات التحويل إلى فحم حيوي.</div>
      </div>

      {error && <div style={{ background: '#FDECEC', color: '#8E1C1C', padding: 16, borderRadius: 16 }}>{error}</div>}
      {step < 4 && stepper()}

      {/* الخطوة 1 */}
      {step === 1 && (
        <div className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h3 style={{ margin: 0 }}>١. حدد الكمية التي تريد جمعها</h3>
          
          <div style={{ background: '#F8F1E2', border: '1px solid #C8A25A', padding: 12, borderRadius: 12, fontSize: 14 }}>
            بناءً على عدد نخيلك (<b>{palms}</b> نخلة)، نقدر أن مزرعتك تنتج <b>{expectedWaste.toLocaleString()}</b> كجم من السعف سنوياً.
          </div>

          <label style={{ border: '2px dashed #0B5D3B', borderRadius: 16, padding: 30, textAlign: 'center', cursor: 'pointer', background: '#F7F3EA' }}>
            <span style={{ fontWeight: 700, color: '#0B5D3B' }}>{photo ? '✓ تم إرفاق صورة السعف (محاكاة)' : 'اضغط لرفع صورة السعف (اختياري)'}</span>
            <input type="file" onChange={() => setPhoto(true)} style={{ display: 'none' }} />
          </label>

          <div>
            <label style={{ display: 'block', fontWeight: 700, marginBottom: 8 }}>الكمية المطلوب جمعها (كجم)</label>
            <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} className="fld" />
          </div>
          
          <button className="btn" onClick={() => setStep(2)} style={{ marginTop: 10 }}>التالي: اختيار الشركة ←</button>
        </div>
      )}

      {/* الخطوة 2 */}
      {step === 2 && (
        <div className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h3 style={{ margin: 0 }}>٢. اختر شركة الجمع</h3>
          <p style={{ margin: 0, color: '#55615A', fontSize: 14 }}>الشركات المتاحة في منطقة {profile.region} (عرض تجريبي، لا يوجد ربط فعلي بجهة جمع):</p>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {companies.map((c, i) => (
              <button key={i} onClick={() => setCompany(i)} className={company === i ? 'btn' : 'btn2'} style={{ flex: 1, padding: 16 }}>
                {c.name}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
            <button className="btn2" onClick={() => setStep(1)}>→ رجوع</button>
            <button className="btn" onClick={handlePropose} disabled={loading}>{loading ? 'جارٍ حساب الموعد...' : 'التالي: عرض الموعد ←'}</button>
          </div>
        </div>
      )}

      {/* الخطوة 3 */}
      {step === 3 && draft && (
        <div className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h3 style={{ margin: 0 }}>٣. تأكيد الطلب</h3>
          <div style={{ background: '#F8F1E2', padding: 16, borderRadius: 12, border: '1px solid #C8A25A' }}>
            <p><b>الشركة:</b> {companies[company].name}</p>
            <p><b>الكمية:</b> {draft.requested_quantity_kg} كجم</p>
            <p><b>تاريخ الاستلام المقترح:</b> {draft.pickup_date}</p>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn2" onClick={() => setStep(2)}>→ رجوع</button>
            <button className="btn" onClick={handleConfirm} disabled={loading}>{loading ? 'جارٍ التأكيد...' : 'أرسل طلب الجمع'}</button>
          </div>
        </div>
      )}

      {/* الخطوة 4: النجاح والربط بالأثر */}
      {step === 4 && saved && (
        <div className="card" style={{ padding: 40, textAlign: 'center', background: '#E6F2EC' }}>
          <div style={{ fontSize: 50, marginBottom: 10 }}>🎉</div>
          <h2 style={{ color: '#0B5D3B', fontSize: 28 }}>تم إرسال طلبك بنجاح!</h2>
          
          <div style={{ background: '#FFFDF9', padding: 20, borderRadius: 16, display: 'inline-block', margin: '20px 0', border: '1px solid #E5DCCB' }}>
            <p style={{ margin: 0 }}>رقم الطلب: <b style={{ color: '#0B5D3B' }}>{saved.request_id}</b></p>
            <p style={{ margin: '8px 0 0 0' }}>الحالة: <b>{saved.status === 'confirmed' ? 'مؤكد' : saved.status === 'cancelled' ? 'ملغى' : saved.status}</b></p>
          </div>

          <div style={{ background: '#0B5D3B', color: '#fff', padding: 16, borderRadius: 12, marginBottom: 20 }}>
            <p style={{ margin: 0, fontSize: 18 }}>
              🌱 تم تسجيل طلب جمع <b>{draft?.requested_quantity_kg}</b> كجم من السعف لتحويلها إلى فحم حيوي بدل التخلص منها.
            </p>
            <p style={{ margin: '8px 0 0 0', fontSize: 13, opacity: 0.85 }}>
              طلب محاكاة: لا يمثل استلاماً ميدانياً ولا يثبت كمية مجنّبة من الحرق.
            </p>
          </div>

          <button className="btn" onClick={() => setScreen('impact')} style={{ fontSize: 18, padding: '0 40px' }}>
            شاهد تقرير الأثر البيئي
          </button>
        </div>
      )}
    </section>
  );
}
