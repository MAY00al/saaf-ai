import { useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { detectPalms, getSatellite, saveBoundary, API_BASE } from '../api/client';

export default function Monitor({ setScreen }: { setScreen: (s: string) => void }) {
  const { sessionId, activeFarmId } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'yolo' | 'satellite'>('yolo');
  
  // حالة إدخال الإحداثيات
  const [lat, setLat] = useState('25.4328');
  const [lon, setLon] = useState('49.5786');
  const [savingBoundary, setSavingBoundary] = useState(false);

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !sessionId || !activeFarmId) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const data = await detectPalms(sessionId, activeFarmId, file);
      setResult(data);
    } catch (err: any) {
      setError(err?.error?.message_ar || 'تعذر تحليل الصورة.');
    } finally { setLoading(false); }
  };

  const handleSatellite = async () => {
    if (!activeFarmId) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const data = await getSatellite(activeFarmId, 'ndvi');
      setResult(data);
    } catch (err: any) {
      setError(err?.error?.message_ar || 'تعذر جلب صور الأقمار الصناعية. تأكد من حفظ الإحداثيات أولاً.');
    } finally { setLoading(false); }
  };

  const handleSaveBoundary = async () => {
    if (!activeFarmId) return;
    setSavingBoundary(true); setError(null);
    try {
      await saveBoundary(activeFarmId, Number(lat), Number(lon));
      alert('تم حفظ إحداثيات المزرعة بنجاح! يمكنك الآن استخدام الأقمار الصناعية.');
    } catch (err) {
      setError('فشل حفظ الإحداثيات. تأكد من صحة الأرقام.');
    } finally { setSavingBoundary(false); }
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <h1 style={{ fontWeight: 800, fontSize: 32, color: '#0B5D3B', margin: 0 }}>الرصد</h1>
        <div style={{ color: '#55615A', fontSize: 15, marginTop: 4 }}>اختر طريقة الرصد: طائرة مسيرة (YOLO) أو أقمار صناعية (NDVI).</div>
      </div>

      <div style={{ display: 'flex', gap: 10, borderBottom: '1px solid #E5DCCB', paddingBottom: 10 }}>
        <button className={mode === 'yolo' ? 'btn' : 'btn2'} onClick={() => { setMode('yolo'); setResult(null); }}>صورة جوية (YOLO)</button>
        <button className={mode === 'satellite' ? 'btn' : 'btn2'} onClick={() => { setMode('satellite'); setResult(null); }}>أقمار صناعية (NDVI)</button>
      </div>

      {error && <div style={{ background: '#FDECEC', color: '#8E1C1C', padding: 16, borderRadius: 16 }}>{error}</div>}

      {/* === قسم الأقمار الصناعية === */}
      {mode === 'satellite' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* إدخال الإحداثيات */}
          <div className="card" style={{ padding: 24, border: '2px dashed #0B5D3B', background: '#F7F3EA' }}>
            <h3 style={{ margin: '0 0 10px', color: '#0B5D3B' }}>١. حدد موقع المزرعة (إحداثيات WGS84)</h3>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: 14, fontWeight: 700 }}>خط العرض (Latitude)</label>
                <input className="fld" value={lat} onChange={e => setLat(e.target.value)} />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: 14, fontWeight: 700 }}>خط الطول (Longitude)</label>
                <input className="fld" value={lon} onChange={e => setLon(e.target.value)} />
              </div>
              <button className="btn" onClick={handleSaveBoundary} disabled={savingBoundary}>
                {savingBoundary ? 'جارٍ الحفظ...' : 'حفظ الموقع'}
              </button>
            </div>
          </div>

          {/* زر تحليل NDVI */}
          <div className="card" style={{ padding: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0 }}>٢. تحليل الغطاء النباتي (Sentinel-2)</h3>
              <p style={{ margin: 0, color: '#55615A', fontSize: 14 }}>سيتم جلب صور من آخر 90 يومًا.</p>
            </div>
            <button className="btn" onClick={handleSatellite} disabled={loading}>تحليل NDVI الآن</button>
          </div>
        </div>
      )}

      {/* === قسم YOLO === */}
      {mode === 'yolo' && (
        <div className="card" style={{ padding: 24 }}>
          <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', border: '2px dashed #0B5D3B', borderRadius: 16, padding: 40, cursor: 'pointer', background: '#F7F3EA' }}>
            <span style={{ fontWeight: 700, fontSize: 18, color: '#0B5D3B' }}>اضغط لاختيار صورة جوية</span>
            <input type="file" accept="image/*" onChange={handleImageUpload} style={{ display: 'none' }} disabled={loading} />
          </label>
        </div>
      )}

      {loading && <div className="card" style={{ padding: 24, textAlign: 'center', color: '#0B5D3B' }}>جارٍ تحليل البيانات...</div>}

      {/* النتائج */}
      {result && mode === 'yolo' && (
        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          <div className="card" style={{ flex: '2 1 400px', padding: 16 }}>
            <img src={`${API_BASE}${result.monitoring.observation.annotated_image}`} alt="YOLO Result" style={{ width: '100%', borderRadius: 12 }} />
          </div>
          <div className="card" style={{ flex: '1 1 250px', padding: 20 }}>
            <h3 style={{ color: '#0B5D3B' }}>النتيجة</h3>
            <div style={{ fontSize: 32, fontWeight: 800 }}>{result.monitoring.observation.detected_count} نخلة</div>
            <p style={{ color: '#55615A' }}>المخلفات: {result.monitoring.observation.estimated_annual_waste_kg} كجم/سنة</p>
          </div>
        </div>
      )}

      {result && mode === 'satellite' && (
        <div className="card" style={{ padding: 24 }}>
          <h3>نتيجة NDVI</h3>
          {result.status === 'ok' ? (
            <div>
              <p>متوسط NDVI: {result.vegetation?.ndvi?.mean?.toFixed(3)}</p>
              {result.vegetation?.preview?.data && (
                <img src={`data:image/png;base64,${result.vegetation.preview.data}`} alt="NDVI" style={{ width: '100%', borderRadius: 12 }} />
              )}
            </div>
          ) : (
            <p style={{ color: '#8E1C1C' }}>{result.answer_ar || 'لا توجد صور متاحة.'}</p>
          )}
        </div>
      )}
    </section>
  );
}