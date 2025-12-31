# 项目文件结构

## 完整文件树

```
ai-intake/
│
├── README.md                           # 项目说明文档
├── DESIGN.md                           # 系统设计文档
├── QUICKSTART.md                       # 快速上手指南
├── EXAMPLE_OUTPUT.md                   # 输出示例文档
├── PROJECT_STRUCTURE.md                # 本文件
│
├── requirements.txt                    # Python依赖列表
├── pyproject.toml                      # 项目配置（PEP 518）
├── .gitignore                          # Git忽略文件
│
├── sources.yaml                        # 信息源配置文件
├── topics.yaml                         # 主题配置文件
├── rules.yaml                          # 评分规则配置文件
│
├── src/                                # 源代码目录
│   ├── __init__.py                     # 包初始化文件
│   ├── main.py                         # 主程序入口（CLI）
│   │
│   ├── ingest/                         # 采集模块
│   │   ├── __init__.py                 # 模块初始化，包含fetch_all函数
│   │   ├── models.py                   # 数据模型（Item类）
│   │   ├── base.py                     # BaseFetcher基类
│   │   ├── rss_fetcher.py              # RSS/Atom Feed采集器
│   │   └── github_fetcher.py           # GitHub Releases采集器
│   │
│   ├── dedup/                          # 去重模块
│   │   └── __init__.py                 # URL规范化、相似度计算、去重逻辑
│   │
│   ├── classify/                       # 分类模块
│   │   └── __init__.py                 # 主题分类逻辑
│   │
│   ├── score/                          # 评分模块
│   │   └── __init__.py                 # Scorer类、评分逻辑、必读标记
│   │
│   ├── summarize/                      # 摘要模块
│   │   └── __init__.py                 # LLMSummarizer、ExtractiveSummarizer
│   │
│   ├── publish/                        # 发布模块
│   │   └── __init__.py                 # 日报/周报Markdown生成
│   │
│   ├── storage/                        # 存储模块
│   │   └── __init__.py                 # Storage类、SQLite操作、JSONL导出
│   │
│   └── utils/                          # 工具模块
│       ├── __init__.py                 # 工具模块导出
│       ├── logger.py                   # 日志工具
│       └── config.py                   # 配置加载工具
│
├── outputs/                            # 输出目录（由程序自动创建）
│   ├── daily/                          # 日报输出目录
│   │   └── YYYY-MM-DD.md               # 日报文件（按日期命名）
│   └── weekly/                         # 周报输出目录
│       └── YYYY-WXX.md                 # 周报文件（按周号命名）
│
├── scripts/                            # 脚本目录
│   ├── run_daily.sh                    # 日报运行脚本（Bash）
│   └── run_weekly.sh                   # 周报运行脚本（Bash）
│
├── .github/                            # GitHub配置目录
│   └── workflows/                      # GitHub Actions工作流
│       ├── daily_digest.yml            # 日报自动化工作流
│       └── weekly_digest.yml           # 周报自动化工作流
│
└── ai-intake.db                        # SQLite数据库（由程序自动创建）
```

## 核心文件说明

### 配置文件

| 文件 | 说明 | 可否修改 |
|------|------|----------|
| [sources.yaml](sources.yaml) | 信息源配置，包含RSS/GitHub等 | ✅ 推荐定制 |
| [topics.yaml](topics.yaml) | 主题与关键词配置 | ✅ 推荐定制 |
| [rules.yaml](rules.yaml) | 评分规则、过滤规则、个人偏好 | ✅ 推荐定制 |
| [requirements.txt](requirements.txt) | Python依赖列表 | ⚠️ 谨慎修改 |
| [pyproject.toml](pyproject.toml) | 项目元数据 | ⚠️ 谨慎修改 |

### 文档文件

