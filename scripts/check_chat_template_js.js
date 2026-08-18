"use strict";

const { mkdtempSync, readFileSync, rmSync, writeFileSync } = require("fs");
const { tmpdir } = require("os");
const { join } = require("path");
const { spawnSync } = require("child_process");

const templatePath = join(__dirname, "..", "app", "templates", "messages", "chat.html");
const template = readFileSync(templatePath, "utf8");
const scripts = [...template.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((match) => match[1]);

if (!scripts.length) {
  throw new Error("لم يُعثر على JavaScript داخل قالب المحادثة.");
}

const renderedLikeJavaScript = scripts
  .join("\n")
  .replace(/\{\{[\s\S]*?\}\}/g, "null")
  .replace(/\{%[\s\S]*?%\}/g, "");
const temporaryDirectory = mkdtempSync(join(tmpdir(), "anter-chat-js-"));
const temporaryFile = join(temporaryDirectory, "chat-template.js");

try {
  writeFileSync(temporaryFile, renderedLikeJavaScript, "utf8");
  const result = spawnSync(process.execPath, ["--check", temporaryFile], { encoding: "utf8" });
  if (result.status !== 0) {
    process.stderr.write(result.stderr || result.stdout || "فشل فحص JavaScript لقالب المحادثة.\n");
    process.exit(result.status || 1);
  }
  console.log("JavaScript قالب المحادثة: OK");
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
