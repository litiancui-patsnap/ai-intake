# 微信通知配置指南

本指南介绍如何将AI日报/周报自动推送到微信群。

---

## 方案1：企业微信群机器人（推荐⭐⭐⭐⭐⭐）

### 优点
- ✅ 官方支持，稳定可靠
- ✅ 完全免费
- ✅ 支持Markdown格式
- ✅ 推送速度快

### 缺点
- ❌ 需要企业微信账号（个人也可以免费注册）

### 配置步骤

#### 1. 注册企业微信
访问 https://work.weixin.qq.com/ 注册企业微信账号（个人也可以注册）

#### 2. 创建群聊并添加机器人
1. 在企业微信中创建一个群聊
2. 点击群聊右上角 `...` → `添加群机器人`
3. 选择 `新创建一个机器人`
4. 设置机器人名称（如：AI日报助手）
5. 复制生成的 **Webhook地址**

#### 3. 配置环境变量

**Windows PowerShell:**
```powershell
# 临时设置（当前会话有效）
$env:WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"

# 永久设置（系统环境变量）
[Environment]::SetEnvironmentVariable("WECOM_WEBHOOK_URL", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY", "User")
```

**Linux/Mac:**
```bash
# 临时设置
export WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"

# 永久设置（添加到 ~/.bashrc 或 ~/.zshrc）
echo 'export WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"' >> ~/.bashrc
source ~/.bashrc
```

#### 4. 启用通知

编辑 `rules.yaml`:
```yaml
notify:
  wecom_enabled: true
```

#### 5. 运行测试
```bash
python -m src.main daily --no-summary
```

如果配置正确，群里会收到日报推送！

---

## 方案2：Server酱（推荐⭐⭐⭐⭐）

### 优点
- ✅ 个人微信可用
- ✅ 配置简单
- ✅ 免费版每天5次推送

### 缺点
- ❌ 需要关注公众号
- ❌ 免费版有次数限制

### 配置步骤

#### 1. 注册Server酱
访问 https://sct.ftqq.com/sendkey 登录并获取 SendKey

#### 2. 关注公众号
使用微信扫码关注 "方糖服务号"

#### 3. 配置环境变量

**Windows:**
```powershell
$env:SERVERCHAN_SENDKEY="SCTxxxxxxxxxxxxxxxxxxxxx"

# 永久设置
[Environment]::SetEnvironmentVariable("SERVERCHAN_SENDKEY", "SCTxxxxxxxxxxxxxxxxxxxxx", "User")
```

**Linux/Mac:**
```bash
export SERVERCHAN_SENDKEY="SCTxxxxxxxxxxxxxxxxxxxxx"
echo 'export SERVERCHAN_SENDKEY="SCTxxxxxxxxxxxxxxxxxxxxx"' >> ~/.bashrc
```

#### 4. 启用通知

编辑 `rules.yaml`:
```yaml
notify:
  serverchan_enabled: true
```

#### 5. 运行测试
```bash
python -m src.main daily --no-summary
```

你会在微信公众号收到推送！

---

## 方案3：PushPlus（推荐⭐⭐⭐）

### 优点
- ✅ 个人微信可用
- ✅ 支持一对多推送
- ✅ 免费版每天200次

### 缺点
- ❌ 需要关注公众号

### 配置步骤

#### 1. 注册PushPlus
访问 https://www.pushplus.plus/push1.html 微信扫码登录

#### 2. 获取Token
登录后在 "发送消息" 页面找到你的 Token

#### 3. 配置环境变量

**Windows:**
```powershell
$env:PUSHPLUS_TOKEN="xxxxxxxxxxxxxxxxxxxx"

# 永久设置
[Environment]::SetEnvironmentVariable("PUSHPLUS_TOKEN", "xxxxxxxxxxxxxxxxxxxx", "User")
```

**Linux/Mac:**
```bash
export PUSHPLUS_TOKEN="xxxxxxxxxxxxxxxxxxxx"
echo 'export PUSHPLUS_TOKEN="xxxxxxxxxxxxxxxxxxxx"' >> ~/.bashrc
```

#### 4. 启用通知

编辑 `rules.yaml`:
```yaml
notify:
  pushplus_enabled: true
```

