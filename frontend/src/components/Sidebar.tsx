import { Home, User, Eye, MessageCircle, Calendar, BarChart3, Truck } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

export default function Sidebar({ screen, setScreen }: { screen: string, setScreen: (s: string) => void }) {
  const { farms, activeFarmId, setFarm } = useAppStore();
  const nav = [
    { key: 'home', label: 'الرئيسية', icon: Home },
    { key: 'profile', label: 'ملفي', icon: User },
    { key: 'monitor', label: '١ الرصد', icon: Eye },
    { key: 'advisor', label: '٢ المرشد', icon: MessageCircle },
    { key: 'collect', label: '٣ الجمع', icon: Calendar },
    { key: 'impact', label: '٤ الأثر', icon: BarChart3 },
    { key: 'operator', label: 'لوحة الجامع', icon: Truck },
  ];

  return (
    <aside className="side">
      <div className="logobox">
        <img
          src="/logo.png"
          alt="شعار سعف"
          style={{ height: '70px', width: 'auto', objectFit: 'contain' }}
        />
      </div>
      <nav className="navlist">
        {nav.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              className={`navbtn ${screen === item.key ? 'active' : ''}`}
              onClick={() => setScreen(item.key)}
            >
              <Icon size={22} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="sidefoot">
        <label htmlFor="farm-select" style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 6 }}>
          المزرعة النشطة (محاكاة)
        </label>
        <select
          id="farm-select"
          value={activeFarmId ?? ''}
          onChange={(e) => setFarm(e.target.value)}
          disabled={farms.length === 0}
          style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E5DCCB', fontSize: 14, background: '#FFFDF9', color: '#1E2A25' }}
        >
          {farms.length === 0 && <option value="">{activeFarmId ?? 'جارٍ التحميل...'}</option>}
          {farms.map((f) => (
            <option key={f.farm_id} value={f.farm_id}>{f.farm_id} · {f.region}</option>
          ))}
        </select>
      </div>
    </aside>
  );
}
