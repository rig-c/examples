import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  ALLOWED_H2_HEADINGS,
  DEFAULT_README_PATH,
  README_WORD_CAP,
  REPO_ROOT,
  checkReadme,
  countWords,
} from "./check-readme.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CHECK_SCRIPT_PATH = path.join(__dirname, "check-readme.mjs");

function githubSlug(headingText) {
  return headingText
    .trim()
    .toLowerCase()
    .replace(/[`*~_]/gu, "")
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .trim()
    .replace(/\s+/gu, "-");
}

test("README.md passes checkReadme and CLI check", () => {
  const markdown = fs.readFileSync(DEFAULT_README_PATH, "utf8");
  const result = checkReadme(markdown);
  assert.equal(result.ok, true, JSON.stringify(result.violations, null, 2));
  assert.ok(
    result.words <= README_WORD_CAP,
    `expected words ${result.words} <= ${README_WORD_CAP}`,
  );
  assert.deepEqual(result.headings, [...ALLOWED_H2_HEADINGS]);
  assert.equal(
    markdown.includes("### Prompts, verbatim"),
    false,
    "### Prompts, verbatim must not appear in README.md",
  );

  const cli = spawnSync(process.execPath, [CHECK_SCRIPT_PATH], {
    cwd: REPO_ROOT,
    encoding: "utf8",
  });
  assert.equal(cli.status, 0, cli.stderr);
  assert.match(cli.stdout, /^OK: README\.md \(\d+\/2350 words, 6 ## headings\)/u);
});

test("README.md local links and inbound anchors resolve", () => {
  const markdown = fs.readFileSync(DEFAULT_README_PATH, "utf8");
  const headingSlugs = new Set();
  for (const line of markdown.split(/\r?\n/u)) {
    const m = line.match(/^ {0,3}#{1,6}\s+(.*?)\s*#*\s*$/u);
    if (m) headingSlugs.add(githubSlug(m[1]));
  }
  assert.ok(headingSlugs.has("trials"), "expected #trials anchor to exist");

  const linkRe = /\[[^\]]*\]\(([^)]+)\)/gu;
  for (const match of markdown.matchAll(linkRe)) {
    const rawTarget = match[1].trim();
    if (/^(?:https?:|mailto:)/iu.test(rawTarget)) continue;
    if (rawTarget.startsWith("#")) {
      const slug = rawTarget.slice(1);
      assert.ok(
        headingSlugs.has(slug),
        `unresolved internal anchor ${rawTarget} in README.md`,
      );
      continue;
    }
    const [relFile, hash] = rawTarget.split("#", 2);
    const resolved = path.resolve(REPO_ROOT, relFile);
    assert.ok(
      fs.existsSync(resolved),
      `missing local target ${relFile} linked from README.md`,
    );
    if (hash && resolved.endsWith(".md")) {
      const targetMd = fs.readFileSync(resolved, "utf8");
      const targetSlugs = new Set();
      for (const line of targetMd.split(/\r?\n/u)) {
        const m = line.match(/^ {0,3}#{1,6}\s+(.*?)\s*#*\s*$/u);
        if (m) targetSlugs.add(githubSlug(m[1]));
      }
      assert.ok(
        targetSlugs.has(hash),
        `unresolved anchor #${hash} in ${relFile}`,
      );
    }
  }
});

test("Each standalone character generation.json is linked and retains prompts, and unrecorded Layers provenance stays in README.md", () => {
  const markdown = fs.readFileSync(DEFAULT_README_PATH, "utf8");
  const keys = [
    "demo",
    "scarf",
    "reference-sample",
    "reference-demo",
    "three-quarter",
    "wind",
    "look",
    "rigboy",
  ];

  for (const key of keys) {
    const rel = `${key}/generation.json`;
    assert.ok(
      markdown.includes(`(${rel})`),
      `expected README.md to link to ${rel}`,
    );
    const fullPath = path.join(REPO_ROOT, rel);
    assert.ok(fs.existsSync(fullPath), `expected ${rel} on disk`);
    const record = JSON.parse(fs.readFileSync(fullPath, "utf8"));
    const positive = record?.positive ?? "";
    const negative = record?.negative ?? "";
    assert.ok(
      typeof positive === "string" && positive.length > 40,
      `expected non-empty positive prompt in ${rel}`,
    );
    assert.ok(
      typeof negative === "string" && negative.length > 40,
      `expected non-empty negative prompt in ${rel}`,
    );
  }

  const requiredLayersProvenance = [
    "98d754bf04f668647919ab750eccb0e0640faa81",
    "0.5.0",
    "790x790",
    "370x370",
    "[639, 144, 1009, 514]",
    "1125x1125",
    "[268, 0, 1393, 1125]",
    "269 px",
  ];
  for (const token of requiredLayersProvenance) {
    assert.ok(
      markdown.includes(token),
      `expected unrecorded See-through Layers provenance token ${JSON.stringify(token)} in README.md`,
    );
  }
});

