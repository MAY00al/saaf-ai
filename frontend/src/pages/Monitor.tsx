import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { useAppStore } from '../store/useAppStore';
import { detectPalms, getSatellite, saveBoundary, API_BASE } from '../api/client';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

function LocationPicker({ setPos }: { setPos: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) { setPos(e.latlng.lat, e.latlng.lng); },
  });
  return null;
}

export default function Monitor({ setScreen }: { setScreen: (s: string) => void }) {
  const { sessionId, activeFarmId, profile, setPrefillQuestion, notify } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'yolo' | 'satellite'>('satellite');
  
  // استخدام إحداثيات الملف الشخصي تلقائياً
  const [pos, setPos] = useState<[number, number]>([
    Number(profile.lat) || 25.4328,
    Number(profile.lon) || 49.5786
  ]);
  const [showMap, setShowMap] = useState(false);
  const [savingBoundary, setSavingBoundary] = useState(false);

  const handleSaveLocation = async () => {
    if (!activeFarmId) return;
    setSavingBoundary(true); setError(null);
    try {
      await saveBoundary(activeFarmId, pos[0], pos[1]);
      setShowMap(false); // إخفاء الخريطة بعد الحفظ
      notify('تم حفظ موقع المزرعة بنجاح', 'success');
    } catch (err: any) {
      setError(err?.error?.message_ar || 'فشل حفظ الموقع. تأكد من الاتصال بالخادم.');
    } finally { setSavingBoundary(false); }
  };

  // تحليل صورة جوية (مرفوعة أو تجريبية) بوكيل الرصد
  const analyzeImage = (file: File) => {
    if (!sessionId || !activeFarmId) return;
    setLoading(true); setError(null); setResult(null);
    detectPalms(sessionId, activeFarmId, file)
      .then(setResult)
      .catch((err) => setError(err?.error?.message_ar || 'تعذر تحليل الصورة.'))
      .finally(() => setLoading(false));
  };

  // صورة تجريبية اختيارية: ضع الملف في frontend/public/sample-aerial.jpg (أو .png) فيظهر الزر تلقائياً
  const [sample, setSample] = useState<{ url: string; type: string } | null>(null);
  useEffect(() => {
    let alive = true;
    (async () => {
      for (const ext of ['jpg', 'png']) {
        try {
          const res = await fetch(`/sample-aerial.${ext}`);
          const type = res.headers.get('content-type') || '';
          if (res.ok && type.startsWith('image/')) {
            if (alive) setSample({ url: `/sample-aerial.${ext}`, type });
            return;
          }
        } catch { /* لا توجد صورة تجريبية */ }
      }
    })();
    return () => { alive = false; };
  }, []);

  const useSampleImage = async () => {
    if (!sample) return;
    const blob = await (await fetch(sample.url)).blob();
    analyzeImage(new File([blob], 'sample', { type: sample.type }));
  };

  const handleSatellite = async () => {
    if (!activeFarmId) return;
    setLoading(true); setError(null); setResult(null);
    try {
      let data = await getSatellite(activeFarmId, 'ndvi');
      // الفحص يحتاج حدوداً مسجلة؛ إن لم تُسجَّل بعد نسجلها تلقائياً من موقع المزرعة ثم نعيد الفحص
      if (data?.status === 'boundary_required') {
        await saveBoundary(activeFarmId, pos[0], pos[1]);
        data = await getSatellite(activeFarmId, 'ndvi');
      }
      setResult(data);
    } catch (err: any) {
      setError(err?.error?.message_ar || 'خدمة الأقمار الصناعية غير متاحة حالياً.');
    } finally { setLoading(false); }
  };

  // الرد يحتوي قائمة مشاهد (scenes)؛ نعرض أحدث مشهد صالح
  const latestScene = result?.scenes?.length
    ? [...result.scenes].sort((a: any, b: any) => String(b.acquired_at).localeCompare(String(a.acquired_at)))[0]
    : null;

  const askAdvisorAboutNDVI = () => {
    const ndvi = latestScene?.ndvi?.mean?.toFixed(2);
    setPrefillQuestion(`أظهر تحليل الأقمار الصناعية أن مؤشر صحة النبات (NDVI) في مزرعتي هو ${ndvi}. ماذا تنصحني أن أفعل لتحسين صحة النخيل؟`);
    setScreen('advisor');
  };

  // تحويل NDVI إلى حالة مفهومة للمزارع
  const getHealthStatus = (ndvi: number) => {
    if (ndvi >= 0.4) return { label: 'ممتازة (نباتات صحية)', color: '#0B5D3B', bg: '#E6F2EC', icon: '🟢' };
    if (ndvi >= 0.2) return { label: 'تحتاج متابعة (إجهاد خفيف)', color: '#856404', bg: '#FFF3CD', icon: '🟡' };
    return { label: 'تحتاج تدخل (جفاف شديد)', color: '#8E1C1C', bg: '#FDECEC', icon: '🔴' };
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <h1 style={{ fontWeight: 800, fontSize: 32, color: '#0B5D3B', margin: 0 }}>الرصد والتحليل</h1>
        <div style={{ color: '#55615A', fontSize: 15, marginTop: 4 }}>افحص صحة مزرعتك من الفضاء، أو اعدّ نخيلك بصورة جوية.</div>
      </div>

      <div style={{ display: 'flex', gap: 10, borderBottom: '1px solid #E5DCCB', paddingBottom: 10 }}>
        <button className={mode === 'satellite' ? 'btn' : 'btn2'} onClick={() => { setMode('satellite'); setResult(null); }}>📍 فحص صحة المزرعة</button>
        <button className={mode === 'yolo' ? 'btn' : 'btn2'} onClick={() => { setMode('yolo'); setResult(null); }}>📸 عدّ النخيل (YOLO)</button>
      </div>

      {error && <div style={{ background: '#FDECEC', color: '#8E1C1C', padding: 16, borderRadius: 16 }}>{error}</div>}

      {/* === قسم الأقمار الصناعية === */}
      {mode === 'satellite' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          
          {/* بطاقة الموقع المبسطة */}
          <div className="card" style={{ padding: 24, background: '#F7F3EA' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ margin: 0, color: '#0B5D3B' }}>📍 موقع المزرعة</h3>
                <p style={{ margin: '4px 0 0', fontSize: 14, color: '#55615A' }}>
                  تم تحديد الموقع بناءً على بيانات ملفك الشخصي ({Number(profile.lat).toFixed(4)}, {Number(profile.lon).toFixed(4)}).
                </p>
              </div>
              <button className="btn2" onClick={() => setShowMap(!showMap)}>
                {showMap ? 'إخفاء الخريطة' : 'تعديل الموقع'}
              </button>
            </div>
            
            {showMap && (
              <div style={{ marginTop: 16 }}>
                <div style={{ height: 300, width: '100%', borderRadius: 16, overflow: 'hidden', zIndex: 0 }}>
                  <MapContainer center={pos} zoom={13} style={{ height: '100%', width: '100%' }}>
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    <LocationPicker setPos={(lat, lon) => setPos([lat, lon])} />
                    <Marker position={pos} />
                  </MapContainer>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
                  <button className="btn" onClick={handleSaveLocation} disabled={savingBoundary}>
                    {savingBoundary ? 'جارٍ الحفظ...' : 'حفظ الموقع الجديد'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* زر الفحص */}
          <div className="card" style={{ padding: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0 }}>هل نخيلك بصحة جيدة؟</h3>
              <p style={{ margin: 0, color: '#55615A', fontSize: 14 }}>سنستخدم صور الأقمار الصناعية لفحص صحة النباتات.</p>
            </div>
            <button className="btn" onClick={handleSatellite} disabled={loading}>
              {loading ? 'جارٍ الفحص...' : 'افحص صحة مزرعتي الآن'}
            </button>
          </div>
        </div>
      )}

      {/* === قسم YOLO === */}
      {mode === 'yolo' && (
        <div className="card" style={{ padding: 24 }}>
          <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', border: '2px dashed #0B5D3B', borderRadius: 16, padding: 40, cursor: 'pointer', background: '#F7F3EA' }}>
            <span style={{ fontWeight: 700, fontSize: 18, color: '#0B5D3B' }}>اضغط لاختيار صورة جوية (JPEG أو PNG)</span>
            <input type="file" accept="image/jpeg,image/png" onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) analyzeImage(file);
            }} style={{ display: 'none' }} disabled={loading} />
          </label>
          {sample && (
            <button className="btn2" onClick={useSampleImage} disabled={loading} style={{ marginTop: 12, width: '100%' }}>
              🖼️ جرّب بصورة جوية تجريبية
            </button>
          )}
        </div>
      )}

      {loading && <div className="card" style={{ padding: 24, textAlign: 'center', color: '#0B5D3B' }}>جارٍ تحليل البيانات...</div>}

      {/* === النتائج المبسطة === */}
      {result && mode === 'yolo' && (
        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          <div className="card" style={{ flex: '2 1 400px', padding: 16 }}>
            <img src={`${API_BASE}${result.monitoring.observation.annotated_image}`} alt="YOLO Result" style={{ width: '100%', borderRadius: 12 }} />
          </div>
          <div className="card" style={{ flex: '1 1 250px', padding: 20 }}>
            <h3 style={{ color: '#0B5D3B' }}>النتيجة</h3>
            <div style={{ fontSize: 32, fontWeight: 800 }}>{result.monitoring.observation.detected_count} نخلة</div>
            <p style={{ color: '#55615A' }}>المخلفات المتوقعة: {result.monitoring.observation.estimated_annual_waste_kg} كجم/سنة</p>
          </div>
        </div>
      )}

      {result && mode === 'satellite' && (
        <div className="card" style={{ padding: 24 }}>
          <h3>نتيجة فحص المزرعة</h3>
          {result.status === 'ok' && latestScene?.ndvi ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ background: getHealthStatus(latestScene.ndvi.mean).bg, padding: 20, borderRadius: 16, textAlign: 'center' }}>
                <div style={{ fontSize: 40 }}>{getHealthStatus(latestScene.ndvi.mean).icon}</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: getHealthStatus(latestScene.ndvi.mean).color, marginTop: 8 }}>
                  {getHealthStatus(latestScene.ndvi.mean).label}
                </div>
                <div style={{ fontSize: 14, color: '#55615A', marginTop: 4 }}>
                  مؤشر صحة النبات (NDVI): {latestScene.ndvi.mean.toFixed(2)} · صورة Sentinel‑2 بتاريخ {String(latestScene.acquired_at).slice(0, 10)}
                </div>
              </div>

              {result.preview?.data && (
                <img
                  src={`data:${result.preview.media_type};base64,${result.preview.data}`}
                  alt="خريطة NDVI للمزرعة"
                  style={{ width: '100%', maxHeight: 320, objectFit: 'contain', borderRadius: 12, background: '#F7F3EA' }}
                />
              )}

              <div style={{ fontSize: 13, color: '#55615A' }}>{result.warning_ar}</div>
              
              <button className="btn" onClick={askAdvisorAboutNDVI} style={{ background: '#C8A25A', color: '#1E2A25', fontSize: 18 }}>
                💬 اسأل المرشد: ماذا أفعل الآن؟
              </button>
            </div>
          ) : (
            <p style={{ color: '#8E1C1C' }}>{result.answer_ar || 'لا توجد صور متاحة (قد تكون المنطقة صحراوية).'}</p>
          )}
        </div>
      )}
      
      <button className="btn2" onClick={() => setScreen('home')}>العودة للرئيسية</button>
    </section>
  );
}
