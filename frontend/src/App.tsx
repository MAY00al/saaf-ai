import { useState, useEffect } from 'react';
import { createSession, getFarms } from './api/client';
import { useAppStore, profileFromFarm } from './store/useAppStore';
import Sidebar from './components/Sidebar';
import Toast from './components/Toast';
import Home from './pages/Home';
import Profile from './pages/Profile';
import Monitor from './pages/Monitor';
import Advisor from './pages/Advisor';
import Collect from './pages/Collect';
import Impact from './pages/Impact';
import Operator from './pages/Operator';

export default function App() {
  const [screen, setScreen] = useState('home');
  const { setSession, setProfile, setFarms, setFarm, activeFarmId } = useAppStore();

  useEffect(() => {
    // 1. إنشاء الجلسة
    createSession()
      .then((data) => setSession(data.session_id))
      .catch((err) => console.error("فشل الاتصال بالخادم:", err));

    // 2. جلب المزارع وتجهيز ملف المزرعة النشطة (بيانات محاكاة)
    getFarms()
      .then((farms) => {
        setFarms(farms);
        const current = useAppStore.getState().activeFarmId;
        const farm = farms.find((f) => f.farm_id === current) ?? farms[0];
        if (farm) {
          if (farm.farm_id !== current) setFarm(farm.farm_id);
          setProfile(profileFromFarm(farm));
        }
      })
      .catch((err) => console.error("فشل جلب المزارع:", err));
  }, [setSession, setProfile, setFarms, setFarm]);

  const renderScreen = () => {
    switch (screen) {
      case 'home': return <Home setScreen={setScreen} />;
      case 'profile': return <Profile setScreen={setScreen} />;
      case 'monitor': return <Monitor setScreen={setScreen} />;
      case 'advisor': return <Advisor setScreen={setScreen} />;
      case 'collect': return <Collect setScreen={setScreen} />;
      case 'impact': return <Impact />;
      case 'operator': return <Operator />;
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
        {/* key: عند تغيير المزرعة النشطة تُعاد تهيئة الصفحة لتعرض بياناتها */}
        <main className="content" key={`${screen}-${activeFarmId}`}>{renderScreen()}</main>

        {/* شريط سفلي يوضح أن البيانات محاكاة */}
        <div style={{ maxWidth: 1080, margin: '0 auto', padding: '0 32px 28px', fontSize: 13.5, color: '#55615A', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>فريق جُمّار · هاكاثون agentX. جميع بيانات المزرعة المعروضة هي <b>بيانات محاكاة تجريبية</b>.</span>
          <span style={{ fontSize: 12 }}>الأبحاث المذكورة مصادر حقيقية.</span>
        </div>
      </div>
      <Toast />
    </div>
  );
}
