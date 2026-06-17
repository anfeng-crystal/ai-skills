#!/usr/bin/env python3
"""
获取金蝶云苍穹官方文档
"""

import requests
from bs4 import BeautifulSoup
import json

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})

def fetch_and_save(url, filepath):
    """获取页面并保存"""
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # 移除不需要的标签
        for tag in soup(['script', 'style', 'nav', 'footer']):
            tag.decompose()

        # 提取主要内容
        main = soup.find('main') or soup.find('article') or soup.find('.content') or soup.find('body')

        if main:
            text = main.get_text(separator='\n', strip=True)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            content = '\n'.join(lines)
        else:
            content = soup.get_text(strip=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# 来源: {url}\n\n")
            f.write(content)

        print(f"已保存: {filepath} ({len(content)} 字符)")
        return content

    except Exception as e:
        print(f"获取失败 {url}: {e}")
        return None

# 获取官方文档
urls = [
    ("https://dev.kingdee.com/", "/Users/anfeng/AI/knowledge/kingdee/cosmic/官方文档/开发者门户.md"),
    ("https://demo.kdcloud.com/devdoc/core/", "/Users/anfeng/AI/knowledge/kingdee/cosmic/官方文档/开发文档中心.md"),
    ("https://dev.kingdee.com/dev/resource", "/Users/anfeng/AI/knowledge/kingdee/cosmic/官方文档/开发资源.md"),
]

for url, filepath in urls:
    print(f"\n获取: {url}")
    fetch_and_save(url, filepath)
