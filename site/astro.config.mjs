// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  site: "https://piewall.th33raphat.dev",
  output: "static",
  trailingSlash: "never",
  build: {
    format: "file",
    // Keep CSS in external files so the CSP can stay `style-src 'self'`.
    inlineStylesheets: "never",
  },
  devToolbar: { enabled: false },
  vite: {
    plugins: [tailwindcss()],
    // Always emit JS as hashed files, never inline, so the CSP stays script-src 'self'.
    build: { assetsInlineLimit: 0 },
  },
});
