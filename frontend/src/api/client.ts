export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API = `${API_BASE}/api/v1`;

export async function createSession(): Promise<any> {
  const res = await fetch(`${API}/sessions`, { method: 'POST' });
  if (!res.ok) throw new Error('فشل إنشاء الجلسة');
  return res.json();
}

export async function getFarms(): Promise<any[]> {
  const res = await fetch(`${API}/farms`);
  return res.json();
}

export async function getFarmStats(): Promise<any> {
  const res = await fetch(`${API}/farms/statistics`);
  return res.json();
}

export async function getImpact(): Promise<any> {
  const res = await fetch(`${API}/impact`);
  return res.json();
}

export async function sendChat(sessionId: string, message: string, farmId?: string) {
  const res = await fetch(`${API}/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, farm_id: farmId || null }),
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

// === وكيل الرصد (YOLO) ===
export async function detectPalms(sessionId: string, farmId: string, file: File) {
  const url = new URL(`${API}/sessions/${sessionId}/monitoring/detect`);
  url.searchParams.append('farm_id', farmId);
  const res = await fetch(url.toString(), {
    method: 'POST',
    headers: { 'Content-Type': file.type },
    body: file,
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

// === وكيل الأقمار الصناعية (NDVI) ===
export async function getSatellite(farmId: string, mode: 'ndvi' | 'imagery' | 'history' = 'ndvi') {
  const res = await fetch(`${API}/farms/${farmId}/satellite/${mode}`);
  return res.json();
}

// === وكيل الجمع (Collection) ===
export async function proposeCollection(sessionId: string, farmId: string, quantityKg: number) {
  const res = await fetch(`${API}/sessions/${sessionId}/collections/propose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ farm_id: farmId, requested_quantity_kg: quantityKg }),
  });
  return res.json();
}

export async function confirmCollection(sessionId: string, draft: any) {
  const res = await fetch(`${API}/sessions/${sessionId}/collections/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirmed: true, draft }),
  });
  return res.json();
}
// === حفظ حدود المزرعة (Boundary) ===
export async function saveBoundary(farmId: string, lat: number, lon: number) {
  // ننشئ مربعاً بسيطاً حول النقطة كحدود للمزرعة
  const delta = 0.001;
  const boundary = {
    type: "Polygon",
    coordinates: [[
      [lon - delta, lat - delta], [lon + delta, lat - delta],
      [lon + delta, lat + delta], [lon - delta, lat + delta],
      [lon - delta, lat - delta]
    ]]
  };
  const res = await fetch(`${API}/farms/${farmId}/boundary`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ boundary, latitude: lat, longitude: lon }),
  });
  return res.json();
}
export async function updateFarm(farmId: string, data: any) {
  const res = await fetch(`${API}/farms/${farmId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}