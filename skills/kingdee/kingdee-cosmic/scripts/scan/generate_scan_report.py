#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描结果报告生成工具。

读取合并后的 scan_java_result.json，按等级分组、路径排序，生成 Markdown 报告；
结果较多或显式要求时，同时生成本地 HTML dashboard 供审核。
"""

import argparse
import datetime
import html
import json
from pathlib import Path
from collections import defaultdict

# 脚本所在目录
SCRIPT_DIR = Path(__file__).parent.resolve()
# active skills 根目录
ACTIVE_ROOT = SCRIPT_DIR.parents[4]
# 结果目录
RESULT_DIR = SCRIPT_DIR.parent / "result"

# 等级排序权重（从高到低）
LEVEL_PRIORITY = {
    "严重": 1,
    "高危": 2,
    "中危": 3,
    "低危": 4
}
ORDERED_LEVELS = ["严重", "高危", "中危", "低危"]


def load_scan_result(result_file=None):
    """加载合并后的扫描结果"""
    result_file = Path(result_file).resolve() if result_file else RESULT_DIR / "scan_java_result.json"
    
    if not result_file.exists():
        print(f"错误: 找不到结果文件 {result_file}")
        return None
    
    with open(result_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def group_by_level(data):
    """按等级分组"""
    groups = defaultdict(list)
    for item in data:
        level = item.get("rule_level", "未知")
        groups[level].append(item)
    return groups


def sort_by_path(items):
    """按文件路径排序"""
    return sorted(items, key=lambda x: x.get("file_path", ""))


def esc(value):
    """HTML escape，避免扫描结果内容破坏 dashboard 结构。"""
    return html.escape(str(value if value is not None else "N/A"), quote=True)


def generate_markdown_report(groups):
    """生成 Markdown 报告"""
    lines = []

    # 标题
    lines.append("# Java 代码扫描结果报告")
    lines.append("")
    lines.append(f"**生成时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 统计摘要
    total_count = sum(len(items) for items in groups.values())
    # 计算违规文件数（去重）
    all_file_paths = set()
    for items in groups.values():
        for item in items:
            all_file_paths.add(item.get('file_path', ''))
    total_files = len(all_file_paths)

    lines.append("## 统计摘要")
    lines.append("")
    lines.append(f"- **总违规数**: {total_count}")
    lines.append(f"- **违规文件数**: {total_files}")
    lines.append("")
    lines.append("| 等级 | 违规数 | 违规文件数 |")
    lines.append("|------|--------|------------|")

    # 按等级优先级排序
    for level in ORDERED_LEVELS:
        if level in groups:
            items = groups[level]
            count = len(items)
            # 计算该等级的违规文件数
            level_files = set(item.get('file_path', '') for item in items)
            file_count = len(level_files)
            lines.append(f"| {level} | {count} | {file_count} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 各等级详细列表
    for level in ORDERED_LEVELS:
        if level not in groups or not groups[level]:
            continue

        items = sort_by_path(groups[level])

        lines.append(f"## {level} 级别违规 ({len(items)} 条)")
        lines.append("")

        # 表头
        lines.append("| 序号 | 规则名称 | 规则编码 | 文件路径 | 行号 | 命中次数 | 匹配类型 | 违规描述 | 解决方案 |")
        lines.append("|------|----------|----------|----------|------|----------|----------|----------|----------|")

        # 表格内容
        for idx, item in enumerate(items, 1):
            rule_name = item.get('rule_name', 'N/A').replace('|', '\\|')
            rule_code = item.get('rule_code', 'N/A')
            file_path = item.get('file_path', 'N/A').replace('|', '\\|')
            line_number = item.get('line_number', 'N/A')
            count = item.get('count', 1)
            match_type = item.get('match_type', 'N/A').replace('|', '\\|')
            violation_desc = item.get('violation_desc', 'N/A').replace('|', '\\|')
            solution = item.get('solution', 'N/A').replace('|', '\\|')

            lines.append(f"| {idx} | {rule_name} | {rule_code} | `{file_path}` | {line_number} | {count} | {match_type} | {violation_desc} | {solution} |")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def html_level_class(level):
    """将中文风险等级映射到稳定 CSS class。"""
    if level == "严重":
        return "level-critical"
    if level == "高危":
        return "level-high"
    if level == "中危":
        return "level-medium"
    return "level-low"


def generate_html_dashboard(data, groups, source_file):
    """生成可筛选的单文件 HTML dashboard。"""
    generated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total_count = len(data)
    all_file_paths = {item.get('file_path', '') for item in data}
    cards = [
        ("总违规数", total_count, ""),
        ("违规文件数", len(all_file_paths), None),
    ]
    for level in ORDERED_LEVELS:
        cards.append((f"{level}级", len(groups.get(level, [])), level))

    card_parts = []
    for label, count, filter_level in cards:
        if filter_level is None:
            card_parts.append(f'<article class="card"><strong>{esc(count)}</strong><span>{esc(label)}</span></article>')
        else:
            card_parts.append(
                '<button type="button" class="card" '
                f'data-filter-level="{esc(filter_level)}">'
                f'<strong>{esc(count)}</strong><span>{esc(label)}</span></button>'
            )
    cards_html = "\n".join(card_parts)
    level_options_html = "\n".join(
        f'<option value="{esc(level)}">{esc(level)}</option>'
        for level in ORDERED_LEVELS
        if groups.get(level)
    )

    sorted_items = sorted(
        data,
        key=lambda item: (
            LEVEL_PRIORITY.get(item.get('rule_level', '未知'), 99),
            item.get('file_path', ''),
            item.get('line_number', 0),
        ),
    )
    rows = []
    for idx, item in enumerate(sorted_items, 1):
        level = item.get('rule_level', '未知')
        rows.append(
            "<tr "
            f'data-level="{esc(level)}">'
            f"<td>{idx}</td>"
            f'<td class="{html_level_class(level)}">{esc(level)}</td>'
            f"<td>{esc(item.get('rule_name', 'N/A'))}<br><code>{esc(item.get('rule_code', 'N/A'))}</code></td>"
            f"<td><code>{esc(item.get('file_path', 'N/A'))}</code></td>"
            f"<td>{esc(item.get('line_number', 'N/A'))}</td>"
            f"<td>{esc(item.get('count', 1))}</td>"
            f"<td>{esc(item.get('match_type', 'N/A'))}</td>"
            f"<td>{esc(item.get('violation_desc', 'N/A'))}</td>"
            f"<td>{esc(item.get('solution', 'N/A'))}</td>"
            "</tr>"
        )

    table_html = f"""
