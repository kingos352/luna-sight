/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        space: {
          950: '#07090e',
          900: '#0c1017',
          850: '#111722',
          800: '#161f2e',
          700: '#233147',
          600: '#344765'
        },
        luna: {
          sun: '#fbbf24',      // Sıcak sarı
          earth: '#38bdf8',    // Buz mavisi
          visible: '#22c55e',  // Yeşil
          blocked: '#ef4444',  // Kırmızı
          uncertain: '#f59e0b',// Amber / Turuncu
          surface: '#94a3b8'   // Ay regolit grisi
        }
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', '"Liberation Mono"', '"Courier New"', 'monospace']
      }
    },
  },
  plugins: [],
}
