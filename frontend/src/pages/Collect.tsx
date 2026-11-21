import { useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { proposeCollection, confirmCollection } from '../api/client';

export default function Collect({ setScreen }: { setScreen: (s: string) => void }) {
  const { sessionId, activeFarmId } = useAppStore();
  const [step, setStep] = useState(1);
  const [qty, setQty] = useState(300); // كجم
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
    setLoading(true); setError(null);
    try {
      const res = await proposeCollection(sessionId, activeFarmId, qty);
      if (res.status === 'awaiting_confirmation') {
        setDraft(res.collection.draft);
        setStep(3);
      } else {
        setError('لم يتم استلام مسودة. قد تكون الكمية غير صالحة.');
      }
    } catch (err) { setError('فشل الاتصال بالخادم.'); }
    finally { setLoading(false); }
  };

  const handleConfirm = async () => {
    if (!sessionId || !draft) return;
    setLoading(true); setError(null);
    try {
      const res = await confirmCollection(sessionId, draft);
      if (res.status === 'ok') {
        setSaved(res.collection.request);
        setStep(4);
      }
    } catch (err) { setError('فشل تأكيد الطلب.'); }
    finally { setLoading(false); }
  };

  const stepper = () => (
    <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
      {['تصوير السعف', 'اختيار الشركة', 'الموعد والتأكيد'].map((l, i) => {
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
          <h3 style={{ margin: 0 }}>١. صوّر السعف المجمّع (اختياري)</h3>
          <label style={{ border: '2px dashed #0B5D3B', borderRadius: 16, padding: 30, textAlign: 'center', cursor: 'pointer', background: '#F7F3EA' }}>
            <span style={{ fontWeight: 700, color: '#0B5D3B' }}>اضغط لرفع صورة (محاكاة)</span>
            <input type="file" onChange={() => setPhoto(true)} style={{ display: 'none' }} />
          </label>
          {photo && <div style={{ color: '#0B5D3B' }}>تم التقاط الصورة (محاكاة)!</div>}
          <div style={{ marginTop: 20 }}>
            <label style={{ display: 'block', fontWeight: 700, marginBottom: 8 }}>أدخل الكمية (كجم)</label>
            <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} className="fld" />
          </div>
          <button className="btn" onClick={() => setStep(2)} disabled={!photo}>التالي: اختيار الشركة ←</button>
        </div>
      )}

      {/* الخطوة 2 */}
      {step === 2 && (
        <div className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h3 style={{ margin: 0 }}>٢. اختر شركة الجمع</h3>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {companies.map((c, i) => (
              <button key={i} onClick={() => setCompany(i)} className={company === i ? 'btn' : 'btn2'} style={{ flex: 1, padding: 16 }}>
                {c.name}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn2" onClick={() => setStep(1)}>→ رجوع</button>
            <button className="btn" onClick={handlePropose} disabled={loading}>{loading ? 'جارٍ الحساب...' : 'التالي: الموعد ←'}</button>
          </div>
        </div>
      )}

      {/* الخطوة 3 */}
      {step === 3 && draft && (
        <div className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h3 style={{ margin: 0 }}>٣. تأكيد الطلب</h3>
          <div style={{ background: '#F8F1E2', padding: 16, borderRadius: 12 }}>
            <p>الشركة: {companies[company].name}</p>
            <p>الكمية: {draft.requested_quantity_kg} كجم</p>
            <p>تاريخ الاستلام: {draft.pickup_date}</p>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn2" onClick={() => setStep(2)}>→ رجوع</button>
            <button className="btn" onClick={handleConfirm} disabled={loading}>أرسل طلب الجمع</button>
          </div>
        </div>
      )}

      {/* الخطوة 4 */}
      {step === 4 && saved && (
        <div className="card" style={{ padding: 40, textAlign: 'center', background: '#E6F2EC' }}>
          <h2 style={{ color: '#0B5D3B', fontSize: 28 }}>تم إرسال طلبك بنجاح!</h2>
          <p>رقم الطلب: <b>{saved.request_id}</b></p>
          <p>الحالة: {saved.status}</p>
          <button className="btn" onClick={() => setScreen('impact')} style={{ marginTop: 20 }}>شاهد تقرير الأثر</button>
        </div>
      )}
    </section>
  );
}