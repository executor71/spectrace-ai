import type { Screen } from './navigation'

// Local solid SVG pictograms; no icon font, emoji or runtime dependency.
const paths: Record<Screen | 'arrow' | 'close' | 'menu' | 'check', string> = {
  impact: 'M2 3h8v3H5v12h5v3H2V3zm12 0h8v18h-8v-3h5V6h-5V3zM8 10h8l-3-3 2-2 6 7-6 7-2-2 3-3H8v-4z',
  dashboard: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  requirements: 'M5 2h9l5 5v15H5V2zm9 1v5h5l-5-5zM8 11v2h8v-2H8zm0 5v2h8v-2H8z',
  analysis: 'M3 2h12v8a7 7 0 0 0-7 11H3V2zm3 4v2h6V6H6zm0 5v2h4v-2H6zm10 0a5 5 0 1 0 2.75 9.18L22 23l1.4-1.4-3.22-3.25A5 5 0 0 0 16 11zm0 2a3 3 0 1 1 0 6 3 3 0 0 1 0-6z',
  testcases: 'M9 4h12v3H9V4zm0 7h12v3H9v-3zm0 7h12v3H9v-3zM2 4h4v3H2V4zm0 7h4v3H2v-3zm0 7h4v3H2v-3z',
  review: 'M12 2 3 6v6c0 5 5 8 9 10 4-2 9-5 9-10V6l-9-4zm-1.5 14L6 11.5 7.5 10l3 3 6-6L18 8.5 10.5 16z',
  execution: 'M7 3v18l15-9L7 3zM2 3h3v18H2V3z',
  evaluation: 'M2 2h2v18h18v2H2V2zm5 9h3v7H7v-7zm5-7h3v14h-3V4zm5 4h3v10h-3V8z',
  graph: 'M3 2h6v5H7v3h10V7h-2V2h6v5h-2v5h-6v5h2v5H9v-5h2v-5H5V7H3V2z',
  arrow: 'm14 4 8 8-8 8-1.5-1.5L18 13H2v-2h16l-5.5-5.5L14 4z',
  close: 'm5 3 7 7 7-7 2 2-7 7 7 7-2 2-7-7-7 7-2-2 7-7-7-7 2-2z',
  menu: 'M3 4h18v3H3V4zm0 7h18v3H3v-3zm0 7h18v3H3v-3z',
  check: 'm3 11 6 6L21 5l2 2L9 21l-8-8 2-2z',
}
export default function Icon({ name, size = 20 }: { name: keyof typeof paths; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path fillRule="evenodd" d={paths[name]} /></svg>
}
