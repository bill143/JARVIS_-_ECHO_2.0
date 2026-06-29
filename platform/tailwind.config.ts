import type { Config } from "tailwindcss";

/**
 * All colors are driven by CSS variables defined in styles/globals.css
 * (`:root` = light, `[data-theme="dark"]` = dark). Components must use these
 * token classes (e.g. `bg-panel`, `text-muted`) and never hardcode hex values.
 */
const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        panel: "var(--panel)",
        "panel-edge": "var(--panel-edge)",
        line: "var(--line)",
        text: "var(--text)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        amber: "var(--amber)",
        flag: "var(--flag)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderColor: {
        DEFAULT: "var(--line)",
      },
    },
  },
  plugins: [],
};

export default config;
