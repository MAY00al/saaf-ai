import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { getFarms, getFarmCollections } from '../api/client';

interface RegionRow {
  region: string; farms: number; palms: number; wasteKg: number; requestedKg: number; requests: number;
}

const STATUS_AR: Record<string, string> = { confirmed: 'مؤكد', cancelled: 'ملغى' };

// لوحة الجهة التي تجمع المخلفات: ترى العرض (مخلفات المزارع المقدّرة) والطلب (طلبات الجمع المؤكدة)
export default function Operator() {
  const [farms, setFarms] = useState<any[] | null>(null);
  const [requests, setRequests] = useState<any[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const list = await getFarms();
        const perFarm = await Promise.all(list.map((f) => getFarmCollections(f.farm_id).catch(() => [])));
        if (!alive) return;
        setFarms(list);
        setRequests(perFarm.flat());
      } catch {
        if (alive) setFailed(true);
      }
    })();
    return () => { alive = false; };
  }, []);

  const confirmed = useMemo(() => requests.filter((r) => r.status === 'confirmed'), [requests]);

  const byFarm = useMemo(() => {
    const m = new Map<string, number>();
    confirmed.forEach((r) => m.set(r.farm_id, (m.get(r.farm_id) || 0) + r.requested_quantity_kg));
    return m;
  }, [confirmed]);

  const regions = useMemo<RegionRow[]>(() => {
    const m = new Map<string, RegionRow>();
    (farms ?? []).forEach((f) => {
      const row = m.get(f.region) ?? { region: f.region, farms: 0, palms: 0, wasteKg: 0, requestedKg: 0, requests: 0 };
      row.farms += 1;
      row.palms += f.palm_count;
      row.wasteKg += f.est_residue_kg_per_year;
      row.requestedKg += byFarm.get(f.farm_id) || 0;
      row.requests += confirmed.filter((r) => r.farm_id === f.farm_id).length;
      m.set(f.region, row);
    });
    return [...m.values()];
  }, [farms, byFarm, confirmed]);

  const upcoming = useMemo(() => {
    const regionOf = new Map((farms ?? []).map((f) => [f.farm_id, f.region]));
    return [...requests]
      .sort((a, b) => String(a.pickup_date).localeCompare(String(b.pickup_date)))
      .map((r) => ({ ...r, region: regionOf.get(r.farm_id) ?? '' }));
  }, [requests, farms]);

  if (failed) return <div style={{ color: '#8E1C1C' }}>تعذر تحميل اللوحة. تأكد من تشغيل الخادم.</div>;
  if (!farms) return <div>جارٍ تحميل اللوحة...</div>;

  const totalWaste = regions.reduce((s, r) => s + r.wasteKg, 0);
  const totalRequested = regions.reduce((s, r) => s + r.requestedKg, 0);
  const lats = farms.map((f) => f.lat), lons = farms.map((f) => f.lon);
  const bounds: [[number, number], [number, number]] = [
    [Math.min(...lats) - 0.2, Math.min(...lons) - 0.2],
    [Math.max(...lats) + 0.2, Math.max(...lons) + 0.2],
  ];

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <h1 style={{ fontWeight: 800, fontSize: 32, color: '#0B5D3B', margin: 0 }}>لوحة الجامع</h1>
        <div style={{ color: '#55615A', fontSize: 15, marginTop: 4 }}>
          عرض الجهة التي تستلم السعف وتحوّله إلى فحم حيوي: أين المخلفات، وكم طُلب جمعه، وما المواعيد القادمة. (بيانات محاكاة)
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
        <div style={{ flex: '1 1 200px', background: '#F8F1E2', borderRadius: 20, padding: '16px 20px' }}>
          <div style={{ color: '#0B5D3B', fontSize: 14, fontWeight: 700 }}>المخلفات السنوية المقدّرة</div>
          <div style={{ fontWeight: 800, fontSize: 28 }}>{Math.round(totalWaste / 1000).toLocaleString()} طن</div>
        </div>
        <div style={{ flex: '1 1 200px', background: '#E6F2EC', borderRadius: 20, padding: '16px 20px' }}>
          <div style={{ color: '#0B5D3B', fontSize: 14, fontWeight: 700 }}>طلبات جمع مؤكدة</div>
          <div style={{ fontWeight: 800, fontSize: 28 }}>{confirmed.length} طلب · {totalRequested.toLocaleString()} كجم</div>
        </div>
        <div style={{ flex: '1 1 200px', background: '#EAF4EE', borderRadius: 20, padding: '16px 20px' }}>
          <div style={{ color: '#0B5D3B', fontSize: 14, fontWeight: 700 }}>نسبة التغطية الحالية</div>
          <div style={{ fontWeight: 800, fontSize: 28 }}>
            {totalWaste ? ((totalRequested / totalWaste) * 100).toFixed(1) : '0'}%
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 16 }}>
        <div style={{ fontWeight: 800, color: '#0B5D3B', marginBottom: 8 }}>
          مواقع المزارع (حجم الدائرة = المخلفات المقدّرة، الذهبي = لديها طلب مؤكد)
        </div>
        <div style={{ height: 340, borderRadius: 16, overflow: 'hidden', zIndex: 0 }}>
          <MapContainer bounds={bounds} style={{ height: '100%', width: '100%' }}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
            {farms.map((f) => {
              const has = (byFarm.get(f.farm_id) || 0) > 0;
              return (
                <CircleMarker
                  key={f.farm_id}
                  center={[f.lat, f.lon]}
                  radius={5 + Math.sqrt(f.est_residue_kg_per_year) / 15}
                  pathOptions={{ color: has ? '#8a6a1f' : '#0B5D3B', fillColor: has ? '#C8A25A' : '#0B5D3B', fillOpacity: 0.65 }}
                >
                  <Popup>
                    <b>{f.farm_id}</b> · {f.region}<br />
                    النخيل: {f.palm_count.toLocaleString()}<br />
                    المخلفات المقدّرة: {f.est_residue_kg_per_year.toLocaleString()} كجم/سنة<br />
                    طلبات مؤكدة: {(byFarm.get(f.farm_id) || 0).toLocaleString()} كجم
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <div style={{ fontWeight: 800, color: '#0B5D3B', marginBottom: 12 }}>العرض والطلب حسب المنطقة</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {regions.map((r) => {
            const pct = r.wasteKg ? Math.min(100, (r.requestedKg / r.wasteKg) * 100) : 0;
            return (
              <div key={r.region}>
                <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, fontSize: 15 }}>
                  <b>{r.region}</b>
                  <span style={{ color: '#55615A' }}>
                    {r.farms} مزرعة · {r.palms.toLocaleString()} نخلة · {Math.round(r.wasteKg / 1000).toLocaleString()} طن مقدّر ·
                    مطلوب جمعه {r.requestedKg.toLocaleString()} كجم ({r.requests} طلب)
                  </span>
                </div>
                <div style={{ background: '#E5DCCB', borderRadius: 8, height: 10, marginTop: 6 }} aria-hidden="true">
                  <div style={{ width: `${Math.max(pct, pct > 0 ? 1.5 : 0)}%`, background: '#0B5D3B', height: '100%', borderRadius: 8 }} />
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ fontSize: 12.5, color: '#55615A', marginTop: 12 }}>
          التقدير السنوي = عدد النخيل × 35 كجم (NASSER2016). الكميات المطلوبة هي طلبات محاكاة ولا تمثل استلاماً ميدانياً.
        </div>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <div style={{ fontWeight: 800, color: '#0B5D3B', marginBottom: 12 }}>جدول الاستلام</div>
        {upcoming.length === 0 ? (
          <div style={{ color: '#55615A' }}>
            لا توجد طلبات بعد. أنشئ طلباً من صفحة «٣ الجمع» وسيظهر هنا فوراً.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 15 }}>
              <thead>
                <tr style={{ textAlign: 'right', color: '#55615A', borderBottom: '1px solid #E5DCCB' }}>
                  <th style={{ padding: 8 }}>التاريخ</th><th style={{ padding: 8 }}>المزرعة</th>
                  <th style={{ padding: 8 }}>المنطقة</th><th style={{ padding: 8 }}>الكمية (كجم)</th>
                  <th style={{ padding: 8 }}>الحالة</th>
                </tr>
              </thead>
              <tbody>
                {upcoming.map((r) => (
                  <tr key={r.request_id} style={{ borderBottom: '1px solid #F0F0F0', opacity: r.status === 'cancelled' ? 0.5 : 1 }}>
                    <td style={{ padding: 8 }}>{r.pickup_date}</td>
                    <td style={{ padding: 8 }}>{r.farm_id}</td>
                    <td style={{ padding: 8 }}>{r.region}</td>
                    <td style={{ padding: 8 }}>{r.requested_quantity_kg.toLocaleString()}</td>
                    <td style={{ padding: 8 }}>{STATUS_AR[r.status] ?? r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
