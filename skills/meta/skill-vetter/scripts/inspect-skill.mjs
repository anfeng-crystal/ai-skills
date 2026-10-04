#!/usr/bin/env node

/**
 * 对本地 skill 路径做静态风险审查，输出 allow / review_needed / block 建议。
 */

import path from "node:path";

import { HOST_TARGETS, RULES } from "./risk-rules.mjs";
import { resolveSkillTarget, collectFiles, readScanText, BINARY_EXTENSIONS, AGENT_FILES } from "./scan-files.mjs";
import { redactReportPaths, redactSourceText } from "./redaction.mjs";

main().catch((error) => {
  console.error(redactSourceText(error instanceof Error ? error.message : String(error)));
  process.exit(1);
});

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (!options.path) {
    throw new Error("Usage: node scripts/inspect-skill.mjs --path /absolute/path/to/skill [--json] [--strict]");
  }

  const inputPath = path.resolve(options.path);
  const report = await inspectPath(inputPath);
  printReport(redactReportPaths(report), options.json);

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
      case "--path": {
        const value = argv[++index];
        if (!value || value.startsWith("--")) {
          throw new Error("--path requires a path value");
        }
        parsed.path = value;
        break;
      }
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
  const { files: discoveredFiles, unscanned } = await collectFiles(target.scanRoot);
  // A known entry can remain readable even when its directory cannot be listed.
  // Include it once so both its cached read result and risk evidence are reported.
  const files = [...new Set([
    ...discoveredFiles,
    ...target.skillRoots.map((root) => path.join(root, "SKILL.md")),
  ])].sort();
  const directoryGaps = [...unscanned, ...(target.discoveryGaps || [])];
  const textCache = new Map();
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
      unscannedDirectories: new Set(directoryGaps.map((gap) => gap.filePath)).size,
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

  for (const gap of directoryGaps) {
    addFinding(report, {
      severity: "medium",
      category: "unscanned_content",
      file: relativeFile(target.scanRoot, gap.filePath),
      line: 1,
      match: gap.reason,
      reason: "目录内容或入口发现未完成；需补充审查后才能完成安装前判断。",
    });
  }

  if (target.skillRoots.length > 1) {
    addFinding(report, {
      severity: "medium",
      category: "multiple_skill_roots",
      file: ".",
      line: 1,
      match: redactSourceText(target.skillRoots.map((item) => relativeFile(target.scanRoot, item)).join(", ")),
      reason: "同一输入路径下发现多个 SKILL.md，需要人工确认要安装或审查哪一个宿主 variant。",
    });
    report.manualReview.push("这是一个多宿主 skill bundle；安装前请先确认实际要落到哪个宿主 variant。");
  }

  for (const skillRoot of target.skillRoots) {
    const skillMdPath = path.join(skillRoot, "SKILL.md");
    const result = await readScanText(skillMdPath);
    textCache.set(skillMdPath, result);
    const frontmatter = parseFrontmatter(result.text || "");
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

    const result = textCache.get(filePath) || await readScanText(filePath);
    if (result.reason) {
      report.fileSummary.skippedBinaryOrLarge += 1;
      addFinding(report, {
        severity: "medium",
        category: "unscanned_content",
        file: relative,
        line: 1,
        match: result.reason,
        reason: "内容未扫描；需核对该文件及其真实目标后才能完成安装前审查。",
      });
      continue;
    }

    const text = result.text;
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

function parseFrontmatter(text) {
  const match = text.replace(/\r\n/g, "\n").match(/^---\n([\s\S]*?)\n---/);
  if (!match) {
    return {
      hasFrontmatter: false,
      name: null,
      description: null,
    };
  }

  const body = match[1];
  return {
    hasFrontmatter: true,
    name: readFrontmatterValue(body, "name"),
    description: readFrontmatterValue(body, "description"),
  };
}

function readFrontmatterValue(body, key) {
  // Keep empty fields on their own line: newline whitespace must never supply
  // another field's value. This remains a scalar excerpt, not a YAML parser.
  const raw = body.match(new RegExp(`^[\\t ]*${key}:[\\t ]*([^\\r\\n]*)$`, "m"))?.[1]?.trim();
  if (!raw) return null;
  const quote = raw[0];
  const value = (quote === '"' || quote === "'") && raw.at(-1) === quote
    ? raw.slice(1, -1).trim()
    : raw;
  return value ? redactSourceText(value) : null;
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
  return redactSourceText(line.trim()).slice(0, 160);
}

function relativeFile(root, filePath) {
  return path.relative(root, filePath) || path.basename(filePath);
}
