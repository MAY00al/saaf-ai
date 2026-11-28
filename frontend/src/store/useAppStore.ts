import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface FarmProfile {
  owner: string; name: string; region: string;
  lat: string; lon: string; area: string;
  soil: string; ph: string; irr: string; palms: string;
}

export type ToastKind = 'success' | 'error' | 'info';

interface AppState {
  sessionId: string | null;
  activeFarmId: string | null;
  profile: FarmProfile;
  farms: any[]; // قائمة المزارع من الخادم (لا تُحفظ محلياً)
  toast: { id: number; msg: string; kind: ToastKind } | null;
  prefillQuestion: string | null;
  setSession: (id: string) => void;
  setFarm: (id: string) => void;
  setFarms: (farms: any[]) => void;
  setProfile: (p: Partial<FarmProfile>) => void;
  setPrefillQuestion: (q: string | null) => void;
  notify: (msg: string, kind?: ToastKind) => void;
  clearToast: () => void;
}

// تحويل سجل مزرعة من الخادم إلى بيانات الملف الشخصي المعروضة
export function profileFromFarm(f: any): Partial<FarmProfile> {
  return {
    owner: 'مستخدم تجريبي (Demo)',
    name: `مزرعة محاكاة ${f.farm_id}`,
    region: f.region,
    lat: String(f.lat),
    lon: String(f.lon),
    area: String(f.area_ha),
    soil: f.soil_sand_pct != null && f.soil_sand_pct > 50 ? 'رملية' : 'كلسية قلوية',
    ph: String(f.soil_ph ?? '7.4'),
    irr: f.irrigation_system || 'تنقيط',
    palms: String(f.palm_count),
  };
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      sessionId: null,
      activeFarmId: 'SIM-001',
      profile: {
        owner: 'مستخدم تجريبي (Demo)',
        name: 'مزرعة نموذجية للمحاكاة',
        region: 'الأحساء',
        lat: '25.4328',
        lon: '49.5786',
        area: '4',
        soil: 'رملية',
        ph: '7.4',
        irr: 'تنقيط',
        palms: '350'
      },
      farms: [],
      toast: null,
      prefillQuestion: null,
      setSession: (id) => set({ sessionId: id }),
      // اختيار مزرعة: نحدّث المعرّف والملف الشخصي معاً حتى تتطابق كل الصفحات
      setFarm: (id) => {
        const farm = get().farms.find((f) => f.farm_id === id);
        set((state) => ({
          activeFarmId: id,
          profile: farm ? { ...state.profile, ...profileFromFarm(farm) } : state.profile,
        }));
      },
      setFarms: (farms) => set({ farms }),
      setProfile: (p) => set((state) => ({ profile: { ...state.profile, ...p } })),
      setPrefillQuestion: (q) => set({ prefillQuestion: q }),
      notify: (msg, kind = 'info') => set({ toast: { id: Date.now(), msg, kind } }),
      clearToast: () => set({ toast: null }),
    }),
    {
      name: 'saaf-storage',
      partialize: (state) => ({ activeFarmId: state.activeFarmId, profile: state.profile }),
    }
  )
);
