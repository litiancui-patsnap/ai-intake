# AI信息摄入系统 - 系统设计文档

## 1. 系统概览

### 1.1 目标
为互联网工程师构建一套低噪音、高信号的AI信息摄入系统，每天15分钟保持AI领域更新，同时将信息沉淀为可检索的知识资产。

### 1.2 核心原则
- **低噪音优先**：宁愿漏掉，也不要浪费时间在低价值信息上
- **可追踪**：每条信息可追溯来源、时间、作者、链接
- **可对比**：同一主题的进展可串联对比
- **可复盘**：支持日报→周报→月度回顾的知识飞轮
- **工程导向**：重点关注SDK、框架、最佳实践、评测、基础设施、产品变更

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         信息源层                                  │
│  RSS/Atom Feed │ GitHub Releases │ Research Blogs │ Changelogs  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Ingest 采集模块                              │
│  - FeedParser (RSS/Atom)                                        │
│  - GitHub API Client                                            │
│  - 标准化为统一数据结构                                           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      De-dup 去重模块                              │
│  - URL规范化                                                      │
│  - 标题相似度 (rapidfuzz)                                         │
│  - 内容哈希                                                       │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Classify 分类模块                             │
│  - 关键词匹配                                                     │
│  - 正则表达式规则                                                 │
│  - 多主题标注                                                     │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Score 评分模块                               │
│  - 研究信号评分                                                   │
│  - 工程信号评分                                                   │
│  - 来源权威度评分                                                 │
│  - 新鲜度评分                                                     │
│  - 个人偏好加权                                                   │
│  - 生成评分详解 (score_breakdown)                                │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Summarize 摘要模块                              │
│  - LLM摘要生成 (可选: OpenAI/Anthropic)                          │
│  - Extractive摘要 (fallback)                                    │
│  - 工程师要点提取                                                 │
│  - 行动项建议                                                     │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Publish 发布模块                               │
│  - daily.md 生成 (按主题分组)                                     │
│  - weekly.md 生成 (趋势聚合)                                      │
│  - 可选: Email/Telegram推送                                      │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Storage 存储层                                 │
│  - SQLite 主存储                                                  │
│  - JSONL 导出 (可选)                                              │
│  - 支持全文检索、时间范围查询、主题过滤                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
1. 定时触发 (Cron/GitHub Actions)
   ↓
2. 从配置文件读取信息源 (sources.yaml)
   ↓
3. 并行采集各信息源 → 标准化
   ↓
4. 去重 (与历史数据对比)
   ↓
5. 分类打标 (topics.yaml)
   ↓
6. 评分排序 (rules.yaml)
   ↓
7. Top-N筛选 + 必读项
   ↓
8. LLM摘要生成 (异步批量)
   ↓
9. 生成报告并存储
   ↓
10. 输出到文件/推送渠道
```

---

## 3. 核心模块说明

### 3.1 Ingest 采集模块

**功能**：
- 支持RSS/Atom Feed解析
- 支持GitHub Releases API
- 支持HTML页面抓取 (BeautifulSoup)
- 统一输出为标准化Item结构

**数据结构**：
```python
Item {
    url: str           # 原始URL
    title: str         # 标题
    published: datetime # 发布时间
    source: str        # 来源标识
    author: str        # 作者
    summary: str       # 原始摘要
    content: str       # 全文内容
    raw_data: dict     # 原始数据备份
}
```

**容错机制**：
- 每个源独立超时控制 (默认30s)
- 单源失败不影响整体
- 重试机制 (最多3次)
- 详细日志记录

### 3.2 De-dup 去重模块

**策略**：
1. **URL规范化**：去除tracking参数、统一scheme
2. **标题相似度**：使用rapidfuzz计算Levenshtein距离，阈值90%
3. **内容哈希**：SHA256哈希，检测完全重复

**时间窗口**：默认对比过去30天的数据

### 3.3 Classify 分类模块

**方法**：
- 关键词匹配 (不区分大小写)
- 正则表达式规则
- 来源自动分类 (sources.yaml中预定义)

**输出**：每个Item可分配0~N个主题标签

### 3.4 Score 评分模块

**评分维度** (总分100)：

| 维度 | 权重 | 计算方法 |
|------|------|----------|
| 研究信号 | 25% | 关键词匹配: 新模型/新方法/评测数据/突破性结果 |
| 工程信号 | 35% | 破坏性变更/性能提升/API更新/实战指南/SDK发布 |
| 来源权威 | 20% | sources.yaml中配置的authority_score |
| 新鲜度 | 10% | 指数衰减: score = 10 * exp(-age_hours/48) |
| 个人偏好 | 10% | topics.yaml中的boost权重 + rules.yaml规则 |

**score_breakdown示例**：
```yaml
score_breakdown:
  total: 87
  research_signal: 20  # "新SOTA模型"
  engineering_signal: 32  # "破坏性API变更"
  authority: 18  # OpenAI官方源
  freshness: 9  # 2小时前发布
  preference: 8  # 命中"LLM"主题 +5, "OpenAI"公司 +3
  reasons:
    - "来自高权威源: OpenAI Research"
    - "工程信号: API破坏性变更"
    - "命中关注主题: LLM, API"
