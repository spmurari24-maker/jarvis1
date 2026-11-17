import { copyFileSync, existsSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const projectRoot = process.cwd();
const publicRoot = resolve(projectRoot, "firebase_public");
const sourceStatic = resolve(projectRoot, "jarvis", "static");
const publicStatic = resolve(publicRoot, "static");
const configPath = resolve(projectRoot, "config", "firebase-web-config.json");
const config = JSON.parse(readFileSync(configPath, "utf8"));

if (config.projectId !== "jarvis-2112" || !config.apiKey || !config.appId) {
  throw new Error("Check config/firebase-web-config.json against the Firebase web app settings.");
}

mkdirSync(publicRoot, { recursive: true });
mkdirSync(publicStatic, { recursive: true });
copyFileSync(resolve(sourceStatic, "app.js"), resolve(publicStatic, "app.js"));
copyFileSync(resolve(sourceStatic, "styles.css"), resolve(publicStatic, "styles.css"));
const unusedStaticIndex = resolve(publicStatic, "index.html");
if (existsSync(unusedStaticIndex)) unlinkSync(unusedStaticIndex);
const htmlPath = resolve(publicRoot, "index.html");
const html = readFileSync(resolve(sourceStatic, "index.html"), "utf8");
if (!html.includes("<!-- FIREBASE_CONFIG_SCRIPT -->")) {
  throw new Error("Firebase config insertion point is missing from the dashboard page.");
}
writeFileSync(htmlPath, html.replace(
  "<!-- FIREBASE_CONFIG_SCRIPT -->",
  '<script src="/firebase-config.js"></script>'
), "utf8");
writeFileSync(resolve(publicRoot, "firebase-config.js"),
  "window.JARVIS_FIREBASE_CONFIG = Object.freeze(" + JSON.stringify(config) + ");\n" +
  "window.JARVIS_REMOTE_AUTH_REQUIRED = true;\n", "utf8");
console.log("Prepared Firebase Hosting files in firebase_public.");
