import { build } from "esbuild";
export async function moduleFrom(path) {
  const result = await build({
    entryPoints: [path],
    bundle: true,
    write: false,
    format: "esm",
    platform: "node",
  });
  return import(
    `data:text/javascript;base64,${Buffer.from(
      result.outputFiles[0].text
    ).toString("base64")}`
  );
}
