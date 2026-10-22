import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0b1020",
        panel: "#131a2e",
        edge: "#22304f",
        accent: "#38bdf8",
        danger: "#f87171",
        warn: "#fbbf24",
        ok: "#34d399",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
