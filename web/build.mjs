import { build } from "esbuild";
import { copyFile, mkdir } from "node:fs/promises";

await mkdir("dist", { recursive: true });
await build({
  entryPoints: ["src/main.tsx"],
  bundle: true,
  outfile: "dist/app.js",
  format: "esm",
  target: "es2020",
  minify: true,
});
for (const file of ["index.html", "config.json"]) {
  await copyFile(file, `dist/${file}`);
}
