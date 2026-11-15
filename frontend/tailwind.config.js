/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // NASA GMAT & Aerospace Mission Control Palette
        gmat: {
          bg: '#080D16',          // Primary dark background
          panel: '#111927',       // Secondary panels
          elevated: '#182235',    // Elevated card surfaces
          border: '#29374A',      // Subtle aerospace borders
          borderLight: '#3D4F67', // Highlight borders
          accent: '#38BDF8',      // Primary cyan/sky accent
          accentHover: '#0ea5e9',
          green: '#22C55E',       // Scientific nominal green
          amber: '#F59E0B',       // Warning amber
          red: '#EF4444',         // Critical red
          purple: '#A855F7',      // AI inference violet
          text: '#E5EDF7',        // Primary telemetry text
          textMuted: '#94A3B8',   // Secondary metadata text
          textDim: '#64748B',     // Dim timestamp text
        },
        space: {
          950: '#080D16',
          900: '#111927',
          850: '#151F30',
          800: '#182235',
          700: '#29374A',
          600: '#3D4F67'
        },
        luna: {
          sun: '#fbbf24',      // Warm solar gold
          earth: '#38bdf8',    // Ice blue direct-to-earth
          visible: '#22c55e',  // Nominal visible
          blocked: '#ef4444',  // Obstructed
          uncertain: '#f59e0b',// Boundary transition zone
          surface: '#94a3b8'   // Regolith gray
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace']
      },
      boxShadow: {
        'gmat-panel': '0 4px 20px -2px rgba(8, 13, 22, 0.7), 0 0 0 1px rgba(41, 55, 74, 0.6)',
        'gmat-glow': '0 0 15px rgba(56, 189, 248, 0.15)',
        'gmat-amber': '0 0 15px rgba(245, 158, 11, 0.15)',
        'gmat-green': '0 0 15px rgba(34, 197, 94, 0.15)',
      }
    },
  },
  plugins: [],
}
