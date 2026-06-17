#!/usr/bin/env python3
"""
通用联网搜索 MCP 服务器
支持 DuckDuckGo、Bing 等搜索引擎
"""

import asyncio
import json
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urlparse

class SearchMCPServer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

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
            return [{'error': str(e)}]

    def fetch_page(self, url):
        """获取页面内容"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 移除不需要的标签
            for tag in soup(['script', 'style', 'nav', 'footer']):
                tag.decompose()

            # 提取主要内容
            main = soup.find('main') or soup.find('article') or soup.find('body')
            if main:
                text = main.get_text(separator='\n', strip=True)
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                return '\n'.join(lines[:100])  # 限制长度

            return soup.get_text(strip=True)[:5000]
        except Exception as e:
            return f"Error: {str(e)}"

    def handle_request(self, request):
        """处理 MCP 请求"""
        method = request.get('method')
        params = request.get('params', {})

        if method == 'search':
            query = params.get('query', '')
            engine = params.get('engine', 'duckduckgo')
            num = params.get('num', 10)

            if engine == 'duckduckgo':
                results = self.search_duckduckgo(query, num)
            else:
                results = [{'error': f'Unsupported engine: {engine}'}]

            return {
                'jsonrpc': '2.0',
                'id': request.get('id'),
                'result': {'results': results}
            }

        elif method == 'fetch':
            url = params.get('url', '')
            content = self.fetch_page(url)

            return {
                'jsonrpc': '2.0',
                'id': request.get('id'),
                'result': {'content': content}
            }

        elif method == 'tools/discover':
            # 返回可用工具列表
            return {
                'jsonrpc': '2.0',
                'id': request.get('id'),
                'result': {
                    'tools': [
                        {
                            'name': 'web_search',
                            'description': 'Search the web using DuckDuckGo',
                            'parameters': {
                                'type': 'object',
                                'properties': {
                                    'query': {'type': 'string', 'description': 'Search query'},
                                    'num': {'type': 'integer', 'description': 'Number of results'}
                                },
                                'required': ['query']
                            }
                        },
                        {
                            'name': 'web_fetch',
                            'description': 'Fetch content from a URL',
                            'parameters': {
                                'type': 'object',
                                'properties': {
                                    'url': {'type': 'string', 'description': 'URL to fetch'}
                                },
                                'required': ['url']
                            }
                        }
                    ]
                }
            }

        else:
            return {
                'jsonrpc': '2.0',
                'id': request.get('id'),
                'error': {'code': -32601, 'message': f'Method not found: {method}'}
            }

    def run(self):
        """运行 MCP 服务器"""
        while True:
            try:
                line = input()
                if not line:
                    continue

                request = json.loads(line)
                response = self.handle_request(request)
                print(json.dumps(response, ensure_ascii=False), flush=True)

            except json.JSONDecodeError as e:
                print(json.dumps({
                    'jsonrpc': '2.0',
                    'error': {'code': -32700, 'message': f'Parse error: {str(e)}'}
                }), flush=True)
            except EOFError:
                break
            except Exception as e:
                print(json.dumps({
                    'jsonrpc': '2.0',
                    'error': {'code': -32603, 'message': f'Internal error: {str(e)}'}
                }), flush=True)

if __name__ == '__main__':
    server = SearchMCPServer()
    server.run()
