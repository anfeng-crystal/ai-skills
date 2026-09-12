import json
import sys
import argparse
import re
from pathlib import Path


def load_sdk(path=None):
    sdk_path = Path(path).expanduser() if path is not None else Path(__file__).resolve().parent.parent / "assets" / "sdk.json"
    with sdk_path.open('r', encoding='utf-8') as f:
        return json.load(f)


def version_parts(value):
    """Read stated numeric components without inventing a missing patch version."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(?:Cosmic\s+)?[vV]?(\d+(?:\.\d+)*)", value.strip(), re.IGNORECASE)
    return tuple(int(part) for part in match.group(1).split('.')) if match else None


def version_comparison(index_version, target_version):
    if target_version is None or (isinstance(target_version, str) and not target_version.strip()):
        return "target-not-specified"
    indexed, target = version_parts(index_version), version_parts(target_version)
    if indexed is None or target is None:
        return "unknown"
    if any(left != right for left, right in zip(indexed, target)):
        return "different-version"
    if len(indexed) < 3 or len(target) < 3 or len(indexed) != len(target):
        return "incomplete-version"
    return "same-version"


def evidence_header(sdk, target_version=None):
    metadata = sdk.get('metadata', {}) if isinstance(sdk, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
    index_version = metadata.get('version')
    target_label = target_version if target_version is not None and str(target_version).strip() else "not provided"
    lines = [
        "## SDK evidence",
        f"- Index version: {index_version or 'unknown'}",
        f"- Index source: {metadata.get('source_url') or 'unknown'}",
        f"- Index crawl time: {metadata.get('crawl_time') or 'unknown'}",
        f"- Requested target version: {target_label}",
        f"- Version comparison: {version_comparison(index_version, target_version)}",
        "- Project compatibility: unverified",
        "- Evidence scope: index-candidate; not confirmed-project.",
        "A matching index version or a unique result does not prove this API is available in the target project. "
        "Verify candidates against the target project's resolved JARs, same-version documentation or compilation against a classpath matching that target. "
        "An incomplete version (for example 7.0) does not identify a patch release; no method introduction version is inferred.",
    ]
    return "\n".join(lines)


def search(sdk, query, limit=10, target_version=None):
    """Search without filtering other versions, while keeping compatibility unverified."""
    return evidence_header(sdk, target_version) + "\n\n" + _search_results(sdk, query, limit)


def format_class(cls_data):
    lines = []
    lines.append(f"# Class: {cls_data['full_name']}")
    lines.append(f"**Type:** {cls_data['type']}")
    if cls_data.get('comment'):
        lines.append(f"**Description:** {cls_data['comment']}")
    
    if cls_data.get('interfaces'):
        lines.append(f"**Interfaces:** {', '.join(cls_data['interfaces'])}")
    
    lines.append("\n## Methods")
    methods = cls_data.get('methods', [])
    if not methods:
        lines.append("*No public methods found.*")
    else:
        for m in methods:
            params = []
            for name, ptype in zip(m.get('paramNames', []), m.get('paramTypes', [])):
                params.append(f"{ptype} {name}")
            
            sig = f"{m.get('modifiers', '')} {m.get('returnType', 'void')} {m['name']}({', '.join(params)})"
            lines.append(f"### `{m['name']}`")
            lines.append(f"**Signature:** `{sig}`")
            if m.get('comment'):
                lines.append(f"**Comment:** {m['comment']}")
            
            # Extract tags if any
            tags = m.get('tags', [])
            if tags:
                for tag in tags:
                    if tag.get('name') and tag.get('comment'):
                        lines.append(f"- {tag['name']} {tag['comment']}")
            lines.append("")
            
    return "\n".join(lines)

def _search_results(sdk, query, limit=10):
    query = query.lower()
    matches = []
    
    # Priority 1: Exact class name match
    for cls in sdk.get('classes', []):
        if cls['name'].lower() == query or cls['full_name'].lower() == query:
            return format_class(cls)
            
    # Priority 2: Substring in class name
    for cls in sdk.get('classes', []):
        if query in cls['name'].lower() or query in cls['full_name'].lower():
            matches.append(cls)
    
    if len(matches) == 1:
        return format_class(matches[0])
    
    if len(matches) > limit:
        result = [f"Found {len(matches)} matching classes. Please be more specific. Top {limit}:"]
        for m in matches[:limit]:
            result.append(f"- {m['full_name']} ({m.get('comment', 'No description').split('.')[0]})")
        return "\n".join(result)
    
    if matches:
        # If a few matches, show their details or just list them? 
        # User said "detailed", but if there are 5 classes, showing all methods might be too much.
        # Let's show a list first if there are > 1
        result = [f"Found {len(matches)} classes:"]
        for m in matches:
            result.append(f"- {m['full_name']}: {m.get('comment', 'No description').split('.')[0]}")
        return "\n".join(result)

    # Priority 3: Keyword search in comments/methods
    keyword_matches = []
    for cls in sdk.get('classes', []):
        cls_text = (cls.get('comment') or "").lower()
        for m in cls.get('methods', []):
            cls_text += (m.get('name') or "").lower()
            cls_text += (m.get('comment') or "").lower()
        
        if query in cls_text:
            keyword_matches.append(cls)
            
    if len(keyword_matches) > limit:
        result = [f"Found {len(keyword_matches)} classes containing '{query}'. Top {limit}:"]
        for m in keyword_matches[:limit]:
            result.append(f"- {m['full_name']} ({m.get('comment', 'No description').split('.')[0]})")
        return "\n".join(result)
    
    if keyword_matches:
        result = [f"Found '{query}' in {len(keyword_matches)} classes:"]
        for m in keyword_matches:
            result.append(f"- {m['full_name']}")
        return "\n".join(result)

    return f"No results found for '{query}'."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Class name or keyword to search")
    parser.add_argument("--target-version", help="Requested platform version, e.g. 7.0 or 7.0.13; missing patch stays unknown")
    parser.add_argument("--sdk-path", type=Path, help="Path to a user-provided SDK index; defaults to the bundled index")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    sdk = {}
    
    try:
        sdk = load_sdk(args.sdk_path)
        print(search(sdk, args.query, target_version=args.target_version))
    except Exception as e:
        print(evidence_header(sdk, args.target_version))
        print(f"Error: {str(e)}")
        sys.exit(1)
