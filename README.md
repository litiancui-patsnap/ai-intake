# ai-intake

一个面向个人使用的 AI 技术情报采集项目。

它不是 Web 服务，也不是 FastAPI 项目，而是一个本地或云端定时运行的 CLI 工具，用来做这些事：

- 聚合 AI 相关信息源
- 去重、分类、评分
- 生成日报和周报
- 可选使用 LLM 生成摘要
- 推送到飞书

当前项目已经整合了两类能力：

- 原有流水线：RSS、GitHub Releases、SQLite、Markdown 报告
- 新增能力：搜索式新闻采集、飞书卡片通知、可选信息图

## 适合什么场景

- 只给自己使用
- 每天自动查找最新的 AI 研发、工程、测试技术动态
- 先生成本地报告，再决定是否发送到飞书
- 使用 GitHub Actions 自动定时发送给自己

## 项目结构

```text
ai-intake/
├─ README.md
├─ .env.example
├─ sources.yaml
├─ topics.yaml
├─ rules.yaml
├─ requirements.txt
├─ outputs/
├─ src/
│  ├─ main.py
│  ├─ ingest/
│  ├─ dedup/
│  ├─ classify/
│  ├─ score/
│  ├─ summarize/
│  ├─ publish/
│  ├─ notify/
│  ├─ storage/
│  └─ utils/
└─ .github/workflows/
```

## 本地安装

```powershell
cd E:\projects\ai-intake
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 本地配置

项目现在只读取根目录 `.env`。

先复制模板：

```powershell
Copy-Item .env.example .env
```

### 飞书配置

如果你要推送到自己的飞书群，至少需要：

```env
FEISHU_WEBHOOK_URL=
FEISHU_APP_ID=
FEISHU_APP_SECRET=
```

建议使用你个人专用飞书群的机器人，不要和同事共用现有 webhook。

### LLM 配置

支持四种 provider：

- `openai`
- `openai_compatible`
- `anthropic`
- `ollama`

第三方 OpenAI 兼容接口示例：

```env
AI_INTAKE_LLM_PROVIDER=openai_compatible
AI_INTAKE_LLM_MODEL=gpt-5.4

OPENAI_BASE_URL=https://ai.hhhl.cc/v1
OPENAI_API_KEY=你的key
OPENAI_MODEL=gpt-5.4
```

本地 Ollama 示例：

```env
AI_INTAKE_LLM_PROVIDER=ollama
AI_INTAKE_LLM_MODEL=mistral-nemo:latest

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral-nemo:latest
OLLAMA_TEMPERATURE=0.7
OLLAMA_MODEL_TOKENS=128000
```

说明：

- 当前只会使用 `AI_INTAKE_LLM_PROVIDER` 指定的那套配置
- 如果暂时不想调用大模型，可以运行时加 `--no-summary`

## 本地运行

先本地试跑，不发通知：

```powershell
python -m src.main daily --no-notify
```

跳过 LLM 摘要：

```powershell
python -m src.main daily --no-summary --no-notify
```

正常生成日报并发送飞书：

```powershell
python -m src.main daily
```

生成周报：

```powershell
python -m src.main weekly
```

## 输出位置

- 日报：`outputs/daily/`
- 周报：`outputs/weekly/`
- 飞书信息图：`outputs/feishu/`
- SQLite 数据库：`ai-intake.db`

## 飞书通知配置

当前默认是“个人使用模式”，配置在 `rules.yaml`：

```yaml
notify:
  personal_use_only: true
  feishu_enabled: true
  feishu_include_infographic: false
  feishu_image_output_dir: "outputs/feishu"
  feishu_max_items: 3
```

这表示：

- 只走飞书
- 默认只发 3 条重点
- 默认不发长图
- 即使其他渠道配置了环境变量，也不会一起发送

## GitHub Actions 自动发送

项目已内置两个工作流：

- [daily_digest.yml](/E:/projects/ai-intake/.github/workflows/daily_digest.yml)
- [weekly_digest.yml](/E:/projects/ai-intake/.github/workflows/weekly_digest.yml)

用途：

- 每天北京时间 `08:30` 自动生成日报并发送飞书
- 每周一北京时间 `09:00` 自动生成周报并发送飞书
- 运行完成后会把 Markdown 报告作为 GitHub Actions Artifact 保存

### 需要配置的 GitHub Secrets

在 GitHub 仓库中进入：

`Settings` -> `Secrets and variables` -> `Actions`

新增这些 Secrets：

```text
OPENAI_BASE_URL
OPENAI_API_KEY
OPENAI_MODEL
FEISHU_WEBHOOK_URL
FEISHU_APP_ID
FEISHU_APP_SECRET
```

按你当前实际配置填写：

```text
OPENAI_BASE_URL = https://ai.hhhl.cc/v1
OPENAI_MODEL = gpt-5.4
```

`OPENAI_API_KEY` 填你的真实 key。

如果你把飞书相关密钥放在 `Environment secrets`，当前工作流默认绑定的 Environment 名称是 `personal`。
如果你的 Environment 不是这个名字，就把这两个工作流里的 `environment: personal` 改成你的实际环境名。

### GitHub Actions 使用说明

- GitHub Actions 不会读取你本机的 `.env`
- 它只会读取 GitHub Secrets
- 云端运行时不能使用你本机的 `Ollama localhost`
- 所以 GitHub Actions 方案固定建议使用 `openai_compatible`

### 手动触发

推送到 GitHub 后，可以在仓库页面手动点：

`Actions` -> `Daily AI Digest` -> `Run workflow`

或：

`Actions` -> `Weekly AI Digest` -> `Run workflow`

## 搜索式新闻源

如果你想把搜索式新闻采集也接进来，可以把下面这段加到 `sources.yaml`：

```yaml
search_news:
  - name: "AI Search Radar"
    type: news_search
    query: "OpenAI Google Meta Anthropic AI model launch release"
    authority_score: 72
    tags: [news, search, launch]
    region: "us-en"
    timelimit: "d"
    max_results: 5
    max_age_hours: 48
    enabled: true
```

这个源会做：

- DuckDuckGo 新闻搜索
- 发布时间校验
- 过滤非文章页、过时内容、tracker、evergreen 页面
- 基于事件去重

## 常用命令

```powershell
python -m src.main daily --verbose
python -m src.main daily --since 48h --limit 30
python -m src.main daily --no-summary --no-notify
python -m src.main weekly --since 7d
```

## 当前限制

- 当前不是 FastAPI 服务，没有 Web UI
- 当前主要以 CLI 和定时任务方式运行
- GitHub Actions 方案必须依赖云端可访问的模型接口

## 推荐使用顺序

1. 配好 `.env`
2. 先运行 `python -m src.main daily --no-notify`
3. 检查输出内容是否符合你的需求
4. 再启用飞书发送
5. 最后把代码推到 GitHub，启用 GitHub Actions 自动发送

## 相关文件

- [rules.yaml](/E:/projects/ai-intake/rules.yaml)
- [sources.yaml](/E:/projects/ai-intake/sources.yaml)
- [topics.yaml](/E:/projects/ai-intake/topics.yaml)
- [SCRAPEGRAPH_MIGRATION.md](/E:/projects/ai-intake/SCRAPEGRAPH_MIGRATION.md)
