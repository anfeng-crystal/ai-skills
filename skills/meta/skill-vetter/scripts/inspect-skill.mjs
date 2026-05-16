#!/usr/bin/env node

/**
 * 对本地 skill 路径做静态风险审查，输出 allow / review_needed / block 建议。
 */

import fs from "node:fs/promises";
import path from "node:path";

const MAX_SKILL_DEPTH = 4;
const MAX_SCAN_BYTES = 256 * 1024;
const IGNORED_DIRS = new Set([
  ".git",
  ".svn",
  ".hg",
  "node_modules",
  "dist",
  "build",
  "__pycache__",
  ".idea",
  ".vscode",
]);
const TEXT_EXTENSIONS = new Set([
  ".md",
  ".txt",
  ".json",
  ".yaml",
  ".yml",
  ".toml",
  ".ini",
  ".sh",
  ".bash",
  ".zsh",
  ".py",
  ".js",
  ".mjs",
  ".cjs",
  ".ts",
  ".tsx",
  ".bat",
  ".ps1",
]);
const BINARY_EXTENSIONS = new Set([
  ".jar",
  ".db",
  ".sqlite",
  ".class",
  ".pyc",
  ".zip",
  ".exe",
  ".dll",
  ".so",
  ".dylib",
]);
const AGENT_FILES = new Set(["AGENTS.md", "CLAUDE.md", "openai.yaml", "plugin.json"]);
const HOST_TARGETS = [
  { name: "codex", pattern: /(?:\/|~\/|\$HOME\/)\.codex\/skills|CODEX_HOME/i },
  { name: "claude", pattern: /(?:\/|~\/|\$HOME\/)\.claude\/skills|CLAUDE\.md/i },
  { name: "agents", pattern: /(?:\/|~\/|\$HOME\/)\.agents\/skills|AGENTS\.md/i },
  { name: "junie", pattern: /(?:\/|~\/|\$HOME\/)\.junie\/skills/i },
];
const RULES = [
  {
    id: "destructive_rm",
    severity: "critical",
    category: "destructive_command",
    reason: "发现 rm -rf，存在强删除风险。",
    regex: /\brm\s+-rf\b/,
  },
  {
    id: "git_hard_reset",
    severity: "critical",
    category: "destructive_command",
    reason: "发现 git 强制回滚命令，可能覆盖用户现有改动。",
    regex: /\bgit\s+reset\s+--hard\b|\bgit\s+checkout\s+--\b/,
  },
  {
    id: "remote_pipe_shell",
    severity: "critical",
    category: "remote_bootstrap",
    reason: "发现远程脚本直接管道执行模式，需要强人工复核。",
    regex: /\b(?:curl|wget)\b[^\n|]*\|\s*(?:sh|bash)\b|\bbash\s*<\(\s*(?:curl|wget)\b/,
  },
  {
    id: "host_path_write",
    severity: "high",
    category: "host_integration",
    reason: "发现宿主 skills 目录写入或覆盖痕迹。",
    regex: /(?:\/|~\/|\$HOME\/)\.(?:codex|claude|agents|junie)\/skills|CODEX_HOME|\.claude\/skills|\.agents\/skills|\.junie\/skills/,
  },
  {
    id: "symlink_ops",
    severity: "high",
    category: "symlink_or_copy",
    reason: "发现软链接或链接重写操作，需要人工确认是否覆盖现有链接。",
    regex: /\bln\s+-s(?:[A-Za-z]*)\b|\bmklink\b|symlink\(/,
  },
  {
    id: "force_copy_move",
    severity: "high",
    category: "symlink_or_copy",
    reason: "发现复制、移动或替换目录行为，需要确认是否影响宿主目录。",
    regex: /\bcp\s+-R\b|\bcp\s+-r\b|\bmv\b|copy_dir_contents|copy_file_to_root/,
  },
  {
    id: "install_commands",
    severity: "medium",
    category: "install_or_bootstrap",
    reason: "发现安装或拉取依赖命令，需要确认运行前提和副作用。",
    regex: /\b(?:npm|pnpm|yarn|pip|pip3|uv|brew|apt|apt-get|cargo|go)\s+install\b|\buv\s+tool\s+install\b|\bgit\s+clone\b/,
  },
  {
    id: "network_fetch",
    severity: "medium",
    category: "network_access",
    reason: "发现主动联网获取资源或远程接口调用。",
    regex: /\b(?:curl|wget)\b|fetch\(|requests\.(?:get|post)|axios\./i,
  },
  {
    id: "database_access",
    severity: "medium",
    category: "database_access",
    reason: "发现数据库访问或连接痕迹，需要确认数据来源和权限边界。",
    regex: /sqlite3\.connect|psycopg|postgres(?:ql)?|jdbc:|create_engine\(|mysql/i,
  },
  {
    id: "exec_apis",
    severity: "high",
    category: "system_execution",
    reason: "发现系统命令执行接口，需要人工复核真实执行面。",
    regex: /child_process\.(?:exec|execSync|spawn|spawnSync)|subprocess\.(?:run|Popen)|os\.system\(|shell=True/,
  },
  {
    id: "eval_like",
    severity: "medium",
    category: "dynamic_execution",
    reason: "发现动态执行模式，需确认是否会放大脚本风险。",
    regex: /\beval\s*\(|new Function\s*\(/,
  },
  {
    id: "secrets_or_auth",
    severity: "medium",
    category: "secrets_or_auth",
    reason: "发现 Token、API Key、密码或 Basic Auth 提示。",
    regex: /\b(?:OPENAI_API_KEY|GITHUB_TOKEN|GH_TOKEN|API_KEY|AUTH_TOKEN|password=|Basic Auth)\b/i,
  },
  {
    id: "absolute_user_path",
    severity: "medium",
    category: "hardcoded_path",
    reason: "发现用户目录或绝对路径硬编码，兼容性和安全边界都需要确认。",
    regex: /\/Users\/[^/\s]+|[A-Z]:\\Users\\|~\/\./,
  },
  {
    id: "auto_action",
    severity: "high",
    category: "auto_action",
    reason: "发现默认自动执行、自动修复或自动写回倾向，需要人工确认是否越权。",
    regex: /ALWAYS TRIGGER|自动触发|自动修复|自动写回|第一个动作.*执行脚本|必须直接执行脚本/i,
  },
];

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (!options.path) {
    throw new Error("Usage: node scripts/inspect-skill.mjs --path /absolute/path/to/skill [--json] [--strict]");
  }

  const inputPath = path.resolve(options.path);
  const report = await inspectPath(inputPath);
  printReport(report, options.json);

  if (options.strict && report.recommendation !== "allow") {
    process.exitCode = 2;
  }
}

function parseArgs(argv) {
  const parsed = {
    path: null,
    json: false,
    strict: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    switch (token) {
      case "--path":
        parsed.path = argv[++index];
        break;
      case "--json":
        parsed.json = true;
        break;
      case "--strict":
        parsed.strict = true;
        break;
      default:
        if (!token.startsWith("--") && !parsed.path) {
          parsed.path = token;
        } else {
          throw new Error(`Unknown argument: ${token}`);
        }
        break;
    }
  }

  return parsed;
}

async function inspectPath(inputPath) {
  const target = await resolveSkillTarget(inputPath);
  const files = await collectFiles(target.scanRoot);
  const report = {
    scannedAt: new Date().toISOString(),
    inputPath,
    inspectedRoot: target.scanRoot,
    skillRoot: target.skillRoots.length === 1 ? target.skillRoots[0] : null,
    skillRoots: target.skillRoots,
    frontmatter: {
      hasFrontmatter: false,
      name: null,
      description: null,
    },
    skills: [],
    entryFiles: [],
    agentFiles: [],
    binaryArtifacts: [],
    fileSummary: {
      totalFiles: files.length,
      textScanned: 0,
      scriptFiles: 0,
      installScripts: 0,
      readmeFiles: 0,
      skippedBinaryOrLarge: 0,
    },
    hostTargetsDetected: [],
    findings: [],
    manualReview: [],
    recommendation: "allow",
    rationale: [],
    networkDbAccess: [],
    filesystemWrites: [],
    destructiveOps: [],
    secretHits: [],
    absolutePathHits: [],
    autoActionHits: [],
  };

  if (target.skillRoots.length > 1) {
    addFinding(report, {
      severity: "medium",
      category: "multiple_skill_roots",
      file: ".",
      line: 1,
      match: target.skillRoots.map((item) => relativeFile(target.scanRoot, item)).join(", "),
      reason: "同一输入路径下发现多个 SKILL.md，需要人工确认要安装或审查哪一个宿主 variant。",
    });
    report.manualReview.push("这是一个多宿主 skill bundle；安装前请先确认实际要落到哪个宿主 variant。");
  }

  for (const skillRoot of target.skillRoots) {
    const skillMdPath = path.join(skillRoot, "SKILL.md");
    const skillMdText = await fs.readFile(skillMdPath, "utf8");
    const frontmatter = parseFrontmatter(skillMdText);
    report.skills.push({
      root: skillRoot,
      relativeRoot: relativeFile(target.scanRoot, skillRoot),
      frontmatter,
    });
    report.entryFiles.push(relativeFile(target.scanRoot, skillMdPath));

    if (target.skillRoots.length === 1) {
      report.frontmatter = frontmatter;
    }

    if (!frontmatter.hasFrontmatter) {
      addFinding(report, {
        severity: "medium",
        category: "skill_structure",
        file: relativeFile(target.scanRoot, skillMdPath),
        line: 1,
        match: "SKILL.md",
        reason: "缺少 YAML frontmatter，触发质量和安装识别都需要人工确认。",
      });
      continue;
    }

    if (!frontmatter.name) {
      addFinding(report, {
        severity: "medium",
        category: "skill_structure",
        file: relativeFile(target.scanRoot, skillMdPath),
        line: 1,
        match: "name",
        reason: "frontmatter 缺少 name。",
      });
    }
    if (!frontmatter.description) {
      addFinding(report, {
        severity: "medium",
        category: "skill_structure",
        file: relativeFile(target.scanRoot, skillMdPath),
        line: 1,
        match: "description",
        reason: "frontmatter 缺少 description。",
      });
    }
  }

  for (const filePath of files) {
    const relative = relativeFile(target.scanRoot, filePath);
    const ext = path.extname(filePath).toLowerCase();
    const base = path.basename(filePath).toLowerCase();

    if (base === "readme.md") {
      report.fileSummary.readmeFiles += 1;
    }
    if (AGENT_FILES.has(path.basename(filePath))) {
      report.agentFiles.push(relative);
    }
    if (BINARY_EXTENSIONS.has(ext)) {
      report.binaryArtifacts.push(relative);
    }
    if (isScriptLike(filePath)) {
      report.fileSummary.scriptFiles += 1;
    }
    if (base === "install.sh" || base.startsWith("setup-") || relative.includes("/setup/")) {
      report.fileSummary.installScripts += 1;
    }

    if (!TEXT_EXTENSIONS.has(ext) && base !== "SKILL.md") {
      report.fileSummary.skippedBinaryOrLarge += 1;
      continue;
    }

    const stat = await fs.stat(filePath);
    if (stat.size > MAX_SCAN_BYTES) {
      report.fileSummary.skippedBinaryOrLarge += 1;
      continue;
    }

    const text = await fs.readFile(filePath, "utf8");
    report.fileSummary.textScanned += 1;
    recordHostTargets(report, text);
    scanText(report, relative, text);
  }

  if (report.fileSummary.installScripts > 0) {
    report.manualReview.push("包含 install/setup 脚本；请人工复核安装步骤和宿主目录影响。");
  }
  if (report.fileSummary.readmeFiles > 0) {
    report.manualReview.push("存在 README 或额外说明文档；请确认是否包含安装副作用或环境假设。");
  }
  if (report.hostTargetsDetected.length > 0) {
    report.manualReview.push(`检测到宿主集成痕迹：${report.hostTargetsDetected.join(", ")}。`);
  }

  finalizeRecommendation(report);
  return report;
}

async function resolveSkillRoot(inputPath) {
  const stat = await fs.stat(inputPath).catch(() => null);
  if (!stat) {
    throw new Error(`Path not found: ${inputPath}`);
  }

  if (stat.isFile()) {
    if (path.basename(inputPath) !== "SKILL.md") {
      throw new Error(`Expected a skill directory or SKILL.md, got file: ${inputPath}`);
    }
    return path.dirname(inputPath);
  }

  const directSkill = path.join(inputPath, "SKILL.md");
  if (await existsFile(directSkill)) {
    return inputPath;
  }

  const skillRoots = [];
  await searchSkillRoots(inputPath, 0, skillRoots);

  if (skillRoots.length === 1) {
    return skillRoots[0];
  }
  if (skillRoots.length === 0) {
    throw new Error(`No SKILL.md found under: ${inputPath}`);
  }
  throw new Error(`Multiple skill roots found under ${inputPath}; pass a narrower path.`);
}

async function resolveSkillTarget(inputPath) {
  const stat = await fs.stat(inputPath).catch(() => null);
  if (!stat) {
    throw new Error(`Path not found: ${inputPath}`);
  }

  if (stat.isFile()) {
    if (path.basename(inputPath) !== "SKILL.md") {
      throw new Error(`Expected a skill directory or SKILL.md, got file: ${inputPath}`);
    }
    return {
      scanRoot: path.dirname(inputPath),
      skillRoots: [path.dirname(inputPath)],
    };
  }

  const directSkill = path.join(inputPath, "SKILL.md");
  if (await existsFile(directSkill)) {
    return {
      scanRoot: inputPath,
      skillRoots: [inputPath],
    };
  }

  const skillRoots = [];
  await searchSkillRoots(inputPath, 0, skillRoots);

  if (skillRoots.length === 0) {
    throw new Error(`No SKILL.md found under: ${inputPath}`);
  }

  return {
    scanRoot: inputPath,
    skillRoots: skillRoots.sort(),
  };
}

async function searchSkillRoots(dirPath, depth, skillRoots) {
  if (depth > MAX_SKILL_DEPTH) {
    return;
  }

  const entries = await fs.readdir(dirPath, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory() || IGNORED_DIRS.has(entry.name)) {
      continue;
    }
    const child = path.join(dirPath, entry.name);
    if (await existsFile(path.join(child, "SKILL.md"))) {
      skillRoots.push(child);
      continue;
    }
    await searchSkillRoots(child, depth + 1, skillRoots);
  }
}

async function collectFiles(root) {
  const collected = [];
  await walk(root, collected);
  return collected.sort();
}

async function walk(dirPath, collected) {
  const entries = await fs.readdir(dirPath, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (IGNORED_DIRS.has(entry.name)) {
        continue;
      }
      await walk(path.join(dirPath, entry.name), collected);
      continue;
    }
    collected.push(path.join(dirPath, entry.name));
  }
}

function parseFrontmatter(text) {
  const match = text.match(/^---\n([\s\S]*?)\n---/);
  if (!match) {
    return {
      hasFrontmatter: false,
      name: null,
      description: null,
    };
  }

  const body = match[1];
  const name = body.match(/^\s*name:\s*["']?(.+?)["']?\s*$/m)?.[1] ?? null;
  const description = body.match(/^\s*description:\s*["']?([\s\S]+?)["']?\s*$/m)?.[1] ?? null;
  return {
    hasFrontmatter: true,
    name,
    description,
  };
}

function scanText(report, relative, text) {
  const lines = text.split(/\r?\n/);
  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];
    for (const rule of RULES) {
      if (rule.id === "auto_action" && !shouldCheckAutoAction(relative)) {
        continue;
      }
      if (!rule.regex.test(line)) {
        continue;
      }
      addFinding(report, {
        severity: rule.severity,
        category: rule.category,
        file: relative,
        line: lineIndex + 1,
        match: trimExcerpt(line),
        reason: rule.reason,
      });
    }
  }

  const lowerRelative = relative.toLowerCase();
  if (isTopLevelReadme(lowerRelative)) {
    addFinding(report, {
      severity: "low",
      category: "extra_docs",
      file: relative,
      line: 1,
      match: "README.md",
      reason: "存在 README；请确认是否混入额外安装流程或宿主假设。",
    });
  }
}

function recordHostTargets(report, text) {
  for (const target of HOST_TARGETS) {
    if (target.pattern.test(text) && !report.hostTargetsDetected.includes(target.name)) {
      report.hostTargetsDetected.push(target.name);
    }
  }
}

function addFinding(report, finding) {
  const dedupeKey = `${finding.category}:${finding.file}:${finding.line}:${finding.match}`;
  if (report.findings.some((item) => item.dedupeKey === dedupeKey)) {
    return;
  }
  report.findings.push({
    ...finding,
    dedupeKey,
  });
}

function finalizeRecommendation(report) {
  const severities = report.findings.map((finding) => finding.severity);
  const hasCritical = severities.includes("critical");
  const hasHigh = severities.includes("high");
  const hasMedium = severities.includes("medium");

  if (hasCritical) {
    report.recommendation = "block";
    report.rationale.push("发现 critical 风险，默认不建议继续安装或分发。");
  } else if (hasHigh || hasMedium) {
    report.recommendation = "review_needed";
    report.rationale.push("存在中高风险项，需人工复核后再决定。");
  } else {
    report.recommendation = "allow";
    report.rationale.push("未发现阻断性静态风险，可进入后续安装或分发流程。");
  }

  report.findings = report.findings
    .map(({ dedupeKey, ...finding }) => finding)
    .sort(compareFindings);
  report.manualReview = Array.from(new Set(report.manualReview));
  report.entryFiles = Array.from(new Set(report.entryFiles)).sort();
  report.agentFiles = Array.from(new Set(report.agentFiles)).sort();
  report.binaryArtifacts = Array.from(new Set(report.binaryArtifacts)).sort();
  report.networkDbAccess = uniqueFindingsByCategory(report.findings, ["network_access", "database_access"]);
  report.filesystemWrites = uniqueFindingsByCategory(report.findings, ["host_integration", "symlink_or_copy"]);
  report.destructiveOps = uniqueFindingsByCategory(report.findings, ["destructive_command", "remote_bootstrap"]);
  report.secretHits = uniqueFindingsByCategory(report.findings, ["secrets_or_auth"]);
  report.absolutePathHits = uniqueFindingsByCategory(report.findings, ["hardcoded_path"]);
  report.autoActionHits = uniqueFindingsByCategory(report.findings, ["auto_action"]);
}

function compareFindings(left, right) {
  const order = { critical: 0, high: 1, medium: 2, low: 3 };
  return (
    order[left.severity] - order[right.severity] ||
    left.file.localeCompare(right.file) ||
    left.line - right.line
  );
}

function printReport(report, json) {
  if (json) {
    console.log(JSON.stringify(report, null, 2));
    return;
  }

  console.log(`Recommendation: ${report.recommendation}`);
  console.log(`Inspected root: ${report.inspectedRoot}`);
  console.log(`Skill root: ${report.skillRoot || "(multiple)"}`);
  console.log(`Skill name: ${report.frontmatter.name || "(missing)"}`);
  console.log(`Host targets: ${report.hostTargetsDetected.join(", ") || "none"}`);
  console.log(`Entry files: ${report.entryFiles.join(", ") || "none"}`);
  console.log(`Agent files: ${report.agentFiles.join(", ") || "none"}`);
  console.log(`Binary artifacts: ${report.binaryArtifacts.join(", ") || "none"}`);
  console.log("Summary:");
  console.log(JSON.stringify(report.fileSummary, null, 2));

  if (report.findings.length === 0) {
    console.log("Findings: none");
  } else {
    console.log("Findings:");
    for (const finding of report.findings) {
      console.log(
        `- [${finding.severity}] ${finding.category} ${finding.file}:${finding.line} -> ${finding.reason}`,
      );
    }
  }

  if (report.manualReview.length > 0) {
    console.log("Manual review:");
    for (const item of report.manualReview) {
      console.log(`- ${item}`);
    }
  }

  if (report.rationale.length > 0) {
    console.log("Rationale:");
    for (const item of report.rationale) {
      console.log(`- ${item}`);
    }
  }
}

function isScriptLike(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const base = path.basename(filePath).toLowerCase();
  return [".sh", ".bash", ".zsh", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".bat", ".ps1"].includes(ext) ||
    base === "install.sh";
}

function uniqueFindingsByCategory(findings, categories) {
  return findings
    .filter((finding) => categories.includes(finding.category))
    .map((finding) => `${finding.file}:${finding.line}`)
    .filter((value, index, array) => array.indexOf(value) === index);
}

function shouldCheckAutoAction(relative) {
  const normalized = relative.replace(/\\/g, "/");
  const basename = path.basename(normalized);
  return (
    basename === "SKILL.md" ||
    basename === "AGENTS.md" ||
    basename === "CLAUDE.md" ||
    basename === "openai.yaml" ||
    basename === "install.sh" ||
    normalized === "README.md" ||
    /^[^/]+\/README\.md$/i.test(normalized)
  );
}

function isTopLevelReadme(relative) {
  return relative === "readme.md" || /^[^/]+\/readme\.md$/i.test(relative);
}

function trimExcerpt(line) {
  return line.trim().slice(0, 160);
}

function relativeFile(root, filePath) {
  return path.relative(root, filePath) || path.basename(filePath);
}

async function existsFile(filePath) {
  try {
    const stat = await fs.stat(filePath);
    return stat.isFile();
  } catch {
    return false;
  }
}