```

### 3.5 Summarize 摘要模块

**两种模式**：

1. **LLM模式** (需配置API Key)：
   - 支持OpenAI/Anthropic
   - 生成100-180字中文摘要
   - 提取3条工程师要点
   - 建议1条行动项
   - 批量处理降低成本

2. **Extractive模式** (Fallback)：
   - 提取前200词
   - 关键句抽取
   - 简单的工程要点提取

**提示词模板** (LLM)：
```
你是一个资深AI工程师。请阅读以下信息并输出：

1. 中文摘要 (100-180字)
2. 工程师要点 (3条bullet points，每条<30字)
3. 行动建议 (1条，"我该做什么"或"何时关注")

原文: {content}

输出JSON格式:
{
  "summary": "...",
  "key_points": ["...", "...", "..."],
  "action": "..."
}
```

### 3.6 Publish 发布模块

**输出格式**：

**daily.md**：
```markdown
# AI信息日报 - 2025-12-29

📊 总计: 38条 | 🔥 必读: 5条 | ⏰ 预计阅读: 12分钟

---

## 🔥 必读 (Must Read)

### [GPT-5 API发布公告](https://...)
- **来源**: OpenAI Changelog | **发布**: 2025-12-29 10:00 JST | **评分**: 95/100
- **摘要**: OpenAI正式发布GPT-5 API，提供2M上下文窗口和原生视频理解能力...
- **工程师要点**:
  - 新增`gpt-5-turbo`模型，定价$0.03/1K tokens
  - 破坏性变更: `temperature`参数范围改为0-2
  - 视频输入通过`messages[].content[].video_url`传递
- **行动建议**: 本周测试API兼容性，评估成本影响
- **评分详解**: 工程信号35/35 (破坏性变更+新功能) | 来源权威20/20 | 新鲜度10/10

---

## 📚 LLM

### [Llama 4架构论文](https://...)
...

## 🔧 Inference
...
```

**weekly.md**：
```markdown
# AI信息周报 - 2025 W52

## 本周总览
本周AI领域三大趋势: (1) 多家厂商发布长上下文模型 (2M+上下文成为标配) (2) 推理加速技术突破，vLLM 0.8发布FlashAttention-3支持 (3) Agent框架整合潮，LangChain与LlamaIndex宣布互操作协议...

---

## 🔥 本周趋势 Top 5

