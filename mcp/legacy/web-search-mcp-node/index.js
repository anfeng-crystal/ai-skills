#!/usr/bin/env node
/**
 * 通用联网搜索 MCP 服务器
 * 支持搜索、过滤、格式化内容
 */

const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require('@modelcontextprotocol/sdk/types.js');
const https = require('https');
const http = require('http');
const { URL } = require('url');

// 简单的 HTML 转文本
function htmlToText(html) {
  return html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim();
}

// 过滤噪音内容
function filterNoise(text) {
  const noisePatterns = [
    /登录\s*[|｜]\s*注册/g,
    /Copyright\s*[©®]\s*\d{4}/gi,
    /版权所有.*保留所有权利/g,
    /京ICP备\d+号/g,
    /点击下载.*$/gm,
    /相关阅读[\s\S]*$/,
    /最新发布[\s\S]*$/,
    /热门标签[\s\S]*$/,
    /您需要登录后才可以发表评论[\s\S]*$/,
    /拖动LOGO至书签栏[\s\S]*?立即收藏/,
    /安装后可以在桌面快捷访问[\s\S]*?立即添加/,
    /解锁后支持完整在线阅读或下载编辑/g,
    /海量优质内容资源[\s\S]*?解锁/,
    /赞\s*\d+/g,
    /阅读\s*\d+/g,
    /收藏\s*\d+/g,
    /分享/g,
    /\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/g,
  ];

  let cleaned = text;
  for (const pattern of noisePatterns) {
    cleaned = cleaned.replace(pattern, '');
  }

  // 移除多余空行
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');

  return cleaned.trim();
}

// 提取主要内容
function extractMainContent(html, url) {
  // 移除 script/style
  let content = html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');

  // 尝试提取文章主体（常见选择器）
  const articlePatterns = [
    /<article[^>]*>([\s\S]*?)<\/article>/i,
    /<main[^>]*>([\s\S]*?)<\/main>/i,
    /<div[^>]*class=["'][^"']*(?:article|content|post|entry)[^"']*["'][^>]*>([\s\S]*?)<\/div>/i,
    /<div[^>]*id=["'][^"']*(?:article|content|post|entry)[^"']*["'][^>]*>([\s\S]*?)<\/div>/i,
  ];

  for (const pattern of articlePatterns) {
    const match = content.match(pattern);
    if (match && match[1].length > 500) {
      return match[1];
    }
  }

  // 如果没找到，返回 body 内容
  const bodyMatch = content.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  return bodyMatch ? bodyMatch[1] : content;
}

// 获取网页内容
function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const client = parsed.protocol === 'https:' ? https : http;

    const req = client.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      },
      timeout: 15000,
    }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        // 跟随重定向
        fetchUrl(new URL(res.headers.location, url).href).then(resolve).catch(reject);
        return;
      }

      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode}`));
        return;
      }

      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Timeout'));
    });
  });
}

// 解析 site: 语法
function parseSiteQuery(query) {
  const sitePattern = /site:(\S+)/i;
  const match = query.match(sitePattern);
  if (match) {
    const site = match[1];
    const cleanQuery = query.replace(sitePattern, '').trim();
    return { site, cleanQuery };
  }
  return { site: null, cleanQuery: query };
}

// 搜索（使用 DuckDuckGo 或 SearX）
async function searchWeb(query, maxResults = 5) {
  const { site, cleanQuery } = parseSiteQuery(query);
  const results = [];

  // 尝试多个搜索引擎
  const searchEngines = [
    () => searchDuckDuckGo(cleanQuery, maxResults * 2, site),
    () => searchSearX(cleanQuery, maxResults * 2, site),
  ];

  for (const engine of searchEngines) {
    try {
      const engineResults = await engine();
      results.push(...engineResults);
      if (results.length >= maxResults) break;
    } catch (e) {
      // 继续尝试下一个
    }
  }

  // 去重
  const seen = new Set();
  let filteredResults = results.filter(r => {
    if (seen.has(r.url)) return false;
    seen.add(r.url);
    return true;
  });

  // 如果指定了 site，过滤结果
  if (site) {
    filteredResults = filteredResults.filter(r => {
      try {
        const url = new URL(r.url);
        return url.hostname.includes(site) || site.includes(url.hostname);
      } catch (e) {
        return false;
      }
    });
  }

  return filteredResults.slice(0, maxResults);
}

// DuckDuckGo 搜索（HTML 版本）
async function searchDuckDuckGo(query, maxResults, site = null) {
  // 如果指定了 site，添加到查询
  const fullQuery = site ? `${query} site:${site}` : query;
  const searchUrl = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(fullQuery)}`;
  const html = await fetchUrl(searchUrl);

  const results = [];
  // DuckDuckGo HTML 结果格式
  const resultPattern = /<a[^>]*class=["']result__a["'][^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g;

  let match;
  const urls = [];
  const titles = [];

  while ((match = resultPattern.exec(html)) && urls.length < maxResults) {
    let url = match[1];
    // DuckDuckGo 使用重定向
    const redirectMatch = url.match(/uddg=([^&]+)/);
    if (redirectMatch) {
      url = decodeURIComponent(redirectMatch[1]);
    }
    urls.push(url);
    titles.push(htmlToText(match[2]));
  }

  for (let i = 0; i < urls.length; i++) {
    if (!urls[i].includes('duckduckgo.com')) {
      results.push({ url: urls[i], title: titles[i] || '无标题' });
    }
  }

  return results;
}