test("rigboy/v2 has at most one index line in README.md pointing to rigboy/v2/README.md", () => {
  const markdown = fs.readFileSync(DEFAULT_README_PATH, "utf8");
  const matchingLines = markdown
    .split(/\r?\n/u)
    .filter((line) => /rigboy\s*\/?\s*v2/iu.test(line));
  assert.equal(
    matchingLines.length,
    1,
    `expected rigboy/v2 on 1 line at most, got ${matchingLines.length}: ${JSON.stringify(matchingLines)}`,
  );
  assert.ok(
    matchingLines[0].includes("rigboy/v2/README.md"),
    "expected rigboy/v2 index line to point at rigboy/v2/README.md",
  );
});

const PLANTED_FAILURES = [
  {
    name: "word-over-cap",
    code: "README_WORD_CAP",
    mutate(base) {
      const extraWords = Array.from(
        { length: README_WORD_CAP - countWords(base) + 5 },
        (_, i) => `filler${i}`,
      ).join(" ");
      return `${base}\n\n${extraWords}\n`;
    },
  },
  {
    name: "unlisted-h2",
    code: "README_HEADING",
    mutate(base) {
      return `${base}\n## Changelog\n\nNot allowed.\n`;
    },
  },
  {
    name: "indented-h2-closing-hashes",
    code: "README_HEADING",
    mutate(base) {
      return `${base}\n   ##Prompts, verbatim   ###\n`;
    },
  },
  {
    name: "empty-h2",
    code: "README_HEADING",
    mutate(base) {
      return `${base}\n##   \n`;
    },
  },
  {
    name: "measured-on-20",
    code: "README_DATED_PHRASE",
    mutate(base) {
      return `${base}\n Throughput was measured on 2026-10-30 on a local runner.\n`;
    },
  },
  {
    name: "read-on-20-wrapped",
    code: "README_DATED_PHRASE",
    mutate(base) {
      return `${base}\n Figures were read\non 2026-10-30 from the candidate sheet.\n`;
    },
  },
  {
    name: "table-cell-date",
    code: "README_TABLE_DATE",
    mutate(base) {
      return `${base}\n| key | date |\n| --- | --- |\n| demo | 2026-10-30 |\n`;
    },
  },
  {
    name: "table-header-date-without-outer-pipes",
    code: "README_TABLE_DATE",
    mutate(base) {
      return `${base}\nkey | 2026-10-30\n--- | ---\ndemo | ok\n`;
    },
  },
];

for (const planted of PLANTED_FAILURES) {
  test(`planted failure refused by name: ${planted.name}`, () => {
    const base = fs.readFileSync(DEFAULT_README_PATH, "utf8");
    const mutated = planted.mutate(base);
    const result = checkReadme(mutated);
    assert.equal(
      result.ok,
      false,
      `expected planted failure ${planted.name} to be refused`,
    );
    assert.ok(
      result.violations.some((v) => v.code === planted.code),
      `expected ${planted.code} in ${JSON.stringify(result.violations)}`,
    );
  });
}

test("CLI exits non-zero when pointed at a planted failure file", () => {
  const base = fs.readFileSync(DEFAULT_README_PATH, "utf8");
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "check-readme-test-"));
  const badPath = path.join(tmpDir, "README.bad.md");
  try {
    fs.writeFileSync(
      badPath,
      `${base}\n## Forbidden heading\n| col | 2026-10-30 |\n`,
      "utf8",
    );
    const cli = spawnSync(process.execPath, [CHECK_SCRIPT_PATH, badPath], {
      cwd: REPO_ROOT,
      encoding: "utf8",
    });
    assert.equal(cli.status, 1);
    assert.match(cli.stderr, /\[README_HEADING\]/u);
    assert.match(cli.stderr, /\[README_TABLE_DATE\]/u);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
