# TOOLS.md - Local Notes

## Cron Jobs

| ID | Name | Schedule | Target | Channel | Status |
|----|------|----------|--------|---------|--------|
| daily-wuxing-cron-001 | 每日五行分析与求职建议 | 09:00 daily（推送明天） | isolated | weixin | ✅ active | **worker** |
| weekly-ai-newsletter-cron-001 | 每周AI周刊推送 | 08:00 Mon | isolated | weixin | ✅ active | **worker** |
| water-reminder-daytime | 喝水提醒 | 09:00/12:00/13:00/18:00/21:00/23:00 daily | isolated | weixin | ✅ active | **worker** |
| spine-health-reminder | 脊柱健康号预约提醒 | 17:00 Sat | isolated | weixin | ✅ active | **worker** |

- Config: `~/.openclaw/cron/jobs.json`
- 五行脚本: `~/.openclaw/workspace/scripts/daily_wuxing.py`
- AI周刊脚本: `~/.openclaw/workspace/scripts/weekly_newsletter.py`
- 脊柱提醒脚本: `~/.openclaw/workspace/scripts/spine_reminder.py`
- AI周刊模板: `~/.openclaw/workspace/AI周刊_模板.md`

## Channels

| Channel | Status | Config Location | Notes |
|---------|--------|----------------|-------|
| kimi-claw | ✅ active | openclaw.json plugins | 主对话通道 |
| weixin (微信) | ✅ active | openclaw-weixin plugin | 通过Kimi Claw一键接入 |
| feishu (飞书) | ⚠️ limited | openclaw-lark plugin | 权限不足，无法创建文档/表格 |

### Feishu Permission Issues
Missing permissions:
- `docx:document:create` - 无法创建文档
- `docx:document:write_only` - 无法写入文档
- `wiki:node:create` - 无法创建Wiki
- `sheets:spreadsheet:create` - 无法创建表格
- `docs:document.media:upload` - 无法上传媒体

Requires admin to enable at https://open.feishu.cn/

## Scripts

| Script | Purpose | Location | 状态文件 | 日志 |
|--------|---------|----------|---------|------|
| daily_wuxing.py | 计算当日干支+五行+吉凶评级+建议 | `workspace/scripts/` | 无（无状态） | ✅ `cron_logger.py` |
| water_tracker.py | 喝水状态追踪器（动态提醒+进度条+用户反馈） | `workspace/scripts/` | `state/water.json` | ✅ `cron_logger.py` |
| weekly_newsletter.py | AI 周刊推送（读取 Markdown 分段输出） | `workspace/scripts/` | 无 | ✅ `cron_logger.py` |
| spine_reminder.py | 脊柱预约提醒（读取 spine.json 生成消息） | `workspace/scripts/` | 无 | ✅ `cron_logger.py` |
| cron_logger.py | **统一日志记录器**：捕获 stdout/stderr、记录执行状态、连续失败告警 | `workspace/scripts/` | `logs/cron-summary.json` `logs/cron-alerts.json` | — |

### Cron 任务规范（必须遵守）

1. **脚本化**：所有 cron 任务必须对应一个 `.py` 脚本，禁止在 payload 里直接写内联逻辑
2. **加日志**：脚本入口必须集成 `cron_logger.py`，捕获 stdout/stderr、记录执行状态
3. **错误告警**：连续失败 ≥3 次时，`cron-alerts.json` 自动标记，主 session 通过 `get_alerts()` 可查询
4. **Delivery 追踪**：cron payload 第 3 步必须记录 `message()` 返回的 messageId
5. **日志位置**：`~/.openclaw/workspace/logs/` — 各任务 `.log` 详细日志 + `cron-summary.json` 聚合 + `cron-alerts.json` 告警

**已打包为 Skill：** `~/.openclaw/workspace/skills/cron-state-manager/`  
**GitHub：** https://github.com/babynata/cron-state-manager

日志查询命令：
```bash
# 查看汇总
python3 -c "from workspace.scripts.cron_logger import get_summary; import json; print(json.dumps(get_summary(), indent=2, ensure_ascii=False))"

# 查看告警
python3 -c "from workspace.scripts.cron_logger import get_alerts; import json; print(json.dumps(get_alerts(), indent=2, ensure_ascii=False))"
```

## State 文件（结构化状态，主 session + Worker 共享）