<table>
  <thead>
    <tr>
      <th data-sort>序号</th>
      <th data-sort>等级</th>
      <th data-sort>规则</th>
      <th data-sort>文件路径</th>
      <th data-sort>行号</th>
      <th data-sort>命中</th>
      <th data-sort>匹配类型</th>
      <th>违规描述</th>
      <th>解决方案</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
"""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Java 代码扫描结果 Dashboard</title>
  <style>
    :root {{
      --bg: #f4f6f8;
      --panel: #ffffff;
      --text: #161d27;
      --muted: #657085;
      --line: #d8dee9;
      --critical: #991b1b;
      --high: #b45309;
      --medium: #1d4ed8;
      --low: #475569;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); }}
    header, main {{ max-width: 1280px; margin: 0 auto; padding: 28px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; line-height: 1.15; letter-spacing: 0; }}
    .meta, .filters {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .meta {{ color: var(--muted); font-size: 13px; }}
    .pill, button, input, select {{ border: 1px solid var(--line); border-radius: 6px; background: var(--panel); }}
    .pill {{ padding: 4px 10px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 20px 0; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; transition: border-color 150ms ease, transform 150ms ease; }}
    button.card {{ min-height: auto; cursor: pointer; text-align: left; color: inherit; }}
    .card:hover, .card.active {{ border-color: var(--accent); }}
    .card:active {{ transform: translateY(1px); }}
    .card strong {{ display: block; font-size: 28px; line-height: 1.1; }}
    .card span {{ color: var(--muted); font-size: 13px; }}
    .filters {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; margin-bottom: 14px; }}
    input, select, button {{ min-height: 36px; padding: 0 10px; font: inherit; }}
    input {{ flex: 1 1 260px; min-width: 0; }}
    button {{ cursor: pointer; transition: border-color 150ms ease, background-color 150ms ease, transform 150ms ease; }}
    button:hover {{ border-color: var(--accent); }}
    button:active {{ transform: translateY(1px); }}
    button:focus-visible, input:focus-visible, select:focus-visible {{ outline: 2px solid color-mix(in srgb, var(--accent) 42%, transparent); outline-offset: 2px; }}
    .count {{ align-self: center; color: var(--muted); font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 600; background: #fafbfc; position: sticky; top: 0; }}
    th[data-sort] {{ cursor: pointer; user-select: none; }}
    th[data-sort]::after {{ content: "  ↕"; color: var(--muted); font-weight: 400; }}
    th[data-sort][aria-sort="ascending"]::after {{ content: "  ↑"; }}
    th[data-sort][aria-sort="descending"]::after {{ content: "  ↓"; }}
    tr[hidden] {{ display: none; }}
    code {{ overflow-wrap: anywhere; }}
    .level-critical {{ color: var(--critical); font-weight: 700; }}
    .level-high {{ color: var(--high); font-weight: 700; }}
    .level-medium {{ color: var(--medium); font-weight: 700; }}
    .level-low {{ color: var(--low); font-weight: 700; }}
    @media (max-width: 720px) {{
      header, main {{ padding: 20px 12px; }}
      h1 {{ font-size: 24px; }}
      .table-wrap {{ overflow-x: auto; }}
      table {{ min-width: 920px; }}
      .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Java 代码扫描结果 Dashboard</h1>
    <div class="meta">
      <span class="pill">生成时间：{esc(generated_at)}</span>
      <span class="pill">来源：{esc(source_file)}</span>
      <span class="pill">记录数：{total_count}</span>
    </div>
  </header>
  <main data-generated-at="{esc(generated_at)}" data-source="{esc(source_file)}" data-source-count="{total_count}">
    <section class="cards">{cards_html}</section>
    <section class="filters" aria-label="筛选">
      <input id="q" type="search" placeholder="按规则、文件、描述搜索">
      <select id="level">
        <option value="">全部等级</option>
        {level_options_html}
      </select>
      <button type="button" id="reset">重置</button>
      <button type="button" id="copyVisible">复制当前视图</button>
      <span class="count" id="visibleCount" aria-live="polite"></span>
    </section>
    <section class="table-wrap">{table_html}</section>
  </main>
  <script>
    const q = document.getElementById('q');
    const level = document.getElementById('level');
    const reset = document.getElementById('reset');
    const copyVisible = document.getElementById('copyVisible');
    const visibleCount = document.getElementById('visibleCount');
    const rows = Array.from(document.querySelectorAll('tbody tr'));
    function applyFilters() {{
      const needle = q.value.trim().toLowerCase();
      const selected = level.value;
      let visible = 0;
      for (const row of rows) {{
        const text = row.textContent.toLowerCase();
        const rowLevel = row.dataset.level || '';
        row.hidden = Boolean((selected && rowLevel !== selected) || (needle && !text.includes(needle)));
        if (!row.hidden) visible += 1;
      }}
      visibleCount.textContent = `显示 ${{visible}} / ${{rows.length}}`;
      document.querySelectorAll('[data-filter-level]').forEach((button) => {{
        button.classList.toggle('active', Boolean(selected && button.dataset.filterLevel === selected));
      }});
    }}
    q.addEventListener('input', applyFilters);
    level.addEventListener('change', applyFilters);
    reset.addEventListener('click', () => {{ q.value = ''; level.value = ''; applyFilters(); }});
    copyVisible.addEventListener('click', async () => {{
      const visibleRows = rows.filter((row) => !row.hidden);
      const text = visibleRows.map((row) => row.innerText.trim().replace(/\\s+/g, '\\t')).join('\\n');
      try {{
        await navigator.clipboard.writeText(text);
        visibleCount.textContent = `已复制 ${{visibleRows.length}} 行`;
      }} catch {{
        visibleCount.textContent = '当前环境不允许复制';
      }}
    }});
    document.querySelectorAll('[data-filter-level]').forEach((button) => {{
      button.addEventListener('click', () => {{
        level.value = level.value === button.dataset.filterLevel ? '' : button.dataset.filterLevel;
        applyFilters();
      }});
    }});
    document.querySelectorAll('th[data-sort]').forEach((th) => {{
      th.addEventListener('click', () => {{
        const index = Array.from(th.parentElement.children).indexOf(th);
        const direction = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
        document.querySelectorAll('th[data-sort]').forEach((item) => item.removeAttribute('aria-sort'));
        th.setAttribute('aria-sort', direction);
        const tbody = th.closest('table').querySelector('tbody');
        rows.sort((a, b) => {{
          const av = a.children[index]?.innerText.trim() || '';
          const bv = b.children[index]?.innerText.trim() || '';
          const cmp = av.localeCompare(bv, 'zh-CN', {{ numeric: true }});
          return direction === 'ascending' ? cmp : -cmp;
        }}).forEach((row) => tbody.appendChild(row));
      }});
    }});
    applyFilters();
  </script>
</body>
</html>
"""


