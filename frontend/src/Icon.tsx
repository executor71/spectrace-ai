import type { Screen } from './navigation'
const paths: Record<Screen | 'arrow' | 'close' | 'menu' | 'check', string> = {
  dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  requirements: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 12h8 M8 16h6',
  analysis: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z M20 2v4 M18 4h4',
  testcases: 'M9 5h11 M9 12h11 M9 19h11 M3 5l1 1 2-2 M3 12l1 1 2-2 M3 19l1 1 2-2',
  review: 'm12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z m-4 9 3 3 5-6',
  execution: 'M9 6l10 6-10 6z M4 4v16',
  evaluation: 'M4 3v17h17 M8 15v-4 M13 15V6 M18 15V9',
  graph: 'M9 5h6 M7 8l4 9 M17 8l-4 9 M9 19h6 M7 5a2 2 0 1 0 0 .01 M17 5a2 2 0 1 0 0 .01 M12 19a2 2 0 1 0 0 .01',
  arrow: 'M4 12h15 m-6-6 6 6-6 6', close: 'm6 6 12 12 M6 18 18 6', menu: 'M4 6h16 M4 12h16 M4 18h16', check: 'm5 12 4 4L19 6',
}
export default function Icon({ name, size = 20 }: { name: keyof typeof paths; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
