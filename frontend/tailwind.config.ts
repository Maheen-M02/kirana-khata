import type { Config } from "tailwindcss";

// Colour tokens live in app/globals.css as bare HSL triplets ("228 53% 23%") so Tailwind's
// opacity modifiers work (bg-ink/10). Brand story: blue ballpoint on ruled khata paper,
// with one marigold action.
const token = (name: string) => `hsl(var(--${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: token("paper"),
        ink: { DEFAULT: token("ink"), soft: token("ink-soft") },
        marigold: { DEFAULT: token("marigold"), deep: token("marigold-deep"), wash: token("marigold-wash") },
        udhaar: { DEFAULT: token("udhaar"), wash: token("udhaar-wash") },
        jama: { DEFAULT: token("jama"), wash: token("jama-wash") },
        rule: token("rule"),
        margin: token("margin"),
        // shadcn names, mapped onto the same palette
        background: token("background"),
        foreground: token("foreground"),
        card: { DEFAULT: token("card"), foreground: token("card-foreground") },
        popover: { DEFAULT: token("card"), foreground: token("card-foreground") },
        primary: { DEFAULT: token("primary"), foreground: token("primary-foreground") },
        secondary: { DEFAULT: token("secondary"), foreground: token("secondary-foreground") },
        muted: { DEFAULT: token("muted"), foreground: token("muted-foreground") },
        accent: { DEFAULT: token("accent"), foreground: token("accent-foreground") },
        destructive: { DEFAULT: token("destructive"), foreground: token("destructive-foreground") },
        border: token("border"),
        input: token("input"),
        ring: token("ring"),
      },
      fontFamily: {
        sans: ["var(--font-anek)", "Noto Sans Devanagari", "Nirmala UI", "system-ui", "sans-serif"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 8px)",
      },
      keyframes: {
        "rise-in": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "ink-dot": {
          "0%, 80%, 100%": { opacity: "0.25", transform: "translateY(0)" },
          "40%": { opacity: "1", transform: "translateY(-4px)" },
        },
        "speak-bar": {
          "0%, 100%": { transform: "scaleY(0.35)" },
          "50%": { transform: "scaleY(1)" },
        },
      },
      animation: {
        "rise-in": "rise-in 220ms cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "ink-dot": "ink-dot 1.1s ease-in-out infinite",
        "speak-bar": "speak-bar 0.9s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
