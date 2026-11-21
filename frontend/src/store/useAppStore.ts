import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface FarmProfile {
  owner: string; name: string; region: string;
  lat: string; lon: string; area: string;
  soil: string; ph: string; irr: string; palms: string;
}

interface AppState {
  sessionId: string | null;
  activeFarmId: string | null;
  profile: FarmProfile;
  setSession: (id: string) => void;
  setFarm: (id: string) => void;
  setProfile: (p: Partial<FarmProfile>) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
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
      setSession: (id) => set({ sessionId: id }),
      setFarm: (id) => set({ activeFarmId: id }),
      setProfile: (p) => set((state) => ({ profile: { ...state.profile, ...p } })),
    }),
    { name: 'saaf-storage' }
  )
);