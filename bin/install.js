#!/usr/bin/env node

const fs = require("fs");
const os = require("os");
const path = require("path");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const BEGIN_MARKER = "<!-- BEGIN memory-state-codex -->";
const END_MARKER = "<!-- END memory-state-codex -->";

function printHelp() {
  console.log(`memory-state-codex installer

Usage:
  npx memory-state-codex [options]

Options:
  --plus                 Install PLUS mode with mandatory session/message logging.
  --codex-home <path>    Install into this Codex home instead of CODEX_HOME or ~/.codex.
  --force-db             Replace an existing memories/memory_state.db template.
  --replace-agents       Replace the entire AGENTS.md file instead of managing a block.
  --dry-run              Show what would change without writing files.
  -h, --help             Show this help.
`);
}

function parseArgs(argv) {
  const options = {
    codexHome: null,
    dryRun: false,
    forceDb: false,
    plus: false,
    replaceAgents: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "-h" || arg === "--help") {
      options.help = true;
    } else if (arg === "--dry-run") {
      options.dryRun = true;
    } else if (arg === "--force-db") {
      options.forceDb = true;
    } else if (arg === "--plus") {
      options.plus = true;
    } else if (arg === "--replace-agents") {
      options.replaceAgents = true;
    } else if (arg === "--codex-home") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("--codex-home requires a path");
      }
      options.codexHome = value;
      index += 1;
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  return options;
}

function resolveCodexHome(options) {
  const configured = options.codexHome || process.env.CODEX_HOME;
  return path.resolve(configured || path.join(os.homedir(), ".codex"));
}

function codexConfig(options) {
  return {
    name: "codex",
    label: "Codex",
    home: resolveCodexHome(options),
    profileFile: options.plus ? "AGENTS-PLUS.md" : "AGENTS-LITE.md",
    targetProfile: "AGENTS.md",
    skillSourceDir: "skills-codex",
  };
}

function ensureDir(dir, dryRun) {
  if (dryRun) {
    console.log(`[dry-run] mkdir -p ${dir}`);
    return;
  }
  fs.mkdirSync(dir, { recursive: true });
}

function copyRecursive(source, destination, dryRun) {
  if (dryRun) {
    console.log(`[dry-run] copy ${source} -> ${destination}`);
    return;
  }

  const stat = fs.statSync(source);
  if (stat.isDirectory()) {
    fs.mkdirSync(destination, { recursive: true });
    for (const entry of fs.readdirSync(source)) {
      copyRecursive(path.join(source, entry), path.join(destination, entry), false);
    }
    return;
  }

  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.copyFileSync(source, destination);
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function backupFile(file, dryRun) {
  if (!fs.existsSync(file)) {
    return null;
  }
  const backup = `${file}.bak-${timestamp()}`;
  if (dryRun) {
    console.log(`[dry-run] backup ${file} -> ${backup}`);
    return backup;
  }
  fs.copyFileSync(file, backup);
  return backup;
}

function managedBlock(sourceText) {
  return `${BEGIN_MARKER}
${sourceText.trim()}
${END_MARKER}
`;
}

function mergeAgents(existing, block) {
  const begin = existing.indexOf(BEGIN_MARKER);
  const end = existing.indexOf(END_MARKER);

  if (begin !== -1 && end !== -1 && end > begin) {
    const afterEnd = end + END_MARKER.length;
    return `${existing.slice(0, begin)}${block}${existing.slice(afterEnd).replace(/^\s*/, "\n")}`.trimEnd() + "\n";
  }

  const separator = existing.trim().length > 0 ? "\n\n" : "";
  return `${existing.trimEnd()}${separator}${block}`;
}

function installProfile(provider, options) {
  const source = path.join(PACKAGE_ROOT, provider.profileFile);
  const target = path.join(provider.home, provider.targetProfile);
  const sourceText = fs.readFileSync(source, "utf8");
  const nextText = options.replaceAgents
    ? `${sourceText.trimEnd()}\n`
    : mergeAgents(fs.existsSync(target) ? fs.readFileSync(target, "utf8") : "", managedBlock(sourceText));

  if (fs.existsSync(target) && fs.readFileSync(target, "utf8") === nextText) {
    console.log(`${provider.targetProfile} already up to date: ${target}`);
    return;
  }

  ensureDir(path.dirname(target), options.dryRun);
  const backup = fs.existsSync(target) ? backupFile(target, options.dryRun) : null;
  if (options.dryRun) {
    console.log(`[dry-run] write ${target}`);
  } else {
    fs.writeFileSync(target, nextText, "utf8");
  }
  console.log(`Installed ${provider.targetProfile} instructions: ${target}`);
  if (backup) {
    console.log(`Backup created: ${backup}`);
  }
}

function installSkill(provider, options) {
  const skillName = options.plus ? "curated-memory-plus" : "curated-memory";
  const source = path.join(PACKAGE_ROOT, provider.skillSourceDir, skillName);
  const target = path.join(provider.home, "skills", skillName);

  ensureDir(path.dirname(target), options.dryRun);
  copyRecursive(source, target, options.dryRun);
  console.log(`Installed ${provider.label} ${skillName} skill: ${target}`);
}

function installMemoryTemplate(provider, options) {
  const source = path.join(PACKAGE_ROOT, "memories", "memory_state.db");
  const target = path.join(provider.home, "memories", "memory_state.db");

  ensureDir(path.dirname(target), options.dryRun);
  if (fs.existsSync(target) && !options.forceDb) {
    console.log(`Memory database already exists, left untouched: ${target}`);
    return;
  }

  if (fs.existsSync(target)) {
    const backup = backupFile(target, options.dryRun);
    if (backup) {
      console.log(`Existing memory database backup created: ${backup}`);
    }
  }
  copyRecursive(source, target, options.dryRun);
  console.log(`Installed empty memory database template: ${target}`);
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }

  console.log(`Mode: ${options.plus ? "PLUS" : "LITE"}`);

  const provider = codexConfig(options);
  console.log("");
  console.log(`${provider.label} home: ${provider.home}`);
  ensureDir(provider.home, options.dryRun);
  installProfile(provider, options);
  installSkill(provider, options);
  installMemoryTemplate(provider, options);

  const skillName = options.plus ? "curated-memory-plus" : "curated-memory";
  const memoryScript = path.join(provider.home, "skills", skillName, "scripts", "memory.py");
  console.log("");
  console.log("Done.");
  console.log(`${provider.label} initialize or repair schema: python "${memoryScript}" init`);
  console.log(`${provider.label} inspect memory store:       python "${memoryScript}" inspect`);
}

try {
  main();
} catch (error) {
  console.error(`memory-state-codex install failed: ${error.message}`);
  process.exitCode = 1;
}
