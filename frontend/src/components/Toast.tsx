import { useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';

const COLORS = {
  success: { bg: '#E6F2EC', fg: '#0B5D3B', border: '#0B5D3B' },
  error: { bg: '#FDECEC', fg: '#8E1C1C', border: '#8E1C1C' },
  info: { bg: '#F8F1E2', fg: '#1E2A25', border: '#C8A25A' },
};

// إشعار عائم يختفي تلقائياً بعد ٤ ثوانٍ (بديل alert)
export default function Toast() {
  const toast = useAppStore((s) => s.toast);
  const clearToast = useAppStore((s) => s.clearToast);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(clearToast, 4000);
    return () => clearTimeout(t);
  }, [toast, clearToast]);

  if (!toast) return null;
  const c = COLORS[toast.kind];
  return (
    <div
      role="status"
      aria-live="polite"
      onClick={clearToast}
      style={{
        position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', zIndex: 2000,
        background: c.bg, color: c.fg, border: `1px solid ${c.border}`, borderRadius: 14,
        padding: '12px 22px', fontWeight: 700, fontSize: 15, maxWidth: '90vw',
        boxShadow: '0 8px 24px rgba(0,0,0,0.18)', cursor: 'pointer',
      }}
    >
      {toast.msg}
    </div>
  );
}
