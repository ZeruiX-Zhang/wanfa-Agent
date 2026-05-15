import type { Config } from "tailwindcss";

function color(token: string) {
  return `rgb(var(--color-${token}) / <alpha-value>)`;
}

const config: Config = {
  darkMode: ["class", "[data-appearance='dark']"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: color("background"),
        foreground: color("foreground"),
        panel: color("panel"),
        "panel-muted": color("panel-muted"),
        border: color("border"),
        "border-strong": color("border-strong"),
        muted: color("muted"),
        accent: color("accent"),
        "accent-soft": color("accent-soft"),
        "accent-foreground": color("accent-foreground"),
        success: color("success"),
        warning: color("warning"),
        danger: color("danger"),
        ink: color("ink"),
      },
      boxShadow: {
        panel: "var(--shadow-panel)",
      },
      borderRadius: {
        panel: "var(--radius-panel)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "Segoe UI",
          "-apple-system",
          "BlinkMacSystemFont",
          "PingFang SC",
          "Noto Sans SC",
          "Source Han Sans SC",
          "Microsoft YaHei",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
