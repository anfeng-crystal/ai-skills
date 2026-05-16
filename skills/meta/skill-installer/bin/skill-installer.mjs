#!/usr/bin/env node

/**
 * Skill Linker CLI 入口
 * 统一管理多 AI 工具的 skills 目录分发
 */

import { parseArgs } from '../src/cli.mjs';
import { buildPlan, applyPlan, buildRemovePlan, applyRemovePlan } from '../src/sync-links.mjs';
import { checkAllUpdates } from '../src/update-checker.mjs';
import { diffSkill, updateSkill, updateAll } from '../src/updater.mjs';
import { buildInstallPlan, applyInstallPlan } from '../src/install.mjs';
import { queryHistory, appendHistory } from '../src/history.mjs';
import { deleteMeta } from '../src/meta.mjs';
import fs from "node:fs/promises";
import path from "node:path";

const HARD_CONFLICT_STATUSES = new Set([
  "missing_skill",
  "invalid_tool",
  "invalid_source",
  "source_name_collision",
  "needs_external_dir_config",
  "missing_target_root",
  "real_path_conflict",
  "external_symlink_conflict",
  "hermes_local_shadow_conflict",
]);

try {
  const options = parseArgs(process.argv.slice(2));

  if (options.help) {
    printHelp();
    process.exit(0);
  }

  // 处理子命令
  if (options.command === 'history') {
    await handleHistory(options);
    process.exit(0);
  }

  if (options.command === 'diff') {
    await handleDiff(options);
    process.exit(0);
  }

  if (options.command === 'update') {
    await handleUpdate(options);
    process.exit(0);
  }

  if (options.command === 'remove') {
    await handleRemove(options);
    process.exit(0);
  }

  if (options.command === 'install') {
    await handleInstall(options);
    process.exit(0);
  }

  // 处理主命令
  if (options.checkUpdates) {
    await handleCheckUpdates(options);
    process.exit(0);
  }

  // 默认：软链接分发
  await handleSync(options);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}

async function handleSync(options) {
  const plan = await buildPlan(options);
  const hardConflicts = plan.records.filter((record) => HARD_CONFLICT_STATUSES.has(record.status));

  if (options.apply && hardConflicts.length > 0) {
    printOutput(
      {
        ...plan,
        ok: false,
        applied: false,
        summary: {
          ...plan.summary,
          blockedByConflicts: hardConflicts.length,
        },
      },
      options,
    );
    process.exit(2);
  }

  if (options.apply) {
    await applyPlan(plan.records);
  }

  printOutput(
    {
      ...plan,
      ok: hardConflicts.length === 0,
      applied: options.apply,
    },
    options,
  );

  if (hardConflicts.length > 0) {
    process.exitCode = 2;
  }
}

async function handleCheckUpdates(options) {
  const result = await checkAllUpdates(options.sourceRoot, options.skills);
  printOutput(result, options);
}

async function handleDiff(options) {
  if (options.skills.length === 0) {
    console.error("错误：diff 子命令需要指定 --skill");
    process.exit(1);
  }

  for (const skill of options.skills) {
    const result = await diffSkill(options.sourceRoot, skill);
    if (options.json) {
      console.log(JSON.stringify(result, null, 2));
    } else {
      printDiff(result);
    }
  }
}

async function handleUpdate(options) {
  if (options.all) {
    const result = await updateAll(options.sourceRoot, {
      dryRun: options.dryRun,
      sync: options.sync,
    });
    printOutput(result, options);
  } else if (options.skills.length > 0) {
    for (const skill of options.skills) {
      const result = await updateSkill(options.sourceRoot, skill, {
        dryRun: options.dryRun,
        sync: options.sync,
      });
      printOutput(result, options);
    }
  } else {
    console.error("错误：update 子命令需要指定 --skill 或 --all");
    process.exit(1);
  }
}

async function handleHistory(options) {
  const result = await queryHistory({
    skill: options.skills.length === 1 ? options.skills[0] : undefined,
    last: options.last,
  });
  printOutput(result, options);
}

async function handleRemove(options) {
  if (options.skills.length === 0) {
    console.error("错误：remove 子命令需要指定 --skill");
    process.exit(1);
  }

  const plan = await buildRemovePlan(options);
  const hardConflicts = plan.records.filter((record) =>
    record.status === "external_symlink_conflict" || record.status === "real_path_conflict"
  );

  if (options.apply && hardConflicts.length > 0) {
    printOutput(
      {
        ...plan,
        ok: false,
        applied: false,
        summary: {
          ...plan.summary,
          blockedByConflicts: hardConflicts.length,
        },
      },
      options,
    );
    process.exit(2);
  }

  if (options.apply) {
    await applyRemovePlan(plan.records);

    // 记录历史
    for (const skill of options.skills) {
      const removedRecords = plan.records.filter(r =>
        r.status === "removed" && (r.skill === skill || path.basename(r.skill || "") === skill)
      );
      if (removedRecords.length > 0) {
        await appendHistory({
          action: "remove",
          skill,
          removedFrom: removedRecords.map(r => r.tool),
          purge: options.purge,
        });
      }
    }

    // 如果 --purge，删除源目录和元数据
    if (options.purge) {
      for (const skill of options.skills) {
        const skillDir = path.join(options.sourceRoot, skill);
        await deleteMeta(skillDir);
        try {
          await fs.rm(skillDir, { recursive: true, force: true });
        } catch {}
      }
    }
  }

  printOutput(
    {
      ...plan,
      ok: hardConflicts.length === 0,
      applied: options.apply,
      purge: options.purge,
    },
    options,
  );

  if (hardConflicts.length > 0) {
    process.exitCode = 2;
  }
}

