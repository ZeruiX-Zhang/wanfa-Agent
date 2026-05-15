import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#f7f8fa",
        foreground: "#1c2430",
        border: "#d9dee7",
        muted: "#657184",
        panel: "#ffffff",
        accent: "#0f766e",
        warning: "#b45309",
        danger: "#b42318",
        ink: "#111827",
      },
      boxShadow: {
        panel: "0 1px 2px rgba(15, 23, 42, 0.07)",
      },
    },
  },
  plugins: [],
};

export default config;
