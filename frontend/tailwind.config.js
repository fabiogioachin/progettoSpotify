import { COLORS, withAlpha } from './src/lib/palette.js'

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: COLORS.background,
        surface: COLORS.surface,
        'surface-hover': COLORS.surfaceHover,
        border: COLORS.border,
        'border-hover': COLORS.borderHover,
        accent: COLORS.accent,
        'accent-hover': COLORS.accentHover,
        'accent-pale': COLORS.accentPale,
        'accent-glow': withAlpha(COLORS.accent, 0.15),
        spotify: COLORS.spotify,
        'text-primary': COLORS.textPrimary,
        'text-secondary': COLORS.textSecondary,
        'text-muted': COLORS.textMuted,
      },
      fontFamily: {
        display: ['Space Grotesk', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
        'shimmer': 'shimmer 1.5s ease-in-out infinite',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: `0 0 20px ${withAlpha(COLORS.accent, 0.1)}` },
          '50%': { boxShadow: `0 0 40px ${withAlpha(COLORS.accent, 0.3)}` },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
    },
  },
  plugins: [],
}
