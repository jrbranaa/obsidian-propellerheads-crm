#!/usr/bin/env node
/*
 * env-build.js — validate client environment files and emit JSON.
 *
 * Unlike Scripts/sr-quickadd.js (a QuickAdd script that runs inside Obsidian),
 * this is a standalone Node CLI. Run it from a terminal / CI / the collector
 * ingest side.
 *
 *   cd Scripts && npm install        # one-time: js-yaml, ajv, ajv-formats
 *   node env-build.js                # validate every environments/<X>/environment.yaml
 *   node env-build.js --code CAH     # just one client
 *   node env-build.js --json         # also write dist/<CODE>.json
 *
 * Scope of this first version: load + schema-validate + referential-integrity
 * check + (optionally) emit dist/<CODE>.json. Collector merge, drift reports,
 * the redacted client projection, and the Obsidian summary refresh are TODO —
 * see "Client Environment Mapping - Design Recommendation.md".
 */

"use strict";

const fs = require("fs");
const path = require("path");

let yaml, Ajv, addFormats;
try {
  yaml = require("js-yaml");
  Ajv = require("ajv");
  addFormats = require("ajv-formats");
} catch (e) {
  console.error(
    "Missing dependencies. Run:  cd Scripts && npm install\n" + e.message,
  );
  process.exit(2);
}

const REPO = path.resolve(__dirname, "..");
const ENVIRONMENTS = path.join(REPO, "environments");
const SCHEMA_PATH = path.join(REPO, "Templates", "environment.schema.json");
const DIST = path.join(REPO, "dist");

const args = process.argv.slice(2);
const only = args.includes("--code") ? args[args.indexOf("--code") + 1] : null;
const emitJson = args.includes("--json");

// --- locate environment files ------------------------------------------------
function findEnvFiles() {
  if (!fs.existsSync(ENVIRONMENTS)) return [];
  return fs
    .readdirSync(ENVIRONMENTS, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => path.join(ENVIRONMENTS, d.name, "environment.yaml"))
    .filter((p) => fs.existsSync(p));
}

// --- referential integrity -------------------------------------------------
// Errors: a ref that MUST resolve to something defined in the file.
// Warnings: a free-text requires/depends_on token that doesn't match an id
//           (allowed — the design uses prose there — but surfaced).
function checkRefs(doc) {
  const errors = [];
  const warnings = [];

  const ids = new Set();
  const add = (arr) => (arr || []).forEach((x) => x && x.id && ids.add(x.id));
  add(doc.devices);
  add(doc.applications);
  add(doc.vendors);
  add(doc.circuits);
  add(doc.sites);
  (doc.network?.subnets || []).forEach((s) => s.id && ids.add(s.id));

  const mustResolve = (val, where) => {
    if (val == null) return;
    if (!ids.has(val)) errors.push(`${where}: "${val}" does not match any id in the file`);
  };
  const shouldResolve = (val, where) => {
    if (val == null) return;
    if (!ids.has(val)) warnings.push(`${where}: "${val}" is not an id (treated as prose)`);
  };

  (doc.devices || []).forEach((d) => {
    if (d.site) mustResolve(d.site, `devices[${d.id}].site`);
    if (d.host) mustResolve(d.host, `devices[${d.id}].host`);
    if (d.vendor) mustResolve(d.vendor, `devices[${d.id}].vendor`);
  });
  (doc.applications || []).forEach((a) => {
    if (a.runs_on) mustResolve(a.runs_on, `applications[${a.id}].runs_on`);
    if (a.vendor) mustResolve(a.vendor, `applications[${a.id}].vendor`);
    (a.depends_on || []).forEach((x, i) => shouldResolve(x, `applications[${a.id}].depends_on[${i}]`));
  });
  (doc.circuits || []).forEach((c) => {
    if (c.vendor) mustResolve(c.vendor, `circuits[${c.id}].vendor`);
  });
  (doc.vendors || []).forEach((v) => {
    (v.supports || []).forEach((x, i) => shouldResolve(x, `vendors[${v.id}].supports[${i}]`));
  });
  (doc.dependencies || []).forEach((dep, di) => {
    (dep.requires || []).forEach((x, i) => shouldResolve(x, `dependencies[${di} "${dep.service}"].requires[${i}]`));
    if (dep.failover) shouldResolve(dep.failover, `dependencies[${di} "${dep.service}"].failover`);
  });

  return { errors, warnings };
}

// --- main --------------------------------------------------------------
const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, "utf8"));
const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);

let files = findEnvFiles();
if (only) files = files.filter((f) => path.basename(path.dirname(f)) === only);

if (files.length === 0) {
  console.error(only ? `No environments/${only}/environment.yaml` : "No environment.yaml files found under environments/.");
  process.exit(1);
}

let hadError = false;
for (const file of files) {
  const rel = path.relative(REPO, file);
  let doc;
  try {
    // JSON_SCHEMA keeps ISO dates as plain strings (default schema turns them
    // into Date objects, which then fail `format: date` string validation).
    doc = yaml.load(fs.readFileSync(file, "utf8"), { schema: yaml.JSON_SCHEMA });
  } catch (e) {
    console.error(`✗ ${rel}\n  YAML parse error: ${e.message}`);
    hadError = true;
    continue;
  }

  const problems = [];
  if (!validate(doc)) {
    for (const err of validate.errors) {
      problems.push(`  schema  ${err.instancePath || "/"} ${err.message}`);
    }
  }
  const { errors, warnings } = checkRefs(doc || {});
  errors.forEach((e) => problems.push(`  ref     ${e}`));

  if (problems.length) {
    hadError = true;
    console.error(`✗ ${rel} (${doc?.code || "?"})`);
    problems.forEach((p) => console.error(p));
  } else {
    console.log(`✓ ${rel} (${doc.code}) — ${(doc.devices || []).length} devices, ${(doc.applications || []).length} apps`);
  }
  warnings.forEach((w) => console.warn(`  warn    ${w}`));

  if (emitJson && doc && doc.code && !problems.length) {
    fs.mkdirSync(DIST, { recursive: true });
    const out = path.join(DIST, `${doc.code}.json`);
    fs.writeFileSync(out, JSON.stringify(doc, null, 2) + "\n");
    console.log(`  wrote   ${path.relative(REPO, out)}`);
  }
}

process.exit(hadError ? 1 : 0);