| 文件 | 用途 | 读写方 |
|------|------|--------|
| `state/water.json` | 每日喝水记录（records数组、total_ml、target_ml） | 主 session 写（用户回复后更新），Worker 读（生成提醒消息） |
| `state/spine.json` | 脊柱预约状态（下次就诊日期、用户确认、提醒计数） | 主 session 写（用户回复后更新），Worker 读（判断是否需要提醒） |

### State 文件设计原则

- **无状态任务**（五行分析、AI周刊）：配置内嵌脚本，不读写 state
- **有状态任务**（喝水提醒、脊柱预约）：用结构化 `state/*.json` 做跨周期数据传递
- **人类记忆**（`memory/*.md`、`MEMORY.md`、`USER.md`）：主 session 专属，Worker 不触碰
- **共享方式**：Worker workspace 保持独立，但通过绝对路径 `~/.openclaw/workspace/state/*.json` 访问共享状态区

### water.json Schema

```json
{
  "date": "2026-05-22",
  "target_ml": 1500,
  "records": [
    {"time": "09:00", "amount": 450, "source": "user_report"},
    {"time": "12:04", "amount": 450, "source": "user_report"}
  ],
  "total_ml": 900,
  "last_updated": "2026-05-22T12:04:00+08:00"
}
```

### spine.json Schema

```json
{
  "next_appointment_date": "2026-05-24",
  "last_reminder_sent": "2026-05-17T17:00:00+08:00",
  "user_confirmed": false,
  "reminder_count": 3
}
```

### 并发安全

使用 `scripts/state_tool.py` 原子读写：
- **写**：temp → fsync → LOCK_EX → rename → 释放锁
- **读**：LOCK_SH → 读 → 释放 → 重试3次
- **冲突场景**：主写从读重叠时，Worker 要么读到旧版要么读到新版，永看不到半成品

### Skill 化

已打包为 `cron-state-manager` skill：
- 路径：`~/.openclaw/workspace/skills/cron-state-manager/`
- 包含：SKILL.md、scripts/state_tool.py、references/architecture.md、references/state-schemas.md
- 打包文件：`cron-state-manager.skill`

## Workspace Structure

```
~/.openclaw/workspace/
├── memory/
│   ├── 2026-05-08.md          # 今日日志
│   └── YYYY-MM-DD.md          # 每日日志（自动创建）
├── knowledge-base/
│   └── product-kb.md          # AI PM知识库框架（本地版）
├── scripts/
│   ├── daily_wuxing.py        # 五行分析脚本
│   └── daily_wuxing_send.sh   # 发送脚本（备用）
├── AGENTS.md                  # 工作规范
├── MEMORY.md                  # 长期记忆
├── USER.md                    # 用户档案
├── SOUL.md                    # 个性设定
├── TOOLS.md                   # 本文件
├── HEARTBEAT.md               # 心跳任务清单
└── AI周刊_2026W*.md           # AI周刊存档（每周一更新）
```

## Useful Commands

```bash
# 手动运行五行分析
python3 ~/.openclaw/workspace/scripts/daily_wuxing.py

# 查看cron配置
cat ~/.openclaw/cron/jobs.json

# 查看gateway状态
openclaw gateway status

# 重启gateway
openclaw gateway restart

# 查看系统日志
tail -f ~/.openclaw/logs/openclaw.log
```

## Session Management Notes

- **Context limit**: 131k tokens
- **Current session usage**: ~95k at end of 2026-05-08 session (72%)
- **Compression mode**: safeguard（自动压缩早期对话）
- **Risk**: 高密度命理分析+技术配置对话容易导致context爆炸
- **Mitigation**: 每次session结束时主动落盘关键信息到memory/

*Last updated: 2026-05-26 12:45 CST*

## 2026-05-20 五行推送故障修复

**故障时间**: 2026-05-20 09:00
**故障现象**: API rate limit + 微信通道未配置，导致五行推送失败
**根因**: isolated session 中 agent 生成完整报告消耗大量 token，触发 rate limit
**修复方案**: 
1. 增强 `daily_wuxing.py` 脚本，直接输出完整报告（含综合判断/求职建议/穿衣方位/忌宜/一句话）
2. 简化 cron payload，只执行脚本+发送输出，不再让 agent 生成内容
3. 预计执行时间从 166秒 降至 <10秒
