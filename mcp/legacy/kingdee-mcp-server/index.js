#!/usr/bin/env node
/**
 * 金蝶云苍穹知识库 MCP 服务器
 */

const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require('@modelcontextprotocol/sdk/types.js');
const fs = require('fs');
const path = require('path');

// 知识库根目录
const KNOWLEDGE_BASE_DIR = '/Users/anfeng/KingdeeKnowledge';

// 简单的向量相似度计算（基于关键词匹配）
function calculateRelevance(query, content) {
  const queryWords = query.toLowerCase().split(/\s+/);
  const contentLower = content.toLowerCase();

  let score = 0;
  for (const word of queryWords) {
    if (word.length > 1) {
      const matches = (contentLower.match(new RegExp(word, 'g')) || []).length;
      score += matches;
    }
  }
  return score;
}

// 递归读取所有 markdown 文件
function getAllMarkdownFiles(dir, files = []) {
  const items = fs.readdirSync(dir);
  for (const item of items) {
    const fullPath = path.join(dir, item);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      getAllMarkdownFiles(fullPath, files);
    } else if (item.endsWith('.md')) {
      files.push(fullPath);
    }
  }
  return files;
}

// 搜索知识库
function searchKnowledgeBase(query, topK = 5) {
  const files = getAllMarkdownFiles(KNOWLEDGE_BASE_DIR);
  const results = [];

  for (const file of files) {
    try {
      const content = fs.readFileSync(file, 'utf-8');
      const score = calculateRelevance(query, content);
      if (score > 0) {
        results.push({
          file: path.relative(KNOWLEDGE_BASE_DIR, file),
          score,
          content: content.slice(0, 3000) // 限制返回内容长度
        });
      }
    } catch (err) {
      // 忽略读取错误
    }
  }

  // 按相关度排序
  results.sort((a, b) => b.score - a.score);
  return results.slice(0, topK);
}

// 获取特定主题的知识
function getTopicKnowledge(topic) {
  const topicMap = {
    '表单插件': '开发指南/插件开发',
    '列表插件': '开发指南/插件开发',
    '操作插件': '开发指南/插件开发',
    'DynamicObject': 'API参考/KORM',
    'KORM': 'API参考/KORM',
    '服务助手': 'API参考/服务助手',
    'BusinessDataServiceHelper': 'API参考/服务助手',
    'SaveServiceHelper': 'API参考/服务助手',
  };

  const dir = topicMap[topic];
  if (!dir) {
    return searchKnowledgeBase(topic);
  }

  const fullDir = path.join(KNOWLEDGE_BASE_DIR, dir);
  if (!fs.existsSync(fullDir)) {
    return searchKnowledgeBase(topic);
  }

  const files = getAllMarkdownFiles(fullDir);
  const results = [];

  for (const file of files) {
    try {
      const content = fs.readFileSync(file, 'utf-8');
      const score = calculateRelevance(topic, content);
      results.push({
        file: path.relative(KNOWLEDGE_BASE_DIR, file),
        score: score || 1,
        content: content.slice(0, 3000)
      });
    } catch (err) {
      // 忽略错误
    }
  }

  results.sort((a, b) => b.score - a.score);
  return results.slice(0, 5);
}

// 创建 MCP 服务器
const server = new Server(
  {
    name: 'kingdee-knowledge-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// 注册工具列表处理器
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'search_knowledge',
        description: '搜索金蝶云苍穹知识库，查找相关开发文档和API参考',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: '搜索关键词',
            },
            topK: {
              type: 'number',
              description: '返回结果数量（默认5条）',
              default: 5,
            },
          },
          required: ['query'],
        },
      },
      {
        name: 'get_topic_guide',
        description: '获取特定主题的完整开发指南（如表单插件、列表插件、DynamicObject等）',
        inputSchema: {
          type: 'object',
          properties: {
            topic: {
              type: 'string',
              description: '主题名称，如：表单插件、列表插件、DynamicObject、KORM等',
            },
          },
          required: ['topic'],
        },
      },
    ],
  };
});

// 注册工具调用处理器
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === 'search_knowledge') {
    const { query, topK = 5 } = args;
    const results = searchKnowledgeBase(query, topK);

    if (results.length === 0) {
      return {
        content: [
          {
            type: 'text',
            text: `未找到与 "${query}" 相关的知识库内容。`,
          },
        ],
      };
    }

    const formattedResults = results.map((r, i) =>
      `[${i + 1}] ${r.file}\n相关度: ${r.score}\n\n${r.content}\n---`
    ).join('\n\n');

    return {
      content: [
        {
          type: 'text',
          text: `搜索 "${query}" 找到 ${results.length} 条结果:\n\n${formattedResults}`,
        },
      ],
    };
  }

  if (name === 'get_topic_guide') {
    const { topic } = args;
    const results = getTopicKnowledge(topic);

    if (results.length === 0) {
      return {
        content: [
          {
            type: 'text',
            text: `未找到 "${topic}" 相关的主题指南。`,
          },
        ],
      };
    }

    const formattedResults = results.map((r, i) =>
      `[${i + 1}] ${r.file}\n\n${r.content}\n---`
    ).join('\n\n');

    return {
      content: [
        {
          type: 'text',
          text: `主题 "${topic}" 的开发指南:\n\n${formattedResults}`,
        },
      ],
    };
  }

  throw new Error(`未知工具: ${name}`);
});

// 启动服务器
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('金蝶云苍穹知识库 MCP 服务器已启动');
}

main().catch(console.error);