async function handleInstall(options) {
  const plan = await buildInstallPlan(options);

  if (options.apply && !plan.ok) {
    printOutput(
      {
        ...plan,
        applied: false,
      },
      options,
    );
    process.exit(2);
  }

  const result = options.apply ? await applyInstallPlan(plan) : plan;
  printOutput(result, options);

  if (!result.ok) {
    process.exitCode = 2;
  }
}

function printDiff(result) {
  if (!result.found) {
    console.log(`\n${result.skill}: 未找到 .skill-meta.json`);
    return;
  }

  if (result.status === 'no_source') {
    console.log(`\n${result.skill}: 未记录来源仓库`);
    return;
  }

  if (result.status === 'up_to_date') {
    console.log(`\n${result.skill}: 已是最新版本`);
    return;
  }

  console.log(`\n${result.skill}:`);
  console.log(`  来源: ${result.source}`);
  console.log(`  本地: ${result.localHash}`);
  console.log(`  远程: ${result.upstreamHash}`);
  if (result.diff) {
    console.log('\n变更:');
    console.log(result.diff);
  }
}

function printOutput(payload, options) {
  const outputPayload = prepareOutputPayload(payload, options);
  if (options.json) {
    console.log(JSON.stringify(outputPayload, null, 2));
    return;
  }

  if (outputPayload.sourceRoot) {
    console.log(`Source root: ${outputPayload.sourceRoot}`);
  }
  if (outputPayload.home) {
    console.log(`Host home: ${outputPayload.home}`);
  }
  if (outputPayload.applied !== undefined) {
    console.log(`Apply mode: ${outputPayload.applied ? "yes" : "no"}`);
  }
  if (outputPayload.purge !== undefined) {
    console.log(`Purge mode: ${outputPayload.purge ? "yes" : "no"}`);
  }
  if (outputPayload.ok !== undefined) {
    console.log(`OK: ${outputPayload.ok ? "yes" : "no"}`);
  }

  if (outputPayload.summary) {
    console.log("Summary:");
    console.log(JSON.stringify(outputPayload.summary, null, 2));
  }

  if (outputPayload.records) {
    console.log("Records:");
    for (const record of outputPayload.records) {
      console.log(
        [
          record.tool,
          record.skill ?? "-",
          record.action,
          record.status,
          record.reason,
          record.targetPath || "-",
        ].join("\t"),
      );
    }
  }

  if (outputPayload.command === "install") {
    console.log("Install:");
    console.log(
      [
        outputPayload.inputType,
        outputPayload.input,
        outputPayload.category || "-",
        outputPayload.skillName || "-",
        outputPayload.status,
        outputPayload.reason,
        outputPayload.targetPath || "-",
      ].join("\t"),
    );
  }

  if (outputPayload.history) {
    console.log("History:");
    for (const record of outputPayload.history) {
      console.log(
        [
          record.timestamp,
          record.action,
          record.skill || "-",
          record.fromHash ? `${record.fromHash} → ${record.toHash}` : "-",
          record.syncedTools ? `synced to ${record.syncedTools.length} tools` : "-",
        ].join("\t"),
      );
    }
  }
}

function prepareOutputPayload(payload, options) {
  if (!payload.records || shouldShowOptionalHosts(options)) {
    return payload;
  }

  const records = payload.records.filter((record) =>
    !(record.status === "optional_host_unavailable" && !record.wouldChange)
  );
  return {
    ...payload,
    records,
    summary: payload.summary ? summarizeRecords(records) : payload.summary,
  };
}

function shouldShowOptionalHosts(options) {
  return options.tools.length > 0;
}

function summarizeRecords(records) {
  return records.reduce(
    (summary, record) => {
      summary.total += 1;
      summary.byAction[record.action] = (summary.byAction[record.action] || 0) + 1;
      summary.byStatus[record.status] = (summary.byStatus[record.status] || 0) + 1;
      if (record.wouldChange) {
        summary.wouldChange += 1;
      }
      return summary;
    },
    { total: 0, wouldChange: 0, byAction: {}, byStatus: {} },
  );
}

function printHelp() {
  console.log(`Skill Linker

Usage:
  skill-installer [options]
  skill-installer remove <skill> [options]
  skill-installer install <local-path-or-git-url> --category <category> [options]
  skill-installer diff <skill> [options]
  skill-installer update <skill|--all> [options]
  skill-installer history [options]

Options:
  --source-root <path>   Source skills root. Defaults to AI_SKILLS_HOME or the current active tree.
  --home <path>          Host home. Defaults to AI_HOST_HOME or $HOME.
  --skill <name>         Skill name or relative path. Can be repeated or comma-separated.
  --tool <name>          codex, claude, junie, agents, or hermes.
  --category <name>      core, automation, kingdee, meta, incoming, or auto.
  --name <name>          Override installed skill directory name.
  --path <subdir>        Use a subdirectory inside a Git source.
  --apply                Apply planned link changes.
  --json                 Print JSON output.
  --check-updates        Check upstream updates.
  --only-updatable       Only show updatable skills.
  --dry-run              Preview update/remove operations.
  --sync                 Sync after update.
  --purge                Remove source directory after unlinking.
  --help                 Show this help.
`);
}
