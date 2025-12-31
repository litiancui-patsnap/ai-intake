# 快速上手指南

## 5分钟快速体验

### 步骤 1: 安装

```bash
# 克隆仓库
git clone https://github.com/yourname/ai-intake.git
cd ai-intake

# 安装依赖
pip install -r requirements.txt
```

### 步骤 2: 首次运行（无LLM）

```bash
# 生成日报（不使用LLM，使用extractive摘要）
python -m src.main daily --no-summary --dry-run

# 查看输出
cat outputs/daily/$(date +%Y-%m-%d).md
```

### 步骤 3: 配置LLM（可选）

```bash
# 设置OpenAI API密钥
export OPENAI_API_KEY="sk-..."

# 使用LLM生成摘要
python -m src.main daily --dry-run
```

### 步骤 4: 正式运行

```bash
# 去掉 --dry-run，数据将保存到数据库
python -m src.main daily

# 生成周报
python -m src.main weekly
```

## 典型工作流

### 场景 1: 每日早晨阅读

```bash
# 早上运行（或配置cron自动运行）
python -m src.main daily

# 在Obsidian或Notion中打开
open outputs/daily/$(date +%Y-%m-%d).md
```

### 场景 2: 周末回顾

```bash
# 生成本周周报
python -m src.main weekly

# 查看趋势和必做事项
open outputs/weekly/$(date +%Y)-W$(date +%V).md
```

### 场景 3: 调整个人偏好

编辑 `rules.yaml`:

```yaml
preferences:
  # 更关注这些公司
  priority_vendors:
    - "OpenAI"
    - "Anthropic"
    - "Mistral"  # 新增

  # 更关注这些主题
  priority_topics:
    - "Inference"
    - "Serving"
    - "FineTuning"  # 新增
```

重新运行后，相关条目会获得更高评分。

### 场景 4: 添加新信息源

编辑 `sources.yaml`:

```yaml
community:
  - name: "Hugging Face Daily Papers"
    type: rss
    url: "https://huggingface.co/papers/rss"
    authority_score: 80
    tags: [research, papers]
    enabled: true
```

## 常用命令

```bash
# 查看最近48小时，限制30条
python -m src.main daily --since 48h --limit 30

# 测试配置（不写数据库）
python -m src.main daily --dry-run --verbose

# 节省API费用（跳过LLM）
python -m src.main daily --no-summary

# 导出JSONL格式（用于其他工具）
python -m src.main daily --export-jsonl
```

## 下一步

- 阅读 [DESIGN.md](DESIGN.md) 了解系统架构
- 阅读 [README.md](README.md) 了解完整功能
- 查看 `sources.yaml`, `topics.yaml`, `rules.yaml` 进行定制化

## 故障排查

### 问题: 采集失败

```bash
# 启用详细日志
python -m src.main daily --verbose

# 查看具体哪个源失败
# 日志会显示: "采集失败 <source_name>: <error>"

# 临时禁用失败的源
# 编辑 sources.yaml，设置 enabled: false
```

### 问题: 没有生成报告

```bash
# 检查是否采集到数据
python -m src.main daily --dry-run --verbose

# 查看过滤条件是否太严格
# 编辑 rules.yaml，降低 min_score
```

### 问题: LLM错误

```bash
# 检查API密钥
echo $OPENAI_API_KEY

# 跳过LLM
python -m src.main daily --no-summary
```

## 最佳实践

1. **先测试后正式**: 使用 `--dry-run` 测试配置
2. **渐进式调整**: 先运行默认配置，再逐步定制
3. **定期检查**: 每周检查评分准确性，调整规则
4. **备份数据库**: 定期备份 `ai-intake.db`
5. **版本控制配置**: 将配置文件加入git，跟踪变更

## 进阶技巧

### 技巧 1: 多配置文件

```bash
# 创建不同场景的配置
cp -r . ai-intake-research
cp -r . ai-intake-engineering

# 分别定制 sources.yaml 和 topics.yaml
cd ai-intake-research && python -m src.main daily
cd ai-intake-engineering && python -m src.main daily
```

### 技巧 2: 自定义评分权重

针对不同角色调整 `rules.yaml`:

**研究员**:
```yaml
scoring:
  weights:
    research_signal: 0.40  # 提高
    engineering_signal: 0.20  # 降低
```

**工程师** (默认):
```yaml
scoring:
  weights:
    research_signal: 0.25
    engineering_signal: 0.35
```

### 技巧 3: 批量历史回顾

```bash
# 查看过去一个月的数据
sqlite3 ai-intake.db "
  SELECT date(published), COUNT(*), AVG(score)
  FROM items
  WHERE published > date('now', '-30 days')
  GROUP BY date(published)
  ORDER BY date(published) DESC;
"
```

## 获取帮助

- GitHub Issues: https://github.com/yourname/ai-intake/issues
- 阅读设计文档: [DESIGN.md](DESIGN.md)
- 查看示例配置: `sources.yaml`, `topics.yaml`, `rules.yaml`
