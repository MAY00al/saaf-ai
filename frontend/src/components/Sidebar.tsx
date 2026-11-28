import { House, User, ScanEye, MessageCircle, Truck, ChartColumn, Warehouse } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

const MAIN = [
  { key: 'home', label: 'الرئيسية', icon: House },
  { key: 'monitor', label: 'افحص', icon: ScanEye },
  { key: 'advisor', label: 'اسأل', icon: MessageCircle },
  { key: 'collect', label: 'اجمع', icon: Truck },
  { key: 'impact', label: 'أثرك', icon: ChartColumn },
];
const MORE = [
  { key: 'profile', label: 'ملف المزرعة', icon: User },
  { key: 'operator', label: 'لوحة الجامع', icon: Warehouse },
];

export default function Sidebar({ screen, setScreen }: { screen: string; setScreen: (s: string) => void }) {
  const { farms, activeFarmId, setFarm } = useAppStore();

  const farmSelect = (id: string) => (
    <select
      id={id}
      aria-label="المزرعة النشطة"
      value={activeFarmId ?? ''}
      onChange={(e) => setFarm(e.target.value)}
      disabled={farms.length === 0}
      className="farm-select"
    >
      {farms.length === 0 && <option value="">{activeFarmId ?? '...'}</option>}
      {farms.map((f) => (
        <option key={f.farm_id} value={f.farm_id}>{f.farm_id} · {f.region}</option>
      ))}
    </select>
  );

  return (
    <>
      {/* الشاشات الكبيرة: شريط جانبي */}
      <aside className="side">
        <div className="logobox">
          <img src="/logo-tight.png" alt="سعف" style={{ height: 64, width: 'auto', objectFit: 'contain' }} />
        </div>
        <nav className="navlist" aria-label="التنقل الرئيسي">
          {[...MAIN, ...MORE].map(({ key, label, icon: Icon }) => (
            <button key={key} className={`navbtn ${screen === key ? 'active' : ''}`} onClick={() => setScreen(key)}
              aria-current={screen === key ? 'page' : undefined}>
              <Icon size={22} strokeWidth={1.9} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidefoot">
          <label htmlFor="farm-select-d" style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 6 }}>
            المزرعة النشطة (محاكاة)
          </label>
          {farmSelect('farm-select-d')}
        </div>
      </aside>

      {/* الجوال: شريط علوي + شريط تنقل سفلي */}
      <header className="topbar">
        <img src="/logo-tight.png" alt="سعف" style={{ height: 34, width: 'auto' }} />
        <div style={{ flex: 1, minWidth: 0 }}>{farmSelect('farm-select-m')}</div>
        {MORE.map(({ key, label, icon: Icon }) => (
          <button key={key} className={`iconbtn ${screen === key ? 'active' : ''}`} onClick={() => setScreen(key)} aria-label={label} title={label}>
            <Icon size={21} strokeWidth={1.9} />
          </button>
        ))}
      </header>
      <nav className="bottomnav" aria-label="التنقل السريع">
        {MAIN.map(({ key, label, icon: Icon }) => (
          <button key={key} className={screen === key ? 'active' : ''} onClick={() => setScreen(key)}
            aria-current={screen === key ? 'page' : undefined}>
            <Icon size={23} strokeWidth={screen === key ? 2.3 : 1.8} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </>
  );
}
