# AI信息摄入系统

> 为互联网工程师打造的低噪音AI信息订阅系统：每天15分钟保持AI更新，不被噪音淹没

## 目标

- **低噪音优先**：宁愿漏掉，也不要浪费时间在低价值信息上
- **可追踪**：每条信息可追溯来源、时间、作者、链接
- **可对比**：同一主题的进展可串联对比
- **可复盘**：支持日报→周报→月度回顾的知识飞轮
- **工程导向**：重点关注SDK、框架、最佳实践、评测、基础设施、产品变更

## 功能特性

- ✅ **多源采集**: RSS/Atom Feed + GitHub Releases
- ✅ **智能去重**: URL规范化 + 标题相似度 + 内容哈希
- ✅ **自动分类**: 基于关键词和正则表达式的主题标注
- ✅ **智能评分**: 研究信号 + 工程信号 + 来源权威度 + 新鲜度 + 个人偏好
- ✅ **LLM摘要**: 支持OpenAI/Anthropic，自动生成中文摘要和行动建议
- ✅ **Markdown输出**: 日报 + 周报，适配Obsidian/Notion
- ✅ **SQLite存储**: 全文检索 + JSONL导出
- ✅ **定时运行**: 支持Cron + GitHub Actions

## 快速开始

### 1. 安装依赖

```bash
# 克隆仓库
git clone https://github.com/yourname/ai-intake.git
cd ai-intake

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

```bash
# 配置文件已包含默认配置，可直接运行
# 可选：编辑配置文件定制化
# - sources.yaml: 信息源配置
# - topics.yaml: 主题配置
# - rules.yaml: 评分规则和个人偏好
```

### 3. 运行

```bash
# 生成日报 (默认24小时)
python -m src.main daily

# 生成日报 (最近48小时，限制40条)
python -m src.main daily --since 48h --limit 40

# 生成周报
python -m src.main weekly

# Dry-run模式 (不写入数据库)
python -m src.main daily --dry-run

# 跳过LLM摘要 (节省API费用)
python -m src.main daily --no-summary
```

### 4. 查看报告

```bash
# 日报输出
outputs/daily/2025-12-29.md

# 周报输出
outputs/weekly/2025-W52.md
```

## 配置LLM (可选)

系统支持两种LLM提供商生成AI摘要：

### OpenAI

```bash
# 设置环境变量
export OPENAI_API_KEY="sk-..."

# 或在 rules.yaml 中配置
llm:
  provider: openai
  model: gpt-4o-mini
```

### Anthropic

```bash
export ANTHROPIC_API_KEY="sk-ant-..."

# rules.yaml
llm:
  provider: anthropic
  model: claude-3-haiku-20240307
```

**注意**: 如果不配置LLM，系统会自动降级到extractive摘要模式。

## 定时运行

### 本地 Cron

```bash
# 编辑 crontab
crontab -e

# 每天早上8点运行日报
0 8 * * * cd /path/to/ai-intake && /usr/bin/python3 -m src.main daily >> /var/log/ai-intake.log 2>&1

# 每周一早上9点运行周报
0 9 * * 1 cd /path/to/ai-intake && /usr/bin/python3 -m src.main weekly >> /var/log/ai-intake.log 2>&1
```

### GitHub Actions

已包含工作流配置：

- `.github/workflows/daily_digest.yml`: 每天UTC 23:00 (JST 08:00)
- `.github/workflows/weekly_digest.yml`: 每周一UTC 00:00 (JST 09:00)

**配置步骤**:

1. Fork此仓库
2. 在仓库设置中添加Secrets:
   - `OPENAI_API_KEY` (如使用OpenAI)
   - `ANTHROPIC_API_KEY` (如使用Anthropic)
3. 启用GitHub Actions
4. 报告将自动生成并作为Artifacts上传

## 项目结构

```
ai-intake/
├── README.md                    # 本文件
├── DESIGN.md                    # 系统设计文档
├── requirements.txt             # Python依赖
├── sources.yaml                 # 信息源配置
├── topics.yaml                  # 主题配置
├── rules.yaml                   # 评分规则配置
├── src/
│   ├── main.py                  # 主程序入口
│   ├── ingest/                  # 采集模块
│   │   ├── rss_fetcher.py
│   │   ├── github_fetcher.py
│   │   └── models.py
│   ├── dedup/                   # 去重模块
│   ├── classify/                # 分类模块
│   ├── score/                   # 评分模块
│   ├── summarize/               # 摘要模块
│   ├── publish/                 # 发布模块
│   ├── storage/                 # 存储模块
│   └── utils/                   # 工具模块
├── outputs/                     # 输出目录
│   ├── daily/                   # 日报
│   └── weekly/                  # 周报
├── scripts/                     # 脚本
│   ├── run_daily.sh
│   └── run_weekly.sh
└── .github/workflows/           # GitHub Actions

