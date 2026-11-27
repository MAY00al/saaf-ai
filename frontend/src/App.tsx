import { useState, useEffect } from 'react';
import { createSession, getFarms } from './api/client'; // تأكد من وجود getFarms هنا
import { useAppStore } from './store/useAppStore';
import Sidebar from './components/Sidebar';
import Home from './pages/Home';
import Profile from './pages/Profile';
import Monitor from './pages/Monitor';
import Advisor from './pages/Advisor';
import Collect from './pages/Collect';
import Impact from './pages/Impact';

export default function App() {
  const [screen, setScreen] = useState('home');
  const { setSession, setProfile, activeFarmId } = useAppStore();

  useEffect(() => {
    // 1. إنشاء الجلسة
    createSession()
      .then((data) => setSession(data.session_id))
      .catch((err) => console.error("فشل الاتصال بالخادم:", err));

    // 2. جلب مزرعة افتراضية وتجهيز بيانات واضحة أنها "تجريبية"
    getFarms()
      .then((farms) => {
        // نجلب المزرعة النشطة (وإلا أول مزرعة) حتى يتطابق الملف الشخصي مع معرّف المزرعة المستخدم في الطلبات
        const defaultFarm = farms.find((f) => f.farm_id === activeFarmId) ?? farms[0];
        if (defaultFarm) {
          setProfile({
            owner: 'مستخدم تجريبي (Demo)',
            name: 'مزرعة نموذجية للمحاكاة',
            region: defaultFarm.region, // مثل: الأحساء
            lat: String(defaultFarm.lat),
            lon: String(defaultFarm.lon),
            area: String(defaultFarm.area_ha),
            soil: defaultFarm.soil_sand_pct && defaultFarm.soil_sand_pct > 50 ? 'رملية' : 'كلسية قلوية',
            ph: String(defaultFarm.soil_ph || '7.4'),
            irr: defaultFarm.irrigation_system || 'تنقيط',
            palms: String(defaultFarm.palm_count),
          });
        }
      })
      .catch((err) => console.error("فشل جلب المزرعة:", err));
  }, [setSession, setProfile, activeFarmId]);

  const renderScreen = () => {
    switch (screen) {
      case 'home': return <Home setScreen={setScreen} />;
      case 'profile': return <Profile setScreen={setScreen} />;
      case 'monitor': return <Monitor setScreen={setScreen} />;
      case 'advisor': return <Advisor setScreen={setScreen} />;
      case 'collect': return <Collect setScreen={setScreen} />;
      case 'impact': return <Impact />;
      default: return <Home setScreen={setScreen} />;
    }
  };

  return (
    <div dir="rtl" className="shell">
      <Sidebar screen={screen} setScreen={setScreen} />
      <div className="main">
        <svg width="100%" height="10" aria-hidden="true" style={{ display: 'block' }}>
          <defs>
            <pattern id="sadu" width="36" height="10" patternUnits="userSpaceOnUse">
              <polygon points="0,10 9,0 18,10" fill="#0B5D3B" />
              <polygon points="18,0 27,10 36,0" fill="#C8A25A" />
            </pattern>
          </defs>
          <rect width="100%" height="10" fill="url(#sadu)" />
        </svg>
        <main className="content">{renderScreen()}</main>
        
        {/* شريط سفلي يوضح أن البيانات محاكاة */}
        <div style={{ maxWidth: 1080, margin: '0 auto', padding: '0 32px 28px', fontSize: 13.5, color: '#55615A', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>فريق جُمّار · هاكاثون agentX. جميع بيانات المزرعة المعروضة هي <b>بيانات محاكاة تجريبية</b>.</span>
          <span style={{ fontSize: 12 }}>الأبحاث المذكورة مصادر حقيقية.</span>
        </div>
      </div>
    </div>
  );
}
