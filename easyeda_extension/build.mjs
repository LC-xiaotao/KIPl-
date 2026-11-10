/**
 * Builds the EasyEDA Pro extension package (`.eext`).
 *
 * The extension loader expects an IIFE bundle exposing the functions named in
 * `headerMenus[].registerFn`; `edaEsbuildExportName` is the global the official
 * easyeda-api-sdk uses for that bundle. The `.eext` itself is a plain ZIP.
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import esbuild from "esbuild";
import JSZip from "jszip";

const root = path.dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(fs.readFileSync(path.join(root, "extension.json"), "utf8"));
const distDir = path.join(root, "dist");
const outDir = path.join(root, "build");
const eextPath = path.join(outDir, `${config.name}_v${config.version}.eext`);

const included = ["extension.json", "dist", "images", "locales", "README.md"];

function walk(relative) {
	const absolute = path.join(root, relative);
	if (!fs.existsSync(absolute)) {
		return [];
	}
	const stat = fs.statSync(absolute);
	if (stat.isFile()) {
		return [relative.replaceAll(path.sep, "/")];
	}
	return fs.readdirSync(absolute, { withFileTypes: true })
		.sort((a, b) => a.name.localeCompare(b.name))
		.flatMap(entry => walk(path.join(relative, entry.name)));
}

await esbuild.build({
	entryPoints: { index: path.join(root, "src", "index.ts") },
	bundle: true,
	platform: "browser",
	format: "iife",
	globalName: "edaEsbuildExportName",
	target: "es2020",
	minify: false,
	outdir: distDir,
	entryNames: "[name]",
	logLevel: "info",
});

const zip = new JSZip();
for (const relative of included.flatMap(walk)) {
	zip.file(relative, fs.readFileSync(path.join(root, relative)));
}
fs.mkdirSync(outDir, { recursive: true });
const bytes = await zip.generateAsync({
	type: "nodebuffer",
	compression: "DEFLATE",
	compressionOptions: { level: 9 },
});
fs.writeFileSync(eextPath, bytes);
console.log(`Packaged: ${eextPath}`);