| 文件 | 说明 |
|------|------|
| [README.md](README.md) | 项目说明、快速开始、CLI参数、FAQ |
| [DESIGN.md](DESIGN.md) | 系统架构、数据流、模块设计、扩展方法 |
| [QUICKSTART.md](QUICKSTART.md) | 5分钟快速体验、典型工作流、最佳实践 |
| [EXAMPLE_OUTPUT.md](EXAMPLE_OUTPUT.md) | 日报/周报输出示例 |

### 源代码模块

#### 1. ingest - 采集模块

| 文件 | 功能 | 行数 |
|------|------|------|
| [models.py](src/ingest/models.py) | Item数据模型定义 | ~70 |
| [base.py](src/ingest/base.py) | BaseFetcher基类 | ~40 |
| [rss_fetcher.py](src/ingest/rss_fetcher.py) | RSS/Atom解析 | ~170 |
| [github_fetcher.py](src/ingest/github_fetcher.py) | GitHub API调用 | ~150 |

**关键类**:
- `Item`: 信息条目数据模型
- `BaseFetcher`: 采集器基类，定义fetch接口
- `RSSFetcher`: RSS/Atom Feed采集器
- `GitHubFetcher`: GitHub Releases采集器

#### 2. dedup - 去重模块

| 文件 | 功能 | 行数 |
|------|------|------|
| [\_\_init\_\_.py](src/dedup/__init__.py) | URL规范化、相似度计算、去重 | ~200 |

**关键函数**:
- `normalize_url()`: URL规范化
- `is_duplicate_url()`: URL相似度判断
- `is_duplicate_title()`: 标题相似度判断
- `deduplicate()`: 批量去重

#### 3. classify - 分类模块

| 文件 | 功能 | 行数 |
|------|------|------|
| [\_\_init\_\_.py](src/classify/__init__.py) | 主题分类逻辑 | ~80 |

**关键函数**:
- `classify_item()`: 为单个Item分配主题标签
- `classify_batch()`: 批量分类

#### 4. score - 评分模块

| 文件 | 功能 | 行数 |
|------|------|------|
| [\_\_init\_\_.py](src/score/__init__.py) | 多维度评分、必读标记 | ~350 |

**关键类与函数**:
- `Scorer`: 评分器类
  - `score_item()`: 为Item评分
  - `_score_research_signal()`: 研究信号评分
  - `_score_engineering_signal()`: 工程信号评分
  - `_score_authority()`: 来源权威度评分
  - `_score_freshness()`: 新鲜度评分
  - `_score_preference()`: 个人偏好评分
- `score_batch()`: 批量评分
- `mark_must_read()`: 标记必读

#### 5. summarize - 摘要模块

| 文件 | 功能 | 行数 |
|------|------|------|
| [\_\_init\_\_.py](src/summarize/__init__.py) | LLM摘要、Extractive摘要 | ~250 |

**关键类**:
- `LLMSummarizer`: LLM摘要器（OpenAI/Anthropic）
- `ExtractiveSummarizer`: 抽取式摘要器（Fallback）

#### 6. publish - 发布模块

| 文件 | 功能 | 行数 |
|------|------|------|
| [\_\_init\_\_.py](src/publish/__init__.py) | 日报/周报Markdown生成 | ~400 |

**关键函数**:
- `generate_daily_report()`: 生成日报
- `generate_weekly_report()`: 生成周报
- `_format_item()`: 格式化单个Item
- `_extract_trends()`: 提取周报趋势

#### 7. storage - 存储模块

| 文件 | 功能 | 行数 |
|------|------|------|
| [\_\_init\_\_.py](src/storage/__init__.py) | SQLite操作、JSONL导出 | ~300 |

**关键类**:
- `Storage`: 存储管理器
  - `save_items()`: 保存Item列表
  - `get_items()`: 查询Item列表
  - `export_jsonl()`: 导出JSONL
  - `log_run()`: 记录运行日志
  - `cleanup_old_data()`: 清理旧数据

#### 8. utils - 工具模块

| 文件 | 功能 | 行数 |
|------|------|------|
| [logger.py](src/utils/logger.py) | 日志工具 | ~60 |
| [config.py](src/utils/config.py) | 配置加载工具 | ~200 |

