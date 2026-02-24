import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          charcoal: "#1A1A1A",    // Primary dark background
          cream: "#F7F5F0",       // Primary light background
          goldenrod: "#C2A676",   // Primary action color
          sage: "#4A5D4E",        // Success states
          slate: "#5C6B7F",       // Muted text, inactive icons
          bone: "#FFFFFF",        // Card backgrounds, text on dark
          clay: "#A05040",        // Error/alert
          mist: "#E5E5E5",        // Subtle borders
          amber: "#D4A84B",       // Warning, in-progress
        },
      },
      fontFamily: {
        display: [
          "Playfair Display", "Georgia", "Times New Roman", "serif",
        ],
        sans: [
          "Inter", "DM Sans", "-apple-system", "BlinkMacSystemFont",
          "Segoe UI", "sans-serif",
        ],
      },
      fontSize: {
        display: ["72px", { lineHeight: "1.1", fontWeight: "700" }],
        h1: ["48px", { lineHeight: "1.2", fontWeight: "700" }],
        h2: ["36px", { lineHeight: "1.25", fontWeight: "600" }],
        h3: ["30px", { lineHeight: "1.3", fontWeight: "600" }],
        h4: ["24px", { lineHeight: "1.4", fontWeight: "500" }],
        h5: ["20px", { lineHeight: "1.4", fontWeight: "500" }],
        "body-lg": ["18px", { lineHeight: "1.7" }],
        body: ["16px", { lineHeight: "1.6" }],
        "body-sm": ["14px", { lineHeight: "1.5" }],
        caption: ["12px", { lineHeight: "1.4" }],
        data: ["11px", { lineHeight: "1.3", fontFamily: "monospace" }],
      },
      spacing: {
        "sp-1": "4px",
        "sp-2": "8px",
        "sp-3": "12px",
        "sp-4": "16px",
        "sp-5": "20px",
        "sp-6": "24px",
        "sp-8": "32px",
        "sp-10": "40px",
        "sp-12": "48px",
        "sp-16": "64px",
        "sp-20": "80px",
        "sp-24": "96px",
        "sp-32": "128px",
      },
      letterSpacing: {
        headline: "-0.02em",
        normal: "0",
        caps: "0.05em",
      },
      borderRadius: {
        pill: "9999px",
        card: "8px",
      },
      boxShadow: {
        card: "0 4px 20px rgba(0, 0, 0, 0.05)",
        "card-hover": "0 8px 30px rgba(0, 0, 0, 0.08)",
        panel: "0 8px 40px rgba(0, 0, 0, 0.12)",
      },
      maxWidth: {
        narrow: "640px",
        default: "1024px",
        wide: "1280px",
        full: "1400px",
      },
      transitionDuration: {
        micro: "150ms",
        state: "250ms",
        page: "350ms",
        modal: "250ms",
      },
      screens: {
        sm: "640px",
        md: "768px",
        lg: "1024px",
        xl: "1280px",
        "2xl": "1400px",
      },
      keyframes: {
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 350ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