### 1. 长上下文成为新标配
- [GPT-5 2M上下文](https://...)
- [Claude 4 1.5M上下文](https://...)
- [Gemini 2.0 10M上下文](https://...)
**趋势**: 2M上下文成为主流模型门槛，RAG架构面临重构

### 2. 推理性能突破
...

---

## ✅ 本周必做 Top 3
1. **测试GPT-5 API**: 评估迁移成本和性能收益
2. **升级vLLM到0.8**: 获得30%推理加速
3. **关注LangChain 0.3**: 破坏性变更影响现有代码

---

## 👀 下周关注清单
- [ ] NVIDIA GTC大会 (可能发布H200性能数据)
- [ ] PyTorch 2.6 RC版本
- [ ] OpenAI DevDay后续
```

### 3.7 Storage 存储模块

**SQLite Schema**：

```sql
-- 信息条目表
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    published DATETIME NOT NULL,
    source TEXT NOT NULL,
    author TEXT,
    summary TEXT,
    content TEXT,
    score REAL,
    score_breakdown TEXT,  -- JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 主题标签表
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- 信息源表
CREATE TABLE sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,  -- rss, github, html
    url TEXT NOT NULL,
    authority_score INTEGER DEFAULT 50,
    enabled BOOLEAN DEFAULT TRUE,
    last_fetched DATETIME
);

-- 运行日志表
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,  -- daily, weekly
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    items_collected INTEGER,
    items_published INTEGER,
    status TEXT,  -- success, partial, failed
    error_log TEXT
);

-- 全文检索索引
CREATE VIRTUAL TABLE items_fts USING fts5(
    title, summary, content,
    content=items,
    content_rowid=id
);
```

---

## 4. 运行方式

### 4.1 本地运行

```bash
# 日报 (默认24小时)
python -m src.main daily

# 周报 (默认7天)
python -m src.main weekly

# 自定义时间范围
python -m src.main daily --since 48h --limit 50

# 干运行 (不写入数据库)
python -m src.main daily --dry-run

# 自定义配置目录
python -m src.main daily --config-dir ./configs --output-dir ./reports
```

### 4.2 Cron定时

```bash
# 每天早上8点运行
0 8 * * * cd /path/to/ai-intake && /usr/bin/python3 -m src.main daily >> /var/log/ai-intake.log 2>&1

# 每周一早上9点运行周报
0 9 * * 1 cd /path/to/ai-intake && /usr/bin/python3 -m src.main weekly >> /var/log/ai-intake.log 2>&1
```

### 4.3 GitHub Actions (可选)

```yaml
name: Daily AI Digest
on:
  schedule:
    - cron: '0 23 * * *'  # UTC 23:00 = JST 08:00
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m src.main daily
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      - uses: actions/upload-artifact@v3
        with:
          name: daily-report
          path: outputs/daily/*.md
```

---

## 5. 扩展方式

### 5.1 新增信息源

**步骤**：
1. 在 [sources.yaml](sources.yaml) 添加配置：
```yaml
- name: "New Research Blog"
  type: rss
  url: "https://example.com/feed.xml"
  authority_score: 75
  tags: [research, ml]
  enabled: true
```

2. 如果是新类型源，在 `src/ingest/` 添加采集器：
```python
# src/ingest/custom_fetcher.py
from .base import BaseFetcher

class CustomFetcher(BaseFetcher):
    def fetch(self, source_config):
        # 实现采集逻辑
        pass
```

3. 在 `src/ingest/__init__.py` 注册：
```python
FETCHERS = {
    'rss': RSSFetcher,
    'github': GitHubFetcher,
    'custom': CustomFetcher,  # 新增
}
```

### 5.2 新增主题/关键词

编辑 [topics.yaml](topics.yaml)：
```yaml
- name: "新主题名称"
  keywords:
    - "关键词1"
    - "关键词2"
  patterns:
    - "正则表达式.*模式"
  boost: 1.2  # 评分加权
  must_read_if_score_above: 80
```

### 5.3 调整评分规则

编辑 [rules.yaml](rules.yaml)：
```yaml
scoring:
  weights:
    research_signal: 0.25
    engineering_signal: 0.35  # 调高工程权重
    authority: 0.20
    freshness: 0.10
    preference: 0.10

  # 新增必读规则
  must_read_rules:
    - condition: "source == 'OpenAI' AND 'breaking' in title.lower()"
      reason: "OpenAI破坏性变更"
    - condition: "score >= 85"
      reason: "高分条目"
```

### 5.4 接入LLM

**方法1: 环境变量**
```bash
export OPENAI_API_KEY="sk-..."
export LLM_PROVIDER="openai"  # 或 "anthropic"
```

**方法2: 配置文件**
```yaml
# config.yaml
llm:
  provider: openai
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}  # 从环境变量读取
  max_tokens: 500
  temperature: 0.3
```

**实现**：
```python
# src/summarize/llm.py
from openai import OpenAI

class LLMSummarizer:
    def __init__(self, provider='openai'):
        if provider == 'openai':
            self.client = OpenAI()
        elif provider == 'anthropic':
            from anthropic import Anthropic
            self.client = Anthropic()

    def summarize(self, item):
        # 调用API生成摘要
        pass
```

---

## 6. 配置文件说明

### 6.1 sources.yaml
定义所有信息源，包括类型、URL、权威度评分、默认标签。

### 6.2 topics.yaml
定义关注主题，包括关键词、正则模式、评分加权、必读阈值。

### 6.3 rules.yaml
定义评分规则、过滤规则、必读规则、输出格式。

---

## 7. 技术栈

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| 语言 | Python 3.11+ | 生态丰富，适合快速开发 |
| RSS解析 | feedparser | 成熟稳定的Feed解析库 |
| HTTP客户端 | requests | 简单可靠 |
| HTML解析 | beautifulsoup4 | 强大的HTML/XML解析 |
| 相似度计算 | rapidfuzz | 快速字符串匹配 |
| 数据库 | SQLite | 零配置，适合单机 |
| 配置解析 | PyYAML | YAML配置文件支持 |
| LLM (可选) | openai/anthropic SDK | API调用 |
| CLI | argparse | Python标准库 |

---

## 8. 性能与资源

**预期性能** (50个信息源，每天300条)：
- 采集: 1-2分钟 (并行)
- 处理: 30秒 (去重/分类/评分)
- LLM摘要: 2-5分钟 (取决于API QPS)
- 总计: 5-10分钟

**资源占用**：
- 内存: < 500MB
- 磁盘: 数据库每月约50MB，报告文件每月约10MB
- 网络: 采集约5-10MB/天

---

## 9. 容错与监控

### 9.1 容错机制
- **单源失败隔离**: 一个信息源失败不影响其他源
- **部分失败继续**: 采集到部分数据也能生成报告
- **优雅降级**: LLM不可用时使用extractive摘要
- **重试机制**: 网络错误自动重试3次

### 9.2 日志系统
```
[2025-12-29 08:00:01] INFO  | Starting daily digest
[2025-12-29 08:00:05] INFO  | Fetched 45 items from OpenAI Blog
[2025-12-29 08:00:07] ERROR | Failed to fetch GitHub:anthropic/anthropic-sdk-python: timeout
[2025-12-29 08:00:07] WARN  | Retrying (1/3)...
[2025-12-29 08:05:32] INFO  | Generated daily report: 38 items, 5 must-read
[2025-12-29 08:05:32] INFO  | Report saved to outputs/daily/2025-12-29.md
```

### 9.3 监控指标
- 采集成功率
- 去重率
- 平均评分
- LLM调用成功率
- 生成报告数量

---

## 10. 未来扩展方向

### 10.1 短期 (1-2月)
- [ ] Email/Telegram推送
- [ ] Web UI查看历史报告
- [ ] 更多信息源 (Twitter/X, Reddit, HN)
- [ ] 智能推荐 (基于阅读历史)

### 10.2 中期 (3-6月)
- [ ] 向量检索 (相似文章推荐)
- [ ] 知识图谱 (公司/产品/技术关系)
- [ ] 多人协作 (团队共享订阅)
- [ ] 移动端适配

### 10.3 长期 (6月+)
- [ ] AI Agent自动追踪研究进展
- [ ] 自动生成技术演进报告
- [ ] 集成到IDE (VSCode插件)

---

## 附录

### A. 故障排查

**问题**: 采集失败率高
- 检查网络连接
- 检查sources.yaml中的URL是否有效
- 增加timeout配置

**问题**: LLM摘要生成失败
- 检查API Key是否配置
- 检查API额度是否充足
- 降级到extractive模式

**问题**: 数据库锁死
- 检查是否有多个进程同时写入
- 使用`--dry-run`测试

### B. 参考资料
- [RSS 2.0规范](https://www.rssboard.org/rss-specification)
- [Atom 1.0规范](https://datatracker.ietf.org/doc/html/rfc4287)
- [GitHub REST API](https://docs.github.com/en/rest)
- [SQLite FTS5](https://www.sqlite.org/fts5.html)
