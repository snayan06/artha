import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17211d',
        moss: {
          50: '#f2f7f4',
          100: '#e2eee8',
          200: '#c5ddd1',
          300: '#9fc5b4',
          400: '#73aa93',
          500: '#4f8e76',
          600: '#3b715e',
          700: '#315b4d',
          800: '#294a40',
          900: '#173f35'
        },
        canvas: '#f5f7f2',
        line: '#e1e6de',
        night: {
          canvas: '#111412',
          surface: '#1a1f1c',
          raised: '#202622',
          input: '#151a17',
          border: '#313a35',
          text: '#f2f1ec',
          muted: '#a7b0aa',
          subtle: '#87928c'
        }
      },
      boxShadow: {
        card: '0 12px 36px rgba(28, 55, 45, 0.06)',
        float: '0 18px 48px rgba(18, 51, 42, 0.2)'
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif']
      }
    }
  },
  plugins: []
} satisfies Config
