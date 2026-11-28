import { useEffect, useState } from 'react';
import { ScanEye, MessageCircle, Truck, ChartColumn, TreePalm, Leaf, Package, Sprout, ArrowLeft, MapPin } from 'lucide-react';
import { getFarmStats, getImpact } from '../api/client';
import { useAppStore } from '../store/useAppStore';
import PalmFrond from '../components/PalmFrond';

const STEPS = [
  { key: 'monitor', n: '١', title: 'افحص', desc: 'عدّ النخيل بصورة جوية أو افحص صحة المزرعة بالقمر الصناعي.', icon: ScanEye },
  { key: 'advisor', n: '٢', title: 'اسأل', desc: 'مرشد يجيبك بالدليل العلمي ويوضح حدود المعلومة.', icon: MessageCircle },
  { key: 'collect', n: '٣', title: 'اجمع', desc: 'اطلب استلام السعف ليتحول إلى فحم حيوي بدل الحرق.', icon: Truck },
  { key: 'impact', n: '٤', title: 'أثرك', desc: 'تابع طلباتك وملخص الأثر لمزرعتك.', icon: ChartColumn },
];

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
    <section style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* بطاقة المزرعة */}
      <div className="hero">
        <PalmFrond className="frond-bg" size={210} color="currentColor" />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#E6F2EC', fontSize: 14 }}>
          <MapPin size={16} /> {profile.region} · {profile.soil} · pH {profile.ph}
        </div>
        <h1 style={{ margin: '6px 0 2px', fontWeight: 800, fontSize: 30, lineHeight: 1.35 }}>{profile.name}</h1>
        <div style={{ color: '#E6F2EC', fontSize: 14.5 }}>مزرعة محاكاة · بيانات تجريبية</div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 18 }}>
          <div className="hero-stat">
            <TreePalm size={26} color="#C8A25A" />
            <div><div className="l">عدد النخيل</div><div className="v">{palms.toLocaleString('en-US')}</div></div>
          </div>
          <div className="hero-stat">
            <Leaf size={26} color="#C8A25A" />
            <div><div className="l">المخلفات السنوية</div><div className="v">{waste} طن</div></div>
          </div>
        </div>

        <button className="btn btn-gold" onClick={() => setScreen('monitor')} style={{ marginTop: 20, width: '100%', maxWidth: 360 }}>
          ابدأ فحص مزرعتك <ArrowLeft size={20} />
        </button>
      </div>

      {/* الرحلة */}
      <div>
        <h2 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 12px', color: 'var(--green)' }}>رحلتك في أربع خطوات</h2>
        <div className="journey">
          {STEPS.map(({ key, n, title, desc, icon: Icon }) => (
            <button key={key} className="step" onClick={() => setScreen(key)}>
              <span className="n">{n}</span>
              <span className="badge"><Icon size={24} strokeWidth={1.9} /></span>
              <b>{title}</b>
              <span className="d">{desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* إحصائيات المنصة */}
      <div>
        <h2 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 12px', color: 'var(--green)' }}>المنصة بالأرقام</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <div className="stat" style={{ flex: '1 1 210px', background: 'var(--gold-lt)' }}>
            <span className="badge gold"><TreePalm size={24} /></span>
            <div><div className="lbl">المزارع المسجلة</div><div className="num">{stats?.farm_count ?? '...'}</div></div>
          </div>
          <div className="stat" style={{ flex: '1 1 210px', background: 'var(--green-lt)' }}>
            <span className="badge"><Sprout size={24} /></span>
            <div><div className="lbl">المخلفات السنوية المقدّرة</div><div className="num">{stats?.total_est_residue_kg_per_year ? Math.round(stats.total_est_residue_kg_per_year / 1000).toLocaleString('en-US') : '...'} <small style={{ fontSize: 15 }}>طن</small></div></div>
          </div>
          <div className="stat" style={{ flex: '1 1 210px', background: '#EAF4EE' }}>
            <span className="badge"><Package size={24} /></span>
            <div><div className="lbl">الكمية المطلوب جمعها</div><div className="num">{(impact?.metrics?.confirmed_requested_quantity_kg || 0).toLocaleString('en-US')} <small style={{ fontSize: 15 }}>كجم</small></div></div>
          </div>
        </div>
      </div>
    </section>
  );
}