def parse_args():
    """解析命令行参数，保持默认 Markdown 报告兼容。"""
    parser = argparse.ArgumentParser(description="生成 Java 扫描 Markdown 报告和可选 HTML dashboard")
    parser.add_argument(
        "--html",
        choices=["auto", "always", "never"],
        default="auto",
        help="HTML dashboard 生成策略：auto=结果超过20条时生成，always=强制生成，never=不生成",
    )
    parser.add_argument(
        "--html-out",
        default=None,
        help="HTML dashboard 输出路径；默认写入 output/html/kingdee-cosmic/<timestamp>/index.html",
    )
    parser.add_argument(
        "--result-file",
        default=None,
        help="扫描结果 JSON 路径；默认读取 scripts/result/scan_java_result.json",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Markdown 报告输出目录；默认写入 scripts/result",
    )
    return parser.parse_args()


def default_html_output_path():
    """按共享 HTML 产物约定生成默认输出路径。"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    return ACTIVE_ROOT / "output" / "html" / "kingdee-cosmic" / timestamp / "index.html"


def main():
    """主函数"""
    args = parse_args()
    print("=" * 60)
    print("Java 代码扫描结果报告生成工具")
    print("=" * 60)
    print()
    
    # 加载数据
    print("[步骤 1] 加载扫描结果...")
    result_file = Path(args.result_file).resolve() if args.result_file else RESULT_DIR / "scan_java_result.json"
    data = load_scan_result(result_file)
    if data is None:
        return 1
    print(f"  加载记录数: {len(data)}")
    print()
    
    # 按等级分组
    print("[步骤 2] 按等级分组...")
    groups = group_by_level(data)
    for level in ORDERED_LEVELS:
        if level in groups:
            print(f"  {level}: {len(groups[level])} 条")
    print()
    
    # 生成报告
    print("[步骤 3] 生成 Markdown 报告...")
    report_content = generate_markdown_report(groups)
    
    # 保存报告
    output_dir = Path(args.out_dir).resolve() if args.out_dir else RESULT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "scan_result.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"  报告已保存到: {output_file}")
    print()

    should_generate_html = args.html == "always" or (args.html == "auto" and len(data) > 20)
    if args.html == "never":
        should_generate_html = False

    if should_generate_html:
        print("[步骤 4] 生成 HTML dashboard...")
        html_output_file = Path(args.html_out).resolve() if args.html_out else default_html_output_path()
        html_output_file.parent.mkdir(parents=True, exist_ok=True)
        html_content = generate_html_dashboard(data, groups, result_file)
        with open(html_output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"  HTML dashboard 已保存到: {html_output_file}")
        print("  建议执行质量门禁:")
        print(
            "  node skills/meta/html-output-quality/scripts/check-html.mjs "
            f"--html {html_output_file} --source {result_file} --out {html_output_file.parent}"
        )
        print()
    else:
        print("[步骤 4] HTML dashboard 未生成（结果不超过 20 条或 --html never）")
        print()
    
    print("=" * 60)
    print("报告生成完成!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit(main())
