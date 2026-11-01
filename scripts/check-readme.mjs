#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.resolve(__dirname, "..");
export const DEFAULT_README_PATH = path.join(REPO_ROOT, "README.md");

// ceil(2130 * 1.10 / 50) * 50 = 2350 (post-cut word count: 2130).
export const README_WORD_CAP = 2350;

export const ALLOWED_H2_HEADINGS = Object.freeze([
  "Family: repairing the result",
  "Trials",
  "Layout",
  "How they were made",
  "Terms",
  "How rig-parts fetches this",
]);

const ALLOWED_H2_SET = new Set(ALLOWED_H2_HEADINGS);
const DATED_MEASUREMENT_RE = /\b(?:measured|read)\s+on\s+20/giu;
const ISO_DATE_RE = /\b\d{4}-\d{2}-\d{2}\b/gu;

export function countWords(markdown) {
  const trimmed = markdown.trim();
  if (trimmed.length === 0) return 0;
  return trimmed.split(/\s+/u).length;
}

function lineNumberAt(text, index) {
  let line = 1;
  for (let i = 0; i < index; i += 1) {
    if (text.charCodeAt(i) === 10) line += 1;
  }
  return line;
}

export function checkReadme(markdown) {
  const violations = [];
  const words = countWords(markdown);
  if (words > README_WORD_CAP) {
    violations.push({
      code: "README_WORD_CAP",
      line: 1,
      message: `README word count ${words} exceeds README_WORD_CAP (${README_WORD_CAP})`,
    });
  }

  for (const match of markdown.matchAll(DATED_MEASUREMENT_RE)) {
    const phrase = match[0].replace(/\s+/gu, " ");
    const line = lineNumberAt(markdown, match.index ?? 0);
    violations.push({
      code: "README_DATED_PHRASE",
      line,
      message: `line ${line}: forbidden dated-measurement phrase ${JSON.stringify(phrase)}`,
    });
  }

  const lines = markdown.split(/\r?\n/u);
  const headings = [];
  let fenceMarker = null;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const lineNumber = index + 1;

    const fenceMatch = line.match(/^ {0,3}(`{3,}|~{3,})/u);
    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (fenceMarker === null) {
        fenceMarker = marker;
      } else if (
        marker[0] === fenceMarker[0] &&
        marker.length >= fenceMarker.length &&
        line.slice(fenceMatch[0].length).trim() === ""
      ) {
        fenceMarker = null;
      }
      continue;
    }

    if (fenceMarker !== null) continue;

    const h2Match = line.match(/^ {0,3}##(?!#)\s*(.*?)\s*#*\s*$/u);
    if (h2Match) {
      const heading = (h2Match[1] ?? "").trim();
      headings.push(heading);
      if (!ALLOWED_H2_SET.has(heading)) {
        violations.push({
          code: "README_HEADING",
          line: lineNumber,
          message:
            `line ${lineNumber}: ## heading ${JSON.stringify(heading)} is not on the allowlist ` +
            `(${ALLOWED_H2_HEADINGS.map((h) => JSON.stringify(h)).join(", ")})`,
        });
      }
    }

    const trimmed = line.trim();
    if (trimmed.includes("|")) {
      for (const match of trimmed.matchAll(ISO_DATE_RE)) {
        violations.push({
          code: "README_TABLE_DATE",
          line: lineNumber,
          message: `line ${lineNumber}: forbidden YYYY-MM-DD date ${JSON.stringify(match[0])} inside a table cell`,
        });
      }
    }
  }

  return {
    ok: violations.length === 0,
    words,
    wordCap: README_WORD_CAP,
    headings,
    violations,
  };
}

function main() {
  const readmePath = process.argv[2]
    ? path.resolve(process.argv[2])
    : DEFAULT_README_PATH;
  const markdown = fs.readFileSync(readmePath, "utf8");
  const result = checkReadme(markdown);
  const relPath = path.relative(REPO_ROOT, readmePath) || "README.md";

  if (!result.ok) {
    for (const violation of result.violations) {
      console.error(`${relPath}:${violation.line}: [${violation.code}] ${violation.message}`);
    }
    process.exit(1);
  }

  console.log(
    `OK: ${relPath} (${result.words}/${result.wordCap} words, ${result.headings.length} ## headings)`,
  );
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
) {
  main();
}
