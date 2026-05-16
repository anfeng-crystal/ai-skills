import path from "node:path";
import { loadConfig } from "./config.mjs";

const DEFAULT_CONFIG = loadConfig();

export function parseArgs(argv) {
  const parsed = {
    sourceRoot: DEFAULT_CONFIG.sourceRoot,
    home: DEFAULT_CONFIG.home,
    config: DEFAULT_CONFIG,
    apply: false,
    json: false,
    skills: [],
    tools: [],
    command: null,
    checkUpdates: false,
    onlyUpdatable: false,
    all: false,
    dryRun: false,
    sync: false,
    last: 10,
    purge: false,
    help: false,
    installSource: null,
    category: null,
    name: null,
    path: null,
  };

  let i = 0;
  while (i < argv.length) {
    const token = argv[i];

    // 子命令
    if (token === 'history' || token === 'diff' || token === 'update' || token === 'remove' || token === 'install' || token === 'migrate') {
      parsed.command = token;
      i++;
      continue;
    }

    switch (token) {
      case "--source-root":
        parsed.sourceRoot = path.resolve(argv[++i]);
        break;
      case "--home":
        parsed.home = path.resolve(argv[++i]);
        break;
      case "--apply":
        parsed.apply = true;
        break;
      case "--json":
        parsed.json = true;
        break;
      case "--skill":
        parsed.skills.push(...splitValues(argv[++i]));
        break;
      case "--category":
        parsed.category = argv[++i];
        break;
      case "--name":
        parsed.name = argv[++i];
        break;
      case "--path":
        parsed.path = argv[++i];
        break;
      case "--tool":
      case "--target":
        parsed.tools.push(...splitValues(argv[++i]));
        break;
      case "--check-updates":
        parsed.checkUpdates = true;
        break;
      case "--only-updatable":
        parsed.onlyUpdatable = true;
        break;
      case "--all":
        parsed.all = true;
        break;
      case "--dry-run":
        parsed.dryRun = true;
        break;
      case "--sync":
        parsed.sync = true;
        break;
      case "--last":
        parsed.last = parseInt(argv[++i], 10) || 10;
        break;
      case "--purge":
        parsed.purge = true;
        break;
      case "-h":
      case "--help":
        parsed.help = true;
        break;
      default:
        if (!token.startsWith("--")) {
          if (parsed.command === "install" && !parsed.installSource) {
            parsed.installSource = token;
          } else {
            parsed.skills.push(...splitValues(token));
          }
        }
        break;
    }
    i++;
  }

  return parsed;
}

function splitValues(value) {
  return String(value)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
