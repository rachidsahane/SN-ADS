import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const STEPS = [100, 200, 300, 400, 500, 600, 700, 800, 900] as const;

/** Échelle tonale du prototype : `--color-<name>-<step>` (valeurs hexadécimales, sans alpha). */
function scale(name: string): Record<number, string> {
  return Object.fromEntries(STEPS.map((step) => [step, `var(--color-${name}-${step})`]));
}

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Jetons sémantiques shadcn/ui (triplets HSL dans globals.css, alpha pris en charge).
        border: "hsl(var(--border) / <alpha-value>)",
        input: "hsl(var(--input) / <alpha-value>)",
        ring: "hsl(var(--ring) / <alpha-value>)",
        background: "hsl(var(--background) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        primary: {
          DEFAULT: "hsl(var(--primary) / <alpha-value>)",
          foreground: "hsl(var(--primary-foreground) / <alpha-value>)",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary) / <alpha-value>)",
          foreground: "hsl(var(--secondary-foreground) / <alpha-value>)",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive) / <alpha-value>)",
          foreground: "hsl(var(--destructive-foreground) / <alpha-value>)",
        },
        muted: {
          DEFAULT: "hsl(var(--muted) / <alpha-value>)",
          foreground: "hsl(var(--muted-foreground) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "hsl(var(--accent) / <alpha-value>)",
          foreground: "hsl(var(--accent-foreground) / <alpha-value>)",
        },
        popover: {
          DEFAULT: "hsl(var(--popover) / <alpha-value>)",
          foreground: "hsl(var(--popover-foreground) / <alpha-value>)",
        },
        card: {
          DEFAULT: "hsl(var(--card) / <alpha-value>)",
          foreground: "hsl(var(--card-foreground) / <alpha-value>)",
        },
        // États (hors prototype, contraste AA vérifié) : vert = sain, rouge = erreur.
        success: {
          DEFAULT: "hsl(var(--success) / <alpha-value>)",
          soft: "hsl(var(--success-soft) / <alpha-value>)",
        },
        danger: {
          DEFAULT: "hsl(var(--danger) / <alpha-value>)",
          soft: "hsl(var(--danger-soft) / <alpha-value>)",
        },
        // Palettes du prototype "Industry".
        brand: { DEFAULT: "var(--color-accent)", ...scale("accent") },
        brand2: { DEFAULT: "var(--color-accent-2)", ...scale("accent-2") },
        neutral: scale("neutral"),
        divider: "var(--color-divider)",
        surface: "var(--color-surface)",
      },
      // Le prototype ne fixe que la taille de police : l'interligne reste celui du corps (1.55). Tailwind imposerait
      // 1rem / 1.25rem / 1.5rem, ce qui resserrait chaque ligne.
      fontSize: {
        xs: ["0.75rem", "1.55"],
        sm: ["0.875rem", "1.55"],
        base: ["1rem", "1.55"],
      },
      maxWidth: { page: "1152px", predict: "1392px" },
      fontFamily: {
        sans: ["var(--font-body)"],
        heading: ["var(--font-heading)"],
      },
      // Composants "blueprint" : angles droits partout (prototype : radius 0 sur cartes, boutons, champs, tags, dialogues).
      borderRadius: {
        lg: "var(--radius)",
        md: "var(--radius)",
        sm: "var(--radius)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
    },
  },
  plugins: [animate],
};

export default config;
