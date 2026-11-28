// سعفة نخيل مرسومة بـ SVG: عرق منحنٍ ووريقات متناظرة. تُستخدم كزخرفة وكعلامة في الواجهة.
const STEM = "M24 94 Q18 38 82 10";
const LEAVES = "M24.4 72.7Q19.3 62.7 9.2 51.9 M24.4 72.7Q32.4 64.8 45.3 57.6 M26.1 65.0Q22.6 54.9 14.4 43.5 M26.1 65.0Q34.3 58.2 47.2 52.7 M28.6 57.7Q26.8 47.7 20.4 35.9 M28.6 57.7Q36.9 51.9 49.7 48.0 M32.0 50.7Q31.7 41.2 27.1 29.2 M32.0 50.7Q40.2 45.9 52.8 43.5 M36.2 44.0Q37.3 35.1 34.3 23.3 M36.2 44.0Q44.3 40.1 56.4 39.1 M41.3 37.7Q43.5 29.6 42.0 18.2 M41.3 37.7Q49.1 34.6 60.6 34.8 M47.2 31.7Q50.3 24.5 50.0 13.7 M47.2 31.7Q54.6 29.2 65.4 30.5 M54.0 26.0Q57.7 19.8 58.5 9.7 M54.0 26.0Q61.0 24.1 71.0 26.1 M61.6 20.7Q65.8 15.5 67.3 6.1 M61.6 20.7Q68.1 19.2 77.3 21.8 M70.1 15.8Q74.5 11.5 76.5 2.8 M70.1 15.8Q76.1 14.4 84.5 17.5 M79.5 11.1Q83.9 7.8 86.3 -0.2 M79.5 11.1Q84.9 10.0 92.5 13.4";

export default function PalmFrond({
  size = 64, color = 'currentColor', opacity = 1, style, className,
}: { size?: number | string; color?: string; opacity?: number; style?: React.CSSProperties; className?: string }) {
  return (
    <svg
      className={className} viewBox="0 0 100 100" width={size} height={size} aria-hidden="true" focusable="false"
      style={{ opacity, flexShrink: 0, ...style }}
      fill="none" stroke={color} strokeLinecap="round" strokeLinejoin="round"
    >
      <path d={STEM} strokeWidth="3.2" />
      <path d={LEAVES} strokeWidth="2.6" />
    </svg>
  );
}
