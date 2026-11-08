import type { Config } from "tailwindcss"
import tailwindcssAnimate from "tailwindcss-animate"

// Tailwind 配置：shadcn/ui 变量驱动，扫描 index.html 与 src 下所有 ts/tsx
export default {
    darkMode: ["class"],
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
  	extend: {
  		fontFamily: {
  			display: ['var(--font-display)'],
  			sans: ['var(--font-sans)']
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		colors: {
  			background: 'oklch(var(--background-ch) / <alpha-value>)',
  			foreground: 'var(--foreground)',
  			card: {
  				DEFAULT: 'var(--card)',
  				foreground: 'var(--card-foreground)'
  			},
  			popover: {
  				DEFAULT: 'var(--popover)',
  				foreground: 'var(--popover-foreground)'
  			},
  			primary: {
  				DEFAULT: 'oklch(var(--primary-ch) / <alpha-value>)',
  				foreground: 'var(--primary-foreground)'
  			},
  			secondary: {
  				DEFAULT: 'oklch(var(--secondary-ch) / <alpha-value>)',
  				foreground: 'var(--secondary-foreground)'
  			},
  			muted: {
  				DEFAULT: 'oklch(var(--muted-ch) / <alpha-value>)',
  				foreground: 'var(--muted-foreground)'
  			},
  			accent: {
  				DEFAULT: 'var(--accent)',
  				foreground: 'var(--accent-foreground)'
  			},
  			destructive: {
  				DEFAULT: 'oklch(var(--destructive-ch) / <alpha-value>)',
  				foreground: 'var(--destructive-foreground)'
  			},
  			border: 'var(--border)',
  			input: 'var(--input)',
  			ring: 'var(--ring)',
  			surface: {
  				DEFAULT: 'oklch(var(--surface-1-ch) / <alpha-value>)',
  				1: 'oklch(var(--surface-1-ch) / <alpha-value>)',
  				2: 'oklch(var(--surface-2-ch) / <alpha-value>)'
  			},
  			glow: {
  				DEFAULT: 'var(--glow)',
  				spread: 'var(--glow-spread)'
  			},
  			chart: {
  				'1': 'var(--chart-1)',
  				'2': 'var(--chart-2)',
  				'3': 'var(--chart-3)',
  				'4': 'var(--chart-4)',
  				'5': 'var(--chart-5)'
  			},
  			sidebar: {
  				DEFAULT: 'var(--sidebar)',
  				foreground: 'var(--sidebar-foreground)',
  				primary: 'var(--sidebar-primary)',
  				'primary-foreground': 'var(--sidebar-primary-foreground)',
  				accent: 'var(--sidebar-accent)',
  				'accent-foreground': 'var(--sidebar-accent-foreground)',
  				border: 'var(--sidebar-border)',
  				ring: 'var(--sidebar-ring)'
  			}
  		},
  		keyframes: {
  			'spin-slow': {
  				to: { transform: 'rotate(360deg)' }
  			}
  		},
  		animation: {
  			'spin-slow': 'spin-slow 6s linear infinite'
  		}
  	}
  },
  plugins: [tailwindcssAnimate],
} satisfies Config
