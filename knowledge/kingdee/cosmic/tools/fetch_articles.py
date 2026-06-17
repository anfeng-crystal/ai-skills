#!/usr/bin/env python3
"""
金蝶云苍穹资料获取工具 - 带内容过滤
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import os

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})

def clean_content(text):
    """清理内容，去除噪音"""
    # 移除多余空行
    lines = text.split('\n')
    cleaned_lines = []
    prev_empty = False

    for line in lines:
        line = line.strip()
        # 跳过纯数字行（页码、序号等）
        if re.match(r'^\d+$', line):
            continue
        # 跳过常见的噪音内容
        if line in ['赞', '评论', '收藏', '分享', '打赏', '阅读', '人点赞', '人阅读', '推荐阅读',
                   '展开全部', '收起', '加载中...', '暂无评论', '发表评论', '回复']:
            continue
        # 跳过广告相关内容
        if any(kw in line for kw in ['广告', '推广', '赞助', '商业合作', '联系我们']):
            continue
        # 跳过导航类内容
        if any(kw in line for kw in ['上一篇', '下一篇', '相关文章', '热门文章', '最新文章']):
            continue

        if line:
            cleaned_lines.append(line)
            prev_empty = False
        elif not prev_empty:
            cleaned_lines.append('')
            prev_empty = True

    return '\n'.join(cleaned_lines)

def extract_article_content(html, url):
    """提取文章正文内容"""
    soup = BeautifulSoup(html, 'html.parser')

    # 移除不需要的标签
    for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'header',
                     'advertisement', 'ad', 'iframe', 'noscript']):
        tag.decompose()

    # 移除常见的噪音元素
    for selector in ['.ad', '.advertisement', '.comment', '.comments',
                     '.related-posts', '.sidebar', '.widget', '.share',
                     '.author-info', '.post-nav', '.pagination']:
        for elem in soup.select(selector):
            elem.decompose()

    # 尝试找到主要内容区域
    content = None
    # 常见的文章容器选择器
    selectors = [
        'article',
        'main',
        '.article-content',
        '.post-content',
        '.content',
        '.entry-content',
        '#article-content',
        '#content',
        '.article',
        '.post',
        '[role="main"]'
    ]

    for selector in selectors:
        content = soup.select_one(selector)
        if content:
            break

    # 如果没找到，尝试从 body 中提取
    if not content:
        content = soup.body

    if not content:
        return None

    # 提取文本
    text = content.get_text(separator='\n', strip=True)

    # 进一步清理
    text = clean_content(text)

    # 限制长度，避免过大
    max_length = 15000
    if len(text) > max_length:
        text = text[:max_length] + '\n\n... (内容已截断)'

    return text

def fetch_article(url, title=None):
    """获取文章并提取内容"""
    try:
        print(f"获取: {url}")
        resp = session.get(url, timeout=30)
        resp.raise_for_status()

        content = extract_article_content(resp.text, url)

        if content and len(content) > 200:
            return {
                'url': url,
                'title': title or '未命名',
                'content': content
            }
        else:
            print(f"  内容过短或为空")
            return None

    except Exception as e:
        print(f"  获取失败: {e}")
        return None

def save_article(article, filepath):
    """保存文章到文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {article['title']}\n\n")
        f.write(f"> 来源: {article['url']}\n\n")
        f.write("---\n\n")
        f.write(article['content'])

    print(f"  已保存: {filepath} ({len(article['content'])} 字符)")

# 需要重新获取的高质量文章
articles = [
    {
        'url': 'https://www.jianshu.com/p/1045cba60079',
        'title': '金蝶云苍穹插件开发指南',
        'filepath': '/Users/anfeng/AI/knowledge/kingdee/cosmic/开发指南/插件开发/插件开发指南.md'
    },
    {
        'url': 'https://blog.csdn.net/2301_79898161/article/details/137326771',
        'title': '表单插件与操作插件',
        'filepath': '/Users/anfeng/AI/knowledge/kingdee/cosmic/开发指南/插件开发/表单插件详解.md'
    },
    {
        'url': 'https://blog.csdn.net/tanrt/article/details/128915484',
        'title': '列表插件事件与接口详解',
        'filepath': '/Users/anfeng/AI/knowledge/kingdee/cosmic/开发指南/插件开发/列表插件详解.md'
    },
    {
        'url': 'https://juejin.cn/post/7388311581658628148',
        'title': '插件开发数据操作详解',
        'filepath': '/Users/anfeng/AI/knowledge/kingdee/cosmic/开发指南/插件开发/数据操作详解.md'
    },
    {
        'url': 'https://vip.kingdee.com/article/466017882661337088?productLineId=29',
        'title': 'DynamicObject相关操作',
        'filepath': '/Users/anfeng/AI/knowledge/kingdee/cosmic/API参考/KORM/DynamicObject详解.md'
    },
]

if __name__ == '__main__':
    for article_info in articles:
        article = fetch_article(article_info['url'], article_info['title'])
        if article:
            save_article(article, article_info['filepath'])
        time.sleep(1.5)  # 避免请求过快
