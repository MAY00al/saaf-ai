import { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { updateFarm } from '../api/client';
export default function Profile({ setScreen }: { setScreen: (s: string) => void }) {
  const { profile, setProfile, activeFarmId } = useAppStore();
  const [form, setForm] = useState(profile);

  // تحديث النموذج إذا تغيرت البيانات في المتجر
  useEffect(() => {
    setForm(profile);
  }, [profile]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

   const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();

    // تحقق قبل الإرسال: الخادم يرفض المساحة ≤ 0 والأرقام غير الصالحة
    const soil_ph = Number(form.ph), area_ha = Number(form.area), lat = Number(form.lat), lon = Number(form.lon);
    const valid = [soil_ph, area_ha, lat, lon].every(Number.isFinite)
      && area_ha > 0 && soil_ph >= 0 && soil_ph <= 14 && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
    if (!valid) {
      alert('تحقق من القيم: المساحة أكبر من صفر، وpH بين 0 و14، وخط العرض والطول رقمان صحيحان.');
      return;
    }

    setProfile(form);

    try {
      await updateFarm(activeFarmId || 'SIM-001', {
        soil_ph,
        irrigation_system: form.irr,
        area_ha,
        lat,
        lon,
      });
      alert('تم حفظ بيانات المزرعة بنجاح!');
      setScreen('monitor');
    } catch {
      alert('تم الحفظ محلياً، لكن تعذر المزامنة مع الخادم.');
      setScreen('monitor');
    }
  };
  const seg = (key: 'soil' | 'irr', val: string) => (
    <button type="button" onClick={() => setForm({ ...form, [key]: val })} style={{
      flex: 1, padding: 12, borderRadius: 14, border: '1px solid', 
      background: form[key] === val ? '#0B5D3B' : '#FFFDF9',
      color: form[key] === val ? '#fff' : '#1E2A25',
      borderColor: form[key] === val ? '#0B5D3B' : '#E5DCCB',
      fontWeight: 700, cursor: 'pointer'
    }}>{val}</button>
  );

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontWeight: 800, fontSize: 32, color: '#0B5D3B', margin: 0 }}>ملفي</h1>
        <div style={{ color: '#55615A', fontSize: 15 }}>معلوماتك ومعلومات مزرعتك. بعد الحفظ يحلل وكيل الأقمار الصناعية مزرعتك تلقائيًا.</div>
      </div>

      <form onSubmit={handleSave} className="card" style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 820 }}>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1 }}><label style={{ fontWeight: 700 }}>اسمي</label><input name="owner" className="fld" value={form.owner} onChange={handleChange} /></div>
          <div style={{ flex: 1 }}><label style={{ fontWeight: 700 }}>رقم الجوال</label><input name="phone" className="fld" placeholder="05XXXXXXXX" onChange={handleChange} /></div>
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1 }}><label style={{ fontWeight: 700 }}>اسم المزرعة</label><input name="name" className="fld" value={form.name} onChange={handleChange} /></div>
          <div style={{ flex: 1 }}><label style={{ fontWeight: 700 }}>المنطقة</label><input name="region" className="fld" value={form.region} onChange={handleChange} /></div>
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1 }}><label style={{ fontWeight: 700 }}>خط العرض</label><input name="lat" className="fld" value={form.lat} onChange={handleChange} /></div>
          <div style={{ flex: 1 }}><label style={{ fontWeight: 700 }}>خط الطول</label><input name="lon" className="fld" value={form.lon} onChange={handleChange} /></div>
          <div style={{ flex: 1 }}><label style={{ fontWeight: 700 }}>المساحة (هكتار)</label><input name="area" className="fld" value={form.area} onChange={handleChange} /></div>
        </div>
        
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', fontWeight: 700, marginBottom: 6 }}>نوع التربة</label>
            <div style={{ display: 'flex', gap: 8 }}>{seg('soil', 'رملية')}{seg('soil', 'كلسية قلوية')}</div>
          </div>
          <div style={{ flex: 1 }}><label style={{ fontWeight: 700 }}>pH</label><input name="ph" className="fld" value={form.ph} onChange={handleChange} /></div>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', fontWeight: 700, marginBottom: 6 }}>نظام الري</label>
            <div style={{ display: 'flex', gap: 8 }}>{seg('irr', 'تنقيط')}{seg('irr', 'غمر')}</div>
          </div>
        </div>
        
        <button type="submit" className="btn" style={{ marginTop: 10 }}>احفظ وحلّل مزرعتي بالأقمار الصناعية</button>
      </form>
    </section>
  );
}
