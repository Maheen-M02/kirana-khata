import type { Config } from "tailwindcss";

// Same tokens as the app (frontend/tailwind.config.ts): blue ballpoint on ruled khata paper,
// with one marigold action.
const token = (name: string) => `hsl(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
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
      },
      fontFamily: {
        sans: ["var(--font-anek)", "Noto Sans Devanagari", "Nirmala UI", "system-ui", "sans-serif"],
      },
      keyframes: {
        "rise-in": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "speak-bar": {
          "0%, 100%": { transform: "scaleY(0.35)" },
          "50%": { transform: "scaleY(1)" },
        },
        "ink-in": {
          from: { clipPath: "inset(0 100% 0 0)" },
          to: { clipPath: "inset(0 0 0 0)" },
        },
      },
      animation: {
        "rise-in": "rise-in 260ms cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "speak-bar": "speak-bar 0.9s ease-in-out infinite",
        "ink-in": "ink-in 700ms cubic-bezier(0.6, 0, 0.2, 1) both",
      },
    },
  },
};
export default config;