// SearX 搜索（公共实例）
async function searchSearX(query, maxResults, site = null) {
  // 使用公共 SearX 实例
  const searxInstances = [
    'https://search.sapti.me',
    'https://search.bus-hit.me',
    'https://searx.be',
  ];

  // 如果指定了 site，添加到查询
  const fullQuery = site ? `${query} site:${site}` : query;

  for (const instance of searxInstances) {
    try {
      const searchUrl = `${instance}/search?q=${encodeURIComponent(fullQuery)}&format=json`;
      const json = await fetchJson(searchUrl);

      if (json && json.results) {
        let results = json.results.slice(0, maxResults).map(r => ({
          url: r.url,
          title: r.title || '无标题',
        }));

        // 如果指定了 site，再次过滤确保准确
        if (site) {
          results = results.filter(r => {
            try {
              const url = new URL(r.url);
              return url.hostname.includes(site);
            } catch (e) {
              return false;
            }
          });
        }

        return results;
      }
    } catch (e) {
      continue;
    }
  }

  return [];
}

// 获取 JSON
function fetchJson(url) {
  return new Promise((resolve, reject) => {
    fetchUrl(url).then(html => {
      try {
        resolve(JSON.parse(html));
      } catch (e) {
        reject(e);
      }
    }).catch(reject);
  });
}

// 获取并格式化页面内容
async function fetchAndFormat(url, maxLength = 5000) {
  try {
    const html = await fetchUrl(url);
    const mainContent = extractMainContent(html, url);
    let text = htmlToText(mainContent);
    text = filterNoise(text);

    // 限制长度
    if (text.length > maxLength) {
      text = text.slice(0, maxLength) + '\n\n... (内容已截断)';
    }

    return text;
  } catch (e) {
    return `获取内容失败: ${e.message}`;
  }
}

// 创建 MCP 服务器
const server = new Server(
  {
    name: 'web-search-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// 注册工具列表
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'web_search',
        description: '联网搜索并返回过滤后的内容。支持 site:xxx.com 语法限定搜索特定网站。自动去除广告、导航、版权信息等噪音。',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: '搜索关键词，支持 site:xxx.com 语法限定网站，如 "金蝶云苍穹 site:vip.kingdee.com"',
            },
            maxResults: {
              type: 'number',
              description: '返回结果数量（默认3条）',
              default: 3,
            },
            fetchContent: {
              type: 'boolean',
              description: '是否获取网页正文内容（默认true）',
              default: true,
            },
          },
          required: ['query'],
        },
      },
      {
        name: 'fetch_page',
        description: '获取指定网页的内容并格式化',
        inputSchema: {
          type: 'object',
          properties: {
            url: {
              type: 'string',
              description: '网页URL',
            },
            maxLength: {
              type: 'number',
              description: '最大内容长度（默认5000字符）',
              default: 5000,
            },
          },
          required: ['url'],
        },
      },
    ],
  };
});

// 注册工具调用
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === 'web_search') {
    const { query, maxResults = 3, fetchContent = true } = args;

    const searchResults = await searchWeb(query, maxResults);

    if (searchResults.length === 0) {
      return {
        content: [{ type: 'text', text: `未找到 "${query}" 的搜索结果。` }],
      };
    }

    let output = `搜索 "${query}" 找到 ${searchResults.length} 条结果:\n\n`;

    for (let i = 0; i < searchResults.length; i++) {
      const result = searchResults[i];
      output += `[${i + 1}] ${result.title}\nURL: ${result.url}\n`;

      if (fetchContent) {
        const content = await fetchAndFormat(result.url, 3000);
        output += `\n内容:\n${content}\n`;
      }

      output += '\n---\n\n';
    }

    return { content: [{ type: 'text', text: output }] };
  }

  if (name === 'fetch_page') {
    const { url, maxLength = 5000 } = args;
    const content = await fetchAndFormat(url, maxLength);

    return {
      content: [{
        type: 'text',
        text: `页面内容 (${url}):\n\n${content}`,
      }],
    };
  }

  throw new Error(`未知工具: ${name}`);
});

// 启动服务器
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('通用联网搜索 MCP 服务器已启动');
}

main().catch(console.error);
