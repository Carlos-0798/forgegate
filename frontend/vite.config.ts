import { defineConfig } from "vite";

export default defineConfig({
  root: "frontend",
  base: "/app/",
  build: {
    outDir: "../src/forgegate/dashboard/static",
    emptyOutDir: true,
    manifest: ".vite/manifest.json",
    license: { fileName: "third-party-licenses.json" },
    sourcemap: false,
    target: "es2022"
  }
});
