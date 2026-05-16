import type { Config } from 'tailwindcss'

export default <Partial<Config>>{
  content: [
    './components/**/*.{vue,js,ts}',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './app.vue',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#070B16',
          900: '#0F172A',
          800: '#111A2E',
          700: '#1E293B',
          600: '#272F42',
          500: '#334155',
          400: '#475569',
        },
        neon: {
          green: '#22C55E',
          cyan: '#22D3EE',
          violet: '#A855F7',
          magenta: '#EC4899',
        },
        fg: {
          DEFAULT: '#F8FAFC',
          muted: '#94A3B8',
          dim: '#64748B',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 32px -8px rgba(34, 197, 94, 0.55)',
        'glow-violet': '0 0 32px -8px rgba(168, 85, 247, 0.55)',
        'glow-cyan': '0 0 32px -8px rgba(34, 211, 238, 0.55)',
      },
      backgroundImage: {
        'grid-fade':
          'radial-gradient(circle at 50% 0%, rgba(168,85,247,0.18), transparent 60%), radial-gradient(circle at 80% 30%, rgba(34,211,238,0.12), transparent 50%), radial-gradient(circle at 20% 70%, rgba(34,197,94,0.10), transparent 55%)',
        'neon-gradient':
          'linear-gradient(135deg, #22C55E 0%, #22D3EE 50%, #A855F7 100%)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'flow': 'flow 3s ease-in-out infinite',
        'fade-up': 'fadeUp 0.6s cubic-bezier(0.2, 0.7, 0.2, 1) both',
      },
      keyframes: {
        flow: {
          '0%, 100%': { opacity: '0.4', transform: 'translateX(0)' },
          '50%': { opacity: '1', transform: 'translateX(4px)' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
}
