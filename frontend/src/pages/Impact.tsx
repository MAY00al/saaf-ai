import { useEffect, useState } from 'react';
import { getImpact } from '../api/client';

export default function Impact() {
  const [data, setData] = useState<any>(null);

  useEffect(() => { getImpact().then(setData).catch(console.error); }, []);

  if (!data) return <div>جارٍ تحميل التقرير...</div>;

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontWeight: 800, fontSize: 32, color: '#0B5D3B', margin: 0 }}>تقرير الأثر</h1>
        <div style={{ color: '#55615A', fontSize: 15 }}>ملخص إنجازات المنصة على مستوى المزارع.</div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
        <div style={{ flex: '1 1 200px', background: '#0B5D3B', color: '#fff', padding: 20, borderRadius: 20 }}>
          <div style={{ fontSize: 14 }}>الكمية المجمعة</div>
          <div style={{ fontSize: 32, fontWeight: 800 }}>{data.metrics?.confirmed_requested_quantity_kg || 0} كجم</div>
        </div>
        <div style={{ flex: '1 1 200px', background: '#FFFDF9', border: '1px solid #E5DCCB', padding: 20, borderRadius: 20 }}>
          <div style={{ fontSize: 14, color: '#55615A' }}>إجمالي المزارع</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: '#0B5D3B' }}>{data.metrics?.farm_count || '—'}</div>
        </div>
        <div style={{ flex: '1 1 200px', background: '#F8F1E2', border: '1px solid #C8A25A', padding: 20, borderRadius: 20 }}>
          <div style={{ fontSize: 14, color: '#55615A' }}>الكربون المحبوس</div>
          <div style={{ fontSize: 32, fontWeight: 800 }}>— طن CO₂</div>
          <div style={{ fontSize: 12, color: '#8E1C1C' }}>* يظهر عند توفر معامل تحويل معتمد.</div>
        </div>
      </div>

      <div className="card" style={{ padding: 24 }}>
        <h2 style={{ marginTop: 0 }}>ملاحظات النظام</h2>
        <p style={{ color: '#55615A', fontSize: 14 }}>هذا التقرير يستند إلى بيانات محاكاة لطلبات الجمع، ولا يمثل استلامًا ميدانيًا.</p>
        <p style={{ color: '#55615A', fontSize: 14 }}>الأثر على الماء مستند إلى تجارب مخبرية (Alkhasha 2018): انخفاض التبخر بنسبة 29.27% في التربة الرملية.</p>
      </div>
    </section>
  );
}