```

## 扩展指南

### 新增信息源

编辑 `sources.yaml`:

```yaml
research:
  - name: "New AI Blog"
    type: rss
    url: "https://example.com/feed.xml"
    authority_score: 80
    tags: [research, ai]
    enabled: true
```

支持的类型：
- `rss`: RSS/Atom Feed
- `github`: GitHub Releases (url格式: `owner/repo`)

### 新增主题

编辑 `topics.yaml`:

```yaml
core_tech:
  - name: "FineTuning"
    display_name: "模型微调"
    keywords:
      - "fine-tune"
      - "finetune"
      - "lora"
      - "qlora"
    patterns:
      - "fine[- ]tun"
    boost: 1.2
    must_read_if_score_above: 75
```

### 调整评分规则

编辑 `rules.yaml`:

```yaml
scoring:
  weights:
    research_signal: 0.25
    engineering_signal: 0.35  # 工程师优先，权重更高
    authority: 0.20
    freshness: 0.10
    preference: 0.10

preferences:
  priority_vendors:  # 加权+3分
    - "OpenAI"
    - "Anthropic"
  priority_tools:    # 加权+2分
    - "LangChain"
    - "vLLM"
```

### 新增采集器类型

1. 创建采集器类:

```python
# src/ingest/custom_fetcher.py
from .base import BaseFetcher
from .models import Item

class CustomFetcher(BaseFetcher):
    def fetch(self, source):
        # 实现采集逻辑
        items = []
        # ...
        return items
```

2. 注册采集器:

```python
# src/ingest/__init__.py
from .custom_fetcher import CustomFetcher

FETCHERS = {
    'rss': RSSFetcher,
    'github': GitHubFetcher,
    'custom': CustomFetcher,  # 新增
}
```

3. 在 `sources.yaml` 中使用:

```yaml
- name: "Custom Source"
  type: custom
  url: "https://..."
```

## CLI参数说明

### `daily` 命令

```bash
python -m src.main daily [OPTIONS]

Options:
  --since TEXT          采集时间范围 (例如: 24h, 48h) [默认: 24h]
  --limit INT           输出条目数量限制 [默认: 40]
  --config-dir TEXT     配置文件目录 [默认: .]
  --output-dir TEXT     输出目录 [默认: outputs]
  --dry-run             Dry-run模式，不写入数据库
  --no-summary          跳过LLM摘要生成
  --export-jsonl        导出JSONL格式
  --verbose             详细日志输出
```

### `weekly` 命令

```bash
python -m src.main weekly [OPTIONS]

Options:
  --since TEXT          查询时间范围 (例如: 7d, 14d) [默认: 7d]
  --limit INT           输出条目数量限制 [默认: 120]
  --config-dir TEXT     配置文件目录 [默认: .]
  --output-dir TEXT     输出目录 [默认: outputs]
  --dry-run             Dry-run模式
  --verbose             详细日志输出
```

## 常见问题

### Q: 采集失败率高怎么办？

A: 检查以下几点：
1. 网络连接是否正常
2. `sources.yaml` 中的URL是否有效（用浏览器测试）
3. 增加 `rules.yaml` 中的 `network.timeout` 和 `network.max_retries`
4. 查看日志中的具体错误信息

### Q: LLM摘要生成失败？

A: 可能原因：
1. API密钥未配置或无效
2. API额度不足
3. 网络连接问题

解决方案：
- 检查环境变量 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`
- 使用 `--no-summary` 跳过LLM摘要
- 系统会自动降级到extractive摘要

### Q: 如何查看历史数据？

A: 数据存储在 `ai-intake.db` (SQLite):

```bash
# 使用sqlite3查看
sqlite3 ai-intake.db

# 查询示例
SELECT title, score, published FROM items ORDER BY score DESC LIMIT 10;

# 导出JSONL
python -m src.main daily --export-jsonl
```

### Q: 内存占用过高？

A: 优化建议：
1. 减少 `sources.yaml` 中启用的信息源数量
2. 降低 `--limit` 参数
3. 定期清理旧数据（系统会自动保留90天）

### Q: 如何自定义报告格式？

A: 编辑 `src/publish/__init__.py` 中的模板函数:
- `_generate_daily_markdown()`: 日报格式
- `_generate_weekly_markdown()`: 周报格式

## 性能与资源占用

**典型运行** (50个信息源，每天300条):
- 采集: 1-2分钟
- 处理: 30秒
- LLM摘要: 2-5分钟 (取决于API QPS)
- **总计**: 5-10分钟

**资源占用**:
- 内存: < 500MB
- 磁盘: 数据库每月约50MB，报告每月约10MB
- 网络: 采集约5-10MB/天

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 致谢

感谢所有开源项目和AI信息源提供商。

---

**Made with ❤️ for AI Engineers**
