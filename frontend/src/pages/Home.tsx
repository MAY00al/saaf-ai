import { useEffect, useState } from 'react';
import { getFarmStats, getImpact } from '../api/client';

export default function Home({ setScreen }: { setScreen: (s: string) => void }) {
  const [stats, setStats] = useState<any>(null);
  const [impact, setImpact] = useState<any>(null);

  useEffect(() => {
    getFarmStats().then(setStats).catch(console.error);
    getImpact().then(setImpact).catch(console.error);
  }, []);

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <h1 style={{ fontWeight: 800, fontSize: 34, lineHeight: 1.4, margin: 0 }}>مرحبًا بك في سعف</h1>
        <div style={{ color: '#55615A' }}>منظومة ذكية لإدارة مخلفات النخيل وتحويلها إلى منتجات ذات قيمة.</div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
        <div style={{ flex: '1 1 200px', background: '#F8F1E2', borderRadius: 20, padding: '18px 20px' }}>
          <div style={{ color: '#0B5D3B', fontSize: 14.5, fontWeight: 700 }}>إجمالي المزارع</div>
          <div style={{ fontFamily: 'Tajawal', fontWeight: 800, fontSize: 32, marginTop: 4 }}>{stats?.farm_count || '...'} مزرعة</div>
          <div style={{ fontSize: 13, color: '#55615A' }}>مسجلة في المنصة (محاكاة)</div>
        </div>
        <div style={{ flex: '1 1 200px', background: '#E6F2EC', borderRadius: 20, padding: '18px 20px' }}>
          <div style={{ color: '#0B5D3B', fontSize: 14.5, fontWeight: 700 }}>إجمالي المخلفات</div>
          <div style={{ fontFamily: 'Tajawal', fontWeight: 800, fontSize: 32, marginTop: 4 }}>{stats?.estimated_annual_waste_kg ? Math.round(stats.estimated_annual_waste_kg / 1000) : '...'} طن</div>
          <div style={{ fontSize: 13, color: '#55615A' }}>متوقعة سنويًا</div>
        </div>
        <div style={{ flex: '1 1 200px', background: '#EAF4EE', borderRadius: 20, padding: '18px 20px' }}>
          <div style={{ color: '#0B5D3B', fontSize: 14.5, fontWeight: 700 }}>الكمية المجمعة</div>
          <div style={{ fontFamily: 'Tajawal', fontWeight: 800, fontSize: 32, marginTop: 4 }}>{impact?.metrics?.confirmed_requested_quantity_kg || 0} كجم</div>
          <div style={{ fontSize: 13, color: '#55615A' }}>من الطلبات المؤكدة</div>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18 }}>
        <div className="card" style={{ flex: '1 1 300px', padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, margin: 0 }}>الرصد الذكي</h2>
          <p style={{ margin: 0, color: '#55615A', fontSize: 14 }}>ارفع صورة جوية لعدّ النخيل بالذكاء الاصطناعي (YOLO)، أو حلل الغطاء النباتي عبر الأقمار الصناعية (NDVI).</p>
          <button className="btn" onClick={() => setScreen('monitor')} style={{ marginTop: 'auto' }}>ابدأ الرصد</button>
        </div>
        <div className="card" style={{ flex: '1 1 300px', padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, margin: 0 }}>جمع المخلفات</h2>
          <p style={{ margin: 0, color: '#55615A', fontSize: 14 }}>احجز موعدًا لاستلام السعف وتحويله إلى فحم حيوي بدلًا من حرقه.</p>
          <button className="btn" onClick={() => setScreen('collect')} style={{ marginTop: 'auto' }}>اطلب جمع</button>
        </div>
      </div>
    </section>
  );
}