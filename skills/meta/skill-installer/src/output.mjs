export function printOutput(payload, options) {
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

  if (outputPayload.command === "migrate" && outputPayload.migrations) {
    console.log(`Migrate: ${outputPayload.count} found, ${outputPayload.planned} planned, ${outputPayload.blocked} blocked`);
    for (const m of outputPayload.migrations) {
      console.log(
        [m.skillName, m.category, m.status, m.reason, m.targetRelativePath || "-"].join("\t"),
      );
    }
    if (outputPayload.migrationError) {
      const error = outputPayload.migrationError;
      console.log(`Status: ${outputPayload.status}`);
      console.log(`Migration error: ${error.skillName} ${error.phase} ${error.code || "unknown"} ${error.message}`);
      console.log(`Source: ${error.sourcePath}`);
      console.log(`Target: ${error.targetPath}`);
      console.log(`Host sync: ${outputPayload.synced ? "complete" : outputPayload.syncPlan || outputPayload.syncError ? "incomplete" : "not_attempted"}`);
    }
  }

  if (outputPayload.status && !["install", "migrate"].includes(outputPayload.command)) {
    console.log(`Status: ${outputPayload.status}${outputPayload.reason ? ` — ${outputPayload.reason}` : ""}`);
  }
  if (outputPayload.status === "metadata_read_failed") {
    console.log(`Skill: ${outputPayload.skill}`);
    console.log(`Metadata error: ${outputPayload.code}`);
  }
  if (["missing_skill", "invalid_source"].includes(outputPayload.status) && outputPayload.skill) {
    console.log(`Skill: ${outputPayload.skill}`);
    if (outputPayload.code) console.log(`Target error: ${outputPayload.code}`);
  }
  for (const [skill, result] of Object.entries(outputPayload.checkErrors || {})) {
    console.log(`${skill}: ${result.status} — ${result.reason}`);
  }
  if (outputPayload.skills && !Array.isArray(outputPayload.skills)) {
    for (const [skill, result] of Object.entries(outputPayload.skills)) {
      console.log(`${skill}: ${result.status}${result.reason ? ` — ${result.reason}` : ""}`);
    }
  }
  if (outputPayload.syncVerification || outputPayload.syncPlan) {
    console.log("Host verification:");
    for (const record of (outputPayload.syncVerification || outputPayload.syncPlan).records) {
      console.log([record.tool, record.status, record.reason, record.targetPath || "-"].join("\t"));
    }
  }
  if (outputPayload.syncError) {
    console.log(`Host sync error: ${outputPayload.syncError.code || "unknown"} ${outputPayload.syncError.message}`);
  }
  if (outputPayload.installError) {
    const error = outputPayload.installError;
    console.log(`Install error: ${error.phase} ${error.code || "unknown"} ${error.message}`);
    console.log(`Target created: ${outputPayload.targetCreated ?? "unknown"}; exists: ${outputPayload.targetExists ?? "unknown"}`);
    console.log(`Cleanup: ${outputPayload.cleanup.status}`);
    for (const item of outputPayload.cleanup.errors) {
      console.log([item.phase, item.code || "unknown", item.relativePath, item.message].join("\t"));
    }
  }
  if (outputPayload.updateError) {
    const error = outputPayload.updateError;
    console.log(`Update error: ${error.phase} ${error.code || "unknown"} ${error.message}`);
    console.log(`Skill: ${outputPayload.skill}`);
    const states = ["sourceUpdated", "metadataUpdated", "updateHistoryRecorded", "syncHistoryRecorded"];
    console.log(states.map((key) => `${key}=${outputPayload[key] === null ? "unknown" : outputPayload[key] ? "complete" : "not_attempted"}`).join("\t"));
    console.log(`Host sync: ${outputPayload.syncAttempted ? outputPayload.synced ? "complete" : "incomplete" : "not_attempted"}`);
  }
  for (const result of outputPayload.results || []) {
    console.log(`Skill: ${result.skill}`);
    printOutput(result, options);
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
