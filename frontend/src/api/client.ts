import { useAppStore } from '../store/useAppStore';

export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API = `${API_BASE}/api/v1`;

// يقرأ الرد ويرمي خطأ الخادم كما هو ({ error: { code, message_ar } }) عند أي حالة غير ناجحة،
// حتى لا تعتبر الصفحات أن الطلب نجح بينما رفضه الخادم (422/404/409...).
async function parse(res: Response) {
  let data: any = null;
  try { data = await res.json(); } catch { /* رد بلا محتوى */ }
  if (!res.ok) {
    throw data ?? { error: { code: 'http_error', message_ar: 'تعذّر تنفيذ الطلب.' } };
  }
  return data;
}

export async function createSession(): Promise<any> {
  return parse(await fetch(`${API}/sessions`, { method: 'POST' }));
}

// الجلسات في ذاكرة الخادم وتنتهي بعد ساعة خمول أو عند إعادة تشغيله.
// إذا انتهت جلسة المستخدم نُنشئ جلسة جديدة ونعيد المحاولة مرة واحدة بدل أن يتعطل العرض.
async function inSession<T>(call: (sessionId: string) => Promise<T>, sessionId: string): Promise<T> {
  try {
    return await call(sessionId);
  } catch (err: any) {
    if (err?.error?.code !== 'session_not_found') throw err;
    const fresh = await createSession();
    useAppStore.getState().setSession(fresh.session_id);
    return call(fresh.session_id);
  }
}

export async function getFarms(): Promise<any[]> {
  return parse(await fetch(`${API}/farms`));
}

export async function getFarmStats(): Promise<any> {
  return parse(await fetch(`${API}/farms/statistics`));
}

export async function getImpact(): Promise<any> {
  return parse(await fetch(`${API}/impact`));
}

export async function sendChat(sessionId: string, message: string, farmId?: string) {
  return inSession(async (id) => parse(await fetch(`${API}/sessions/${id}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, farm_id: farmId || null }),
  })), sessionId);
}

// === وكيل الرصد (YOLO) ===
export async function detectPalms(sessionId: string, farmId: string, file: File) {
  return inSession(async (id) => {
    const url = new URL(`${API}/sessions/${id}/monitoring/detect`);
    url.searchParams.append('farm_id', farmId);
    return parse(await fetch(url.toString(), {
      method: 'POST',
      headers: { 'Content-Type': file.type },
      body: file,
    }));
  }, sessionId);
}

// === وكيل الأقمار الصناعية (NDVI) ===
export async function getSatellite(farmId: string, mode: 'ndvi' | 'imagery' | 'history' = 'ndvi') {
  return parse(await fetch(`${API}/farms/${farmId}/satellite/${mode}`));
}

// === وكيل الجمع (Collection) ===
export async function proposeCollection(sessionId: string, farmId: string, quantityKg: number) {
  return inSession(async (id) => parse(await fetch(`${API}/sessions/${id}/collections/propose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ farm_id: farmId, requested_quantity_kg: quantityKg }),
  })), sessionId);
}

// المسودة تعيش في جلسة الخادم، لذلك لا نعيد المحاولة هنا بجلسة جديدة.
export async function confirmCollection(sessionId: string, draft: any) {
  return parse(await fetch(`${API}/sessions/${sessionId}/collections/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirmed: true, draft }),
  }));
}

export async function getFarmCollections(farmId: string): Promise<any[]> {
  return parse(await fetch(`${API}/farms/${farmId}/collections`));
}

// === حفظ حدود المزرعة (Boundary) ===
export async function saveBoundary(farmId: string, lat: number, lon: number) {
  // ننشئ مربعاً بسيطاً (~٤ هكتار) حول النقطة كحدود تجريبية للمزرعة
  const delta = 0.001;
  const boundary = {
    type: "Polygon",
    coordinates: [[
      [lon - delta, lat - delta], [lon + delta, lat - delta],
      [lon + delta, lat + delta], [lon - delta, lat + delta],
      [lon - delta, lat - delta]
    ]]
  };
  return parse(await fetch(`${API}/farms/${farmId}/boundary`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ boundary, latitude: lat, longitude: lon }),
  }));
}

export async function updateFarm(farmId: string, data: any) {
  return parse(await fetch(`${API}/farms/${farmId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }));
}
