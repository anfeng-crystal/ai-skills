import path from "node:path";
import { loadConfig } from "./config.mjs";

export function parseArgs(argv, defaultConfig = loadConfig()) {
  const parsed = {
    sourceRoot: defaultConfig.sourceRoot,
    home: defaultConfig.home,
    config: defaultConfig,
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
        parsed.sourceRoot = path.resolve(requiredValue(argv, ++i, token));
        break;
      case "--home":
        parsed.home = path.resolve(requiredValue(argv, ++i, token));
        break;
      case "--apply":
        parsed.apply = true;
        break;
      case "--json":
        parsed.json = true;
        break;
      case "--skill":
        parsed.skills.push(...splitValues(requiredValue(argv, ++i, token), token));
        break;
      case "--category":
        parsed.category = requiredValue(argv, ++i, token);
        break;
      case "--name":
        parsed.name = requiredValue(argv, ++i, token);
        break;
      case "--path":
        parsed.path = requiredValue(argv, ++i, token);
        break;
      case "--tool":
      case "--target":
        parsed.tools.push(...splitValues(requiredValue(argv, ++i, token), token));
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
        parsed.last = parseInt(requiredValue(argv, ++i, token), 10) || 10;
        break;
      case "--purge":
        parsed.purge = true;
        break;
      case "-h":
      case "--help":
        parsed.help = true;
        break;
      default:
        if (token.startsWith("--")) {
          // Never discard a mistyped scope or preview flag before executing work.
          throw new Error(`错误：未知参数 ${token.split("=", 1)[0]}，请使用 --help 查看支持的参数。`);
        }
        if (parsed.command === "install" && !parsed.installSource) {
          parsed.installSource = token;
        } else {
          parsed.skills.push(...splitValues(token, "Skill"));
        }
        break;
    }
    i++;
  }

  if (parsed.apply && parsed.dryRun) {
    throw new Error("错误：--dry-run 与 --apply 不能同时使用，请选择预览或执行。");
  }

  if (!parsed.help && !parsed.sourceRoot) {
    throw new Error(
      "错误：无法确定 skills source root，请使用 --source-root <path>、AI_SKILLS_HOME 或配置文件 sourceRoot。",
    );
  }

  return parsed;
}

function requiredValue(argv, index, token) {
  const value = argv[index];
  if (!value || value.startsWith("--")) {
    throw new Error(`错误：${token} 需要指定值`);
  }
  return value;
}

function splitValues(value, label) {
  const values = String(value)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  // An explicit empty selection must not become the omitted-scope default.
  if (values.length === 0) {
    throw new Error(`错误：${label} 需要指定至少一个非空值`);
  }
  return values;
}
