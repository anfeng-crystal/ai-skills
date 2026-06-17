#!/usr/bin/env python3
"""
金蝶云苍穹资料搜索工具 - 使用 requests
用于搜索和整理金蝶云苍穹 7.0/8.0 开发资料
"""

import requests
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

class KingdeeSearcher:
    def __init__(self):
        self.knowledge_base = Path("/Users/anfeng/AI/knowledge/kingdee/cosmic")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def search_duckduckgo(self, query, num_results=10):
        """使用 DuckDuckGo 搜索"""
        try:
            url = "https://html.duckduckgo.com/html/"
            data = {'q': query, 'kl': 'zh-cn'}

            response = self.session.post(url, data=data, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            for result in soup.find_all('div', class_='result'):
                title_elem = result.find('a', class_='result__a')
                snippet_elem = result.find('a', class_='result__snippet')

                if title_elem and snippet_elem:
                    results.append({
                        'url': title_elem.get('href', ''),
                        'title': title_elem.get_text(strip=True),
                        'snippet': snippet_elem.get_text(strip=True)
                    })

            return results[:num_results]
        except Exception as e:
            print(f"搜索出错: {e}")
            return []

    def fetch_page(self, url):
        """获取页面内容"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"获取页面失败 {url}: {e}")
            return None

    def extract_main_content(self, html):
        """从 HTML 中提取正文内容"""
        soup = BeautifulSoup(html, 'html.parser')

        # 移除 script 和 style
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()

        # 尝试找到主要内容区域
        main_content = None
        for selector in ['main', 'article', '.content', '#content', '.main', '#main', '.document']:
            main_content = soup.select_one(selector)
            if main_content:
                break

        if not main_content:
            main_content = soup.body

        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
            # 清理多余空行
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            return '\n'.join(lines)

        return ""

    def save_to_knowledge_base(self, category, subcategory, filename, content):
        """保存到知识库"""
        directory = self.knowledge_base / category / subcategory
        directory.mkdir(parents=True, exist_ok=True)

        filepath = directory / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"已保存: {filepath}")
        return filepath

    def search_cosmic_docs(self):
        """搜索金蝶云苍穹文档"""
        queries = [
            ("金蝶云苍穹 7.0 开发平台 官方文档", "官方文档", "v7.0"),
            ("金蝶云苍穹 8.0 开发平台 官方文档", "官方文档", "v8.0"),
            ("金蝶云苍穹 插件开发指南", "开发指南", "插件开发"),
            ("金蝶云苍穹 kdorm 动态领域模型", "API参考", "KORM"),
            ("金蝶云苍穹 操作服务", "API参考", "操作服务"),
            ("金蝶云苍穹 元数据设计", "开发指南", "元数据设计"),
            ("金蝶云苍穹 开发规范", "最佳实践", "开发规范"),
            ("金蝶云苍穹 性能优化", "最佳实践", "性能优化"),
            ("金蝶云苍穹 常见问题", "常见问题", "常见问题"),
        ]

        all_results = {}

        for query, category, subcategory in queries:
            print(f"\n搜索: {query}")
            results = self.search_duckduckgo(query, num_results=5)
            all_results[query] = results

            # 保存搜索结果
            if results:
                content = f"# {query}\n\n"
                for i, r in enumerate(results, 1):
                    print(f"  {i}. {r['title'][:60]}...")
                    content += f"## {r['title']}\n\n"
                    content += f"- URL: {r['url']}\n"
                    content += f"- 摘要: {r['snippet']}\n\n"

                    # 尝试获取页面内容
                    if 'kingdee.com' in r['url'] or 'k3cloud' in r['url'] or 'cosmic' in r['url']:
                        print(f"     正在获取页面内容...")
                        page_html = self.fetch_page(r['url'])
                        if page_html:
                            page_content = self.extract_main_content(page_html)
                            if len(page_content) > 500:
                                content += f"### 页面内容\n\n{page_content[:3000]}...\n\n"

                filename = f"{subcategory.replace(' ', '_')}_search.md"
                self.save_to_knowledge_base(category, subcategory, filename, content)

        # 保存总索引
        index_content = "# 金蝶云苍穹资料搜索索引\n\n"
        index_content += "## 版本说明\n\n"
        index_content += "- 当前关注版本：7.0（当前使用）、8.0（未来升级）\n"
        index_content += "- 不包含：金蝶云星空（K3Cloud）、EAS\n\n"
        index_content += "## 搜索主题\n\n"

        for query, items in all_results.items():
            index_content += f"### {query}\n\n"
            for r in items:
                index_content += f"- [{r['title']}]({r['url']})\n"
            index_content += "\n"

        self.save_to_knowledge_base("社区资源", "搜索索引", "search_index.md", index_content)

        return all_results

def main():
    searcher = KingdeeSearcher()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "search":
            searcher.search_cosmic_docs()

        elif command == "fetch" and len(sys.argv) > 2:
            url = sys.argv[2]
            html = searcher.fetch_page(url)
            if html:
                content = searcher.extract_main_content(html)
                print(content[:3000])

    else:
        print("用法:")
        print("  python3 kingdee_search.py search    - 搜索金蝶云苍穹资料")
        print("  python3 kingdee_search.py fetch <url> - 获取指定页面")

if __name__ == "__main__":
    main()
