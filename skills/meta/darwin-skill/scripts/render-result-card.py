#!/usr/bin/env python3
"""
Darwin Skill 成果卡片渲染脚本

用法:
  python3 render-result-card.py <template_path> <data_json>

示例:
  python3 render-result-card.py templates/result-card-tech.html.template '{"skill_name":"test","score_before":"85","score_after":"91","score_delta":"6.0","date":"2026-04-29","dimensions":[{"name":"工作流清晰度","before":11,"after":14,"delta":3}],"improvements":["改进1","改进2"],"test_results":[{"id":"test1","status":"通过","delta":"+1"}]}'
"""

import sys
import json
import html
from string import Template


def esc(value):
    """Escape values inserted into HTML templates."""
    return html.escape(str(value), quote=True)


def render_dimensions_table(dimensions):
    """渲染维度对比表格（Markdown 格式）"""
    rows = []
    for dim in dimensions:
        rows.append(f"| {dim['name']} | {dim['before']}/10 | {dim['after']}/10 | +{dim['delta']} |")
    return '\n'.join(rows)


def render_dimensions_rows(dimensions):
    """渲染维度对比表格行（HTML 格式）"""
    rows = []
    for dim in dimensions:
        rows.append(f"""          <tr>
            <td>{esc(dim['name'])}</td>
            <td>{esc(dim['before'])}/10</td>
            <td>{esc(dim['after'])}/10</td>
            <td class="delta-cell">+{esc(dim['delta'])}</td>
          </tr>""")
    return '\n'.join(rows)


def render_improvements_list(improvements):
    """渲染改进列表（Markdown 格式）"""
    items = []
    for i, improvement in enumerate(improvements, 1):
        items.append(f"{i}. {improvement}")
    return '\n'.join(items)


def render_improvements_items(improvements):
    """渲染改进列表项（HTML 格式）"""
    items = []
    for improvement in improvements:
        items.append(f"        <li>{esc(improvement)}</li>")
    return '\n'.join(items)


def render_test_results_list(test_results):
    """渲染测试结果列表（Markdown 格式）"""
    items = []
    for result in test_results:
        items.append(f"- {result['id']}: {result['status']} (skill_delta: {result['delta']})")
    return '\n'.join(items)


def render_test_results_items(test_results):
    """渲染测试结果列表项（HTML 格式）"""
    items = []
    for result in test_results:
        items.append(f"""        <li>
          <div class="test-result">
            <span class="test-id">{esc(result['id'])}</span>
            <span class="test-status">{esc(result['status'])}</span>
            <span class="test-delta">{esc(result['delta'])}</span>
          </div>
        </li>""")
    return '\n'.join(items)


def render_template(template_path, data):
    """渲染模板"""
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()

    # 准备渲染数据
    render_data = {
        'skill_name': str(data['skill_name']),
        'score_before': str(data['score_before']),
        'score_after': str(data['score_after']),
        'score_delta': str(data['score_delta']),
        'date': str(data['date']),
    }

    # 根据模板类型选择渲染函数
    if template_path.endswith('.md.template'):
        # Markdown 模板
        render_data['dimensions_table'] = render_dimensions_table(data['dimensions'])
        render_data['improvements_list'] = render_improvements_list(data['improvements'])
        render_data['test_results_list'] = render_test_results_list(data['test_results'])
    else:
        # HTML 模板
        for key in ['skill_name', 'score_before', 'score_after', 'score_delta', 'date']:
            render_data[key] = esc(render_data[key])
        render_data['dimensions_rows'] = render_dimensions_rows(data['dimensions'])
        render_data['improvements_items'] = render_improvements_items(data['improvements'])
        render_data['test_results_items'] = render_test_results_items(data['test_results'])

    # 使用 Template 替换变量
    template = Template(template_content)
    return template.substitute(render_data)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    template_path = sys.argv[1]
    data_json = sys.argv[2]

    try:
        data = json.loads(data_json)
    except json.JSONDecodeError as e:
        print(f"错误: 无法解析 JSON 数据: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        result = render_template(template_path, data)
        print(result)
    except FileNotFoundError:
        print(f"错误: 模板文件不存在: {template_path}", file=sys.stderr)
        sys.exit(1)
    except KeyError as e:
        print(f"错误: 缺少必需的数据字段: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: 渲染失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
