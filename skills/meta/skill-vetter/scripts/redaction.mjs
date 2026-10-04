// Findings preserve type and file:line. Source values belong in the local file,
// never in the report, including frontmatter and errors containing user input.
const CREDENTIAL_CONTEXT = /\b(?:[\w-]*(?:token|secret|password|passwd|api[_-]?key)|authorization|cookie|set-cookie|session[_-]?id|basic\s+auth|bearer)\b/i;
const URL = /(?:\b[a-z][a-z\d+.-]*:)?\/\/[^\s<>"'`]+/gi;
export const CURL_USER_AUTH = /\bcurl\b[^\n]*\s(?:--user(?:\s+|=)|-u(?=\S|\s+\S))/i;

export function redactSourceText(value) {
  const text = String(value);
  if (CREDENTIAL_CONTEXT.test(text) || CURL_USER_AUTH.test(text)) return "[REDACTED_CREDENTIAL_CONTEXT]";
  return text.replace(URL, "[REDACTED_URL]");
}

function redactPath(value) {
  if (value === null) return null;
  // Retain harmless parent segments, but never publish a credential-bearing name.
  return String(value).replace(URL, "[REDACTED_URL]").split(/([\\/])/).map((part) =>
    CREDENTIAL_CONTEXT.test(part) || CURL_USER_AUTH.test(part) ? "[REDACTED_PATH_SEGMENT]" : part,
  ).join("");
}

function redactLocation(value) {
  const location = value.match(/^(.*):(\d+)$/);
  return location ? `${redactPath(location[1])}:${location[2]}` : redactPath(value);
}

export function redactReportPaths(report) {
  // Keep raw paths for analysis and apply the output boundary equally to JSON/text.
  const result = { ...report };
  for (const key of ["inputPath", "inspectedRoot", "skillRoot"]) result[key] = redactPath(report[key]);
  for (const key of ["skillRoots", "entryFiles", "agentFiles", "binaryArtifacts"]) {
    result[key] = report[key].map(redactPath);
  }
  result.skills = report.skills.map((skill) => ({
    ...skill, root: redactPath(skill.root), relativeRoot: redactPath(skill.relativeRoot),
  }));
  result.findings = report.findings.map((finding) => ({ ...finding, file: redactPath(finding.file) }));
  for (const key of ["networkDbAccess", "filesystemWrites", "destructiveOps", "secretHits", "absolutePathHits", "autoActionHits"]) {
    result[key] = report[key].map(redactLocation);
  }
  return result;
}
