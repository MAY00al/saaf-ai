import { Home, User, Eye, MessageCircle, Calendar, BarChart3 } from 'lucide-react';

export default function Sidebar({ screen, setScreen }: { screen: string, setScreen: (s: string) => void }) {
  const nav = [
    { key: 'home', label: 'الرئيسية', icon: Home },
    { key: 'profile', label: 'ملفي', icon: User },
    { key: 'monitor', label: '١ الرصد', icon: Eye },
    { key: 'advisor', label: '٢ المرشد', icon: MessageCircle },
    { key: 'collect', label: '٣ الجمع', icon: Calendar },
    { key: 'impact', label: '٤ الأثر', icon: BarChart3 },
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
        <div style={{ fontWeight: 700 }}></div>
        <div style={{ color: '#E6F2EC', fontSize: 13 }}>مزرعة الأحساء · الأحساء</div>
      </div>
    </aside>
  );
}