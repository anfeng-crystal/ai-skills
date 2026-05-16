import json
import sys
import os
import argparse

def load_sdk():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sdk_path = os.path.join(script_dir, "..", "assets", "sdk.json")
    with open(sdk_path, 'r', encoding='utf-8') as f:
        return json.load(f)

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

def search(sdk, query, limit=10):
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
    args = parser.parse_args()
    
    try:
        sdk = load_sdk()
        print(search(sdk, args.query))
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