**关键类与函数**:
- `setup_logger()`: 设置日志记录器
- `get_logger()`: 获取日志记录器
- `Config`: 配置管理器
  - `get_enabled_sources()`: 获取已启用的信息源
  - `get_scoring_config()`: 获取评分配置
  - `get_llm_config()`: 获取LLM配置

#### 9. main.py - 主程序

| 文件 | 功能 | 行数 |
|------|------|------|
| [main.py](src/main.py) | CLI入口、流程编排 | ~350 |

**关键函数**:
- `run_daily()`: 运行日报生成流程
- `run_weekly()`: 运行周报生成流程
- `main()`: 主函数，解析命令行参数

## 代码统计

| 模块 | 文件数 | 代码行数（估算） |
|------|--------|------------------|
| ingest | 5 | ~450 |
| dedup | 1 | ~200 |
| classify | 1 | ~80 |
| score | 1 | ~350 |
| summarize | 1 | ~250 |
| publish | 1 | ~400 |
| storage | 1 | ~300 |
| utils | 3 | ~280 |
| main | 1 | ~350 |
| **总计** | **15** | **~2,660** |

## 数据流向

```
sources.yaml → ingest → [Items] → dedup → [Unique Items]
                                              ↓
                                          classify
                                              ↓
                                    [Items with Tags]
                                              ↓
                                            score
                                              ↓
                                    [Scored Items]
                                              ↓
                                        summarize (optional)
                                              ↓
                                    [Items with AI Summary]
                                              ↓
                                          publish
                                              ↓
                                   daily.md / weekly.md
                                              ↓
                                          storage
                                              ↓
                                      ai-intake.db
```

## 配置文件依赖关系

```
sources.yaml ──┐
               ├──> Config ──> main.py
topics.yaml ───┤
               │
rules.yaml ────┘
```

## 运行时文件生成

| 文件/目录 | 何时创建 | 说明 |
|-----------|----------|------|
| `ai-intake.db` | 首次运行 | SQLite数据库 |
| `outputs/daily/` | 运行daily命令 | 日报输出目录 |
| `outputs/weekly/` | 运行weekly命令 | 周报输出目录 |
| `*.md` (日报) | 每次运行daily | 按日期命名 |
| `*.md` (周报) | 每次运行weekly | 按周号命名 |
| `*.jsonl` | 使用--export-jsonl | JSONL导出文件 |

## 扩展点

### 1. 新增信息源类型

**文件**: `src/ingest/`

1. 创建新的Fetcher类（继承BaseFetcher）
2. 在`src/ingest/__init__.py`中注册到FETCHERS字典
3. 在`sources.yaml`中使用新类型

### 2. 新增评分维度

**文件**: `src/score/__init__.py`

1. 在`Scorer`类中添加`_score_xxx()`方法
2. 在`score_item()`中调用新方法
3. 在`rules.yaml`中配置新维度权重

### 3. 新增输出格式

**文件**: `src/publish/__init__.py`

1. 添加`generate_xxx_report()`函数
2. 在`src/main.py`中添加新命令

### 4. 新增LLM提供商

**文件**: `src/summarize/__init__.py`

1. 在`LLMSummarizer.__init__()`中添加新provider分支
2. 在`rules.yaml`中配置新provider

## 最佳实践

1. **修改配置文件**: 优先通过修改YAML配置文件定制行为
2. **扩展源代码**: 需要新功能时，遵循现有模块结构添加
3. **版本控制**: 使用Git跟踪配置文件变更
4. **备份数据库**: 定期备份`ai-intake.db`
5. **测试新功能**: 使用`--dry-run`测试新配置

## 相关文档

- 系统架构详解: [DESIGN.md](DESIGN.md)
- 快速开始: [QUICKSTART.md](QUICKSTART.md)
- 完整功能说明: [README.md](README.md)
- 输出示例: [EXAMPLE_OUTPUT.md](EXAMPLE_OUTPUT.md)
