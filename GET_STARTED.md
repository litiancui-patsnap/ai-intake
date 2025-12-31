# 立即开始使用 - AI信息摄入系统

## ✅ 系统已就绪！

恭喜！系统已成功安装并开始运行。首次运行正在后台进行中...

---

## 📋 快速命令参考

### Windows (当前环境)

```powershell
# 进入项目目录
cd e:\projects\ai-intake

# 激活虚拟环境
.\venv\Scripts\activate

# 运行日报（推荐：不使用LLM，节省成本）
python -m src.main daily --no-summary

# 运行日报（使用LLM生成AI摘要）
$env:OPENAI_API_KEY="sk-..."
python -m src.main daily

# 运行周报
python -m src.main weekly

# 测试模式（不写数据库）
python -m src.main daily --dry-run --no-summary

# 详细日志
python -m src.main daily --verbose --no-summary
```

### Linux/Mac

```bash
# 进入项目目录
cd ai-intake

# 激活虚拟环境
source venv/bin/activate

# 运行日报
python -m src.main daily --no-summary

# 其他命令同Windows
```

---

## 📊 查看首次运行结果

```powershell
# 查看今天的日报
notepad outputs\daily\2025-12-29.md

# 或用您喜欢的编辑器
code outputs\daily\2025-12-29.md
```

---

## ⚙️ 个性化配置（可选）

### 1. 调整关注主题

编辑 `rules.yaml`:

```yaml
preferences:
  # 更关注这些公司（每个+3分）
  priority_vendors:
    - "OpenAI"
    - "Anthropic"
    - "Mistral"      # 新增

  # 更关注这些工具（每个+2分）
  priority_tools:
    - "LangChain"
    - "vLLM"
    - "Cursor"       # 新增

  # 更关注这些主题（每个+2分）
  priority_topics:
    - "Inference"
    - "Serving"
    - "FineTuning"   # 新增
```

### 2. 调整评分权重

编辑 `rules.yaml`:

```yaml
scoring:
  weights:
    research_signal: 0.20     # 降低研究权重
    engineering_signal: 0.40  # 提高工程权重到40%
    authority: 0.20
    freshness: 0.10
    preference: 0.10
```

### 3. 添加新信息源

编辑 `sources.yaml`:

```yaml
community:
  - name: "Your Favorite Blog"
    type: rss
    url: "https://example.com/feed.xml"
    authority_score: 75
    tags: [community, ai]
    enabled: true
```

---

## 🕐 设置定时运行

### Windows Task Scheduler

```powershell
# 创建每天早上8点运行的任务
$action = New-ScheduledTaskAction -Execute "python" -Argument "-m src.main daily --no-summary" -WorkingDirectory "e:\projects\ai-intake"
$trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM
Register-ScheduledTask -TaskName "AI-Intake-Daily" -Action $action -Trigger $trigger
```

### Linux/Mac Cron

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天早上8点）
0 8 * * * cd /path/to/ai-intake && /usr/bin/python3 -m src.main daily --no-summary >> /var/log/ai-intake.log 2>&1
```

---

## 🔧 常见问题处理

### Q1: 部分信息源采集失败

**这是正常的！** 系统已配置容错机制，部分失败不影响整体。

查看日志中的错误：
- `404 Not Found`: URL已失效，可在 `sources.yaml` 中禁用
- `SSL/网络错误`: 临时网络问题，下次运行会重试

**解决方案**：
1. 禁用失败的源：编辑 `sources.yaml`，设置 `enabled: false`
2. 或更新URL（某些源可能已更换地址）

### Q2: 如何只生成特定主题的报告

修改 `rules.yaml`:

```yaml
filter_rules:
  # 新增：只保留特定主题
  - condition: "not any(tag in ['LLM', 'Inference', 'Agent'] for tag in tags)"
    reason: "非关注主题"
```

### Q3: 输出文件在哪里

```
outputs/
├── daily/
│   └── 2025-12-29.md    # 今天的日报
└── weekly/
    └── 2025-W52.md      # 本周的周报
```

### Q4: 如何启用LLM摘要

```powershell
# 设置环境变量（每次会话需重新设置）
$env:OPENAI_API_KEY="sk-..."

# 或永久设置（系统环境变量）
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "User")

# 然后运行（去掉 --no-summary）
python -m src.main daily
```

---

## 📚 深入学习

- **完整文档**: [README.md](README.md)
- **系统架构**: [DESIGN.md](DESIGN.md)
- **快速上手**: [QUICKSTART.md](QUICKSTART.md)
- **输出示例**: [EXAMPLE_OUTPUT.md](EXAMPLE_OUTPUT.md)
- **项目结构**: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

---

## 🎯 推荐工作流

### 工作日早晨（5分钟）

```powershell
# 1. 生成日报
python -m src.main daily --no-summary

# 2. 在编辑器中打开
code outputs\daily\$(Get-Date -Format 'yyyy-MM-dd').md

# 3. 快速扫描"必读"部分（~2分钟）
# 4. 浏览感兴趣的主题（~3分钟）
```

### 周末回顾（15分钟）

```powershell
# 1. 生成周报
python -m src.main weekly

# 2. 查看本周趋势和必做事项
code outputs\weekly\$(Get-Date -UFormat '%Y-W%V').md

# 3. 深入阅读3-5条重点内容
# 4. 制定下周学习/实验计划
```

---

## 🚀 下一步建议

1. **等待首次运行完成**（约5-10分钟）
2. **查看生成的日报**：`outputs\daily\2025-12-29.md`
3. **根据兴趣调整配置**：编辑 `rules.yaml` 的 `preferences`
4. **设置定时任务**：每天自动运行
5. **集成到工作流**：Obsidian/Notion同步

---

## 💡 小技巧

### 技巧1: 快速查找特定公司的消息

```powershell
# 搜索今天日报中的 OpenAI 相关内容
Select-String -Path "outputs\daily\2025-12-29.md" -Pattern "OpenAI"
```

### 技巧2: 导出JSONL用于其他工具

```powershell
python -m src.main daily --export-jsonl --no-summary

# JSONL文件位置
cat outputs\daily\2025-12-29.jsonl
```

### 技巧3: 查看历史数据

```powershell
# 安装 sqlite3（如果需要）
# 查询数据库
sqlite3 ai-intake.db "SELECT title, score FROM items ORDER BY score DESC LIMIT 10"
```

---

## 🎉 开始享受低噪音的AI信息流！

每天15分钟，掌握AI领域最重要的动态。

有问题？查看 [README.md](README.md) 或 [DESIGN.md](DESIGN.md)