#### 5. 运行测试
```bash
python -m src.main daily --no-summary
```

---

## 同时使用多个通知渠道

你可以同时启用多个通知方式！

编辑 `rules.yaml`:
```yaml
notify:
  wecom_enabled: true        # 企业微信
  serverchan_enabled: true   # Server酱
  pushplus_enabled: false    # PushPlus禁用
```

同时设置对应的环境变量：
```powershell
$env:WECOM_WEBHOOK_URL="..."
$env:SERVERCHAN_SENDKEY="..."
```

---

## 关闭通知

### 临时关闭（命令行参数）
```bash
python -m src.main daily --no-summary --no-notify
```

### 永久关闭（配置文件）
编辑 `rules.yaml`:
```yaml
notify:
  wecom_enabled: false
  serverchan_enabled: false
  pushplus_enabled: false
```

---

## 自动化推送

### Windows任务计划程序

每天早上8点自动推送到企业微信：

```powershell
# 创建任务
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-Command `"cd e:\projects\ai-intake; .\venv\Scripts\activate; `$env:WECOM_WEBHOOK_URL='YOUR_WEBHOOK_URL'; python -m src.main daily --no-summary`"" `
    -WorkingDirectory "e:\projects\ai-intake"

$trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM

Register-ScheduledTask `
    -TaskName "AI-Intake-Daily-Notify" `
    -Action $action `
    -Trigger $trigger `
    -Description "每天早上8点生成AI日报并推送到企业微信"
```

### Linux/Mac Cron

```bash
# 编辑crontab
crontab -e

# 添加以下行（每天早上8点）
0 8 * * * export WECOM_WEBHOOK_URL='YOUR_WEBHOOK_URL' && cd /path/to/ai-intake && python -m src.main daily --no-summary >> /var/log/ai-intake.log 2>&1
```

---

## 推送内容说明

推送消息包含以下内容：

### 1. 统计信息
- 总条目数
- 必读条目数
- 高分推荐数

### 2. 必读条目（最多5条）
- 标题（可点击跳转）
- 来源
- 评分

### 3. 高分推荐（最多5条）
- 标题（可点击跳转）
- 来源
- 评分

### 示例效果

```
# AI日报 - 2025-12-31

## 🔥 必读 (3条)

- **[OpenAI发布GPT-5](https://...)**
  > 来源: OpenAI Research | 评分: 95

- **[Anthropic推出Claude 4](https://...)**
  > 来源: Anthropic Research | 评分: 92

## ⭐ 高分推荐 (8条)

- [LangChain 0.3.0 重大更新](https://...)
  > LangChain Blog | 85分

---
总计 23 条信息
```

---

## 故障排查

### Q1: 企业微信通知发送失败？

检查：
1. Webhook URL是否正确
2. 环境变量是否设置成功：`echo $env:WECOM_WEBHOOK_URL`
3. 网络是否正常

### Q2: Server酱没有收到推送？

检查：
1. 是否关注了公众号
2. SendKey是否正确
3. 是否超过每日限额（免费版5次/天）

### Q3: 想要自定义推送内容？

编辑 `src/notify/__init__.py` 中的消息构建逻辑。

---

## 进阶配置

### 只在有必读内容时推送

修改 `src/main.py`，在推送前检查：

```python
# 只有必读内容才推送
must_read = [item for item in items if item.is_must_read]
if must_read:
    results = notify.send_notifications(items, "daily", datetime.now(), notify_config)
```

### 定制推送时间

可以为不同时间段配置不同的推送方式：

```bash
# 工作日早上推送到企业微信
0 8 * * 1-5 ... WECOM_WEBHOOK_URL=... python -m src.main daily

# 周末推送到个人微信（Server酱）
0 9 * * 0,6 ... SERVERCHAN_SENDKEY=... python -m src.main daily
```

---

## 推荐配置

**工作场景**：企业微信群机器人
- 推送到团队群
- 方便讨论和分享

**个人使用**：Server酱
- 推送到个人微信
- 随时查看

**两者结合**：
- 企业微信：工作日早上8点
- Server酱：周末早上9点

---

需要更多帮助？查看 [README.md](README.md) 或提交 [Issue](https://github.com/litiancui-patsnap/ai-intake/issues)
