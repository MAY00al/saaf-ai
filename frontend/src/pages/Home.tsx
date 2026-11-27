import { useEffect, useState } from 'react';
import { getFarmStats, getImpact } from '../api/client';
import { useAppStore } from '../store/useAppStore';

export default function Home({ setScreen }: { setScreen: (s: string) => void }) {
  const [stats, setStats] = useState<any>(null);
  const [impact, setImpact] = useState<any>(null);
  
  const { profile } = useAppStore();
  const palms = parseInt(profile.palms) || 0;
  const waste = ((palms * 35) / 1000).toFixed(2);

  useEffect(() => {
    getFarmStats().then(setStats).catch(console.error);
    getImpact().then(setImpact).catch(console.error);
  }, []);

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* الترحيب */}
      <div>
        <h1 style={{ fontWeight: 800, fontSize: 34, lineHeight: 1.4, margin: 0 }}>
          مرحبًا يا {profile.owner}
        </h1>
        <div style={{ color: '#55615A' }}>منظومة ذكية لإدارة مخلفات النخيل وتحويلها إلى منتجات ذات قيمة.</div>
      </div>

      {/* شريط الرحلة (الترابط البصري) */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, background: '#FFFDF9', padding: 16, borderRadius: 16, border: '1px solid #E5DCCB', justifyContent: 'center', alignItems: 'center' }}>
        <span style={{ color: '#0B5D3B', fontWeight: 700 }}>١. الرصد</span>
        <span style={{ color: '#C8A25A' }}>←</span>
        <span style={{ color: '#0B5D3B', fontWeight: 700 }}>٢. المرشد</span>
        <span style={{ color: '#C8A25A' }}>←</span>
        <span style={{ color: '#0B5D3B', fontWeight: 700 }}>٣. الجمع</span>
        <span style={{ color: '#C8A25A' }}>←</span>
        <span style={{ color: '#0B5D3B', fontWeight: 700 }}>٤. الأثر</span>
      </div>

      {/* بطاقة المزرعة الشخصية */}
      <div style={{ background: '#0B5D3B', color: '#fff', borderRadius: 20, padding: 24, display: 'flex', flexWrap: 'wrap', gap: 20, alignItems: 'center' }}>
        <div style={{ flex: '1 1 200px' }}>
          <div style={{ fontSize: 15, color: '#E6F2EC' }}>مزرعتك (المحاكاة)</div>
          <div style={{ fontSize: 24, fontWeight: 800, fontFamily: 'Tajawal' }}>{profile.name}</div>
          <div style={{ fontSize: 14, color: '#E6F2EC', marginTop: 4 }}>{profile.region} · {profile.soil} · pH {profile.ph}</div>
        </div>
        <div style={{ flex: '1 1 120px', textAlign: 'center', background: 'rgba(255,255,255,0.1)', padding: 12, borderRadius: 16 }}>
          <div style={{ fontSize: 14, color: '#E6F2EC' }}>عدد النخيل</div>
          <div style={{ fontSize: 28, fontWeight: 800 }}>{palms} نخلة</div>
        </div>
        <div style={{ flex: '1 1 120px', textAlign: 'center', background: 'rgba(255,255,255,0.1)', padding: 12, borderRadius: 16 }}>
          <div style={{ fontSize: 14, color: '#E6F2EC' }}>المخلفات السنوية</div>
          <div style={{ fontSize: 28, fontWeight: 800 }}>{waste} طن</div>
        </div>
      </div>

      <h2 style={{ fontSize: 22, fontWeight: 800, margin: '10px 0 0 0', color: '#0B5D3B' }}>إحصائيات المنصة</h2>
      
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
        <div style={{ flex: '1 1 200px', background: '#F8F1E2', borderRadius: 20, padding: '18px 20px' }}>
          <div style={{ color: '#0B5D3B', fontSize: 14.5, fontWeight: 700 }}>إجمالي المزارع</div>
          <div style={{ fontFamily: 'Tajawal', fontWeight: 800, fontSize: 32, marginTop: 4 }}>{stats?.farm_count || '...'} مزرعة</div>
        </div>
        <div style={{ flex: '1 1 200px', background: '#E6F2EC', borderRadius: 20, padding: '18px 20px' }}>
          <div style={{ color: '#0B5D3B', fontSize: 14.5, fontWeight: 700 }}>إجمالي المخلفات</div>
          <div style={{ fontFamily: 'Tajawal', fontWeight: 800, fontSize: 32, marginTop: 4 }}>{stats?.estimated_annual_waste_kg ? Math.round(stats.estimated_annual_waste_kg / 1000) : '...'} طن</div>
        </div>
        <div style={{ flex: '1 1 200px', background: '#EAF4EE', borderRadius: 20, padding: '18px 20px' }}>
          <div style={{ color: '#0B5D3B', fontSize: 14.5, fontWeight: 700 }}>الكمية المجمعة</div>
          <div style={{ fontFamily: 'Tajawal', fontWeight: 800, fontSize: 32, marginTop: 4 }}>{impact?.metrics?.confirmed_requested_quantity_kg || 0} كجم</div>
        </div>
      </div>

      {/* أزرار الانتقال السريع للوكلاء */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18, marginTop: 10 }}>
        <div className="card" style={{ flex: '1 1 300px', padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, margin: 0 }}>١. الرصد الذكي</h2>
          <p style={{ margin: 0, color: '#55615A', fontSize: 14 }}>ارفع صورة جوية لعدّ النخيل، أو افحص صحة مزرعتك بالأقمار الصناعية (NDVI).</p>
          <button className="btn" onClick={() => setScreen('monitor')} style={{ marginTop: 'auto' }}>ابدأ الرصد</button>
        </div>
        <div className="card" style={{ flex: '1 1 300px', padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, margin: 0 }}>٢. المرشد الذكي</h2>
          <p style={{ margin: 0, color: '#55615A', fontSize: 14 }}>اسأل عن جرعة الفحم الحيوي، وأثرها على الماء والتربة، بالدليل العلمي.</p>
          <button className="btn" onClick={() => setScreen('advisor')} style={{ marginTop: 'auto' }}>افتح المرشد</button>
        </div>
        <div className="card" style={{ flex: '1 1 300px', padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, margin: 0 }}>٣. جمع المخلفات</h2>
          <p style={{ margin: 0, color: '#55615A', fontSize: 14 }}>احجز موعدًا لاستلام السعف وتحويله إلى فحم حيوي بدلًا من حرقه.</p>
          <button className="btn" onClick={() => setScreen('collect')} style={{ marginTop: 'auto' }}>اطلب جمع</button>
        </div>
      </div>
    </section>
  );
}