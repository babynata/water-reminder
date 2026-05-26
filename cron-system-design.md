# 定时任务系统设计规范（截至 2026-05-26）

> 适用于 OpenClaw + 微信通道的自动化推送系统  
> 作者：麻辣虾尾

---

## 一、架构总览

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Gateway   │────▶│  Cron Worker │────▶│  Python脚本 │
│  (调度器)    │     │  (isolated)  │     │ (业务逻辑)  │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                  │
                    ┌──────────────┐              │
                    │  主 Session   │◀─────────────┘
                    │ (调度+汇报)   │   用户回复 → 写 state
                    └──────────────┘
```

**关键原则：**
- **每个任务必须对应一个 `.py` 脚本**，禁止在 cron payload 里写内联逻辑
- **所有脚本必须集成 `cron_logger.py`**，记录执行状态
- **主 session 不直接执行任务**，只调度 + 汇报
- **Worker 通过 `sessions_spawn` 执行异步/复杂任务**，隔离失败

---

## 二、三层状态分离

| 层级 | 存储位置 | 读写方 | 说明 |
|------|---------|--------|------|
| **无状态任务** | 脚本内嵌配置 / `config.json` | Worker 自给自足 | 五行分析、AI 周刊：每次运行独立，不依赖历史 |
| **有状态任务** | `state/*.json` | 主写、Worker 读 | 喝水追踪、脊柱提醒：跨周期数据传递 |
| **人类记忆** | `memory/*.md`、`MEMORY.md` | 主 session 独占 | Worker 不触碰，保护隐私 |

**共享方式：** Worker workspace 保持独立，通过绝对路径 `~/.openclaw/workspace/state/*.json` 访问共享状态区。

---

## 三、原子状态读写（并发安全）

**实现文件：** `scripts/state_tool.py`

**机制：**
1. **写**：temp 文件 → `fsync` → `LOCK_EX` → `os.rename` 原子替换 → 释放锁
2. **读**：`LOCK_SH` → 读取 → 释放 → 重试 3 次
3. **冲突处理**：读写重叠时，Worker 要么读到旧版要么读到新版，**永看不到半成品**

**核心规则：**
- 主 session 写 state（用户回复后更新）
- Worker 读 state（生成提醒消息）
- `water_tracker.py` 的 `cmd_record` 必须显式走 `load_state()` 日期检查流程，禁止绕过 `update_state` 直接追加到旧 state

---

## 四、统一日志系统

**实现文件：** `scripts/cron_logger.py`

### 4.1 执行日志（Execution Log）

```python
def log_execution(job_id, cmd, status, stdout, stderr, duration_ms)
```

**记录内容：**
- 时间戳、执行状态（success/error）
- 完整命令字符串
- stdout（脚本输出）
- stderr（错误信息）
- 耗时（毫秒）

**文件：** `logs/{job_id}.log`

### 4.2 聚合摘要（Summary）

**文件：** `logs/cron-summary.json`

```json
{
  "water-reminder-daytime": {
    "last_run": "2026-05-26T12:00:10+08:00",
    "last_status": "success",
    "consecutive_success": 7,
    "consecutive_errors": 0,
    "total_runs": 7
  }
}
```

### 4.3 连续失败告警（Alerts）

**触发条件：** 连续失败 ≥3 次

**文件：** `logs/cron-alerts.json`

```json
[
  {
    "job_id": "daily-wuxing-cron-001",
    "alert_time": "2026-05-20T09:05:00+08:00",
    "message": "连续失败 16 次",
    "last_error": "Channel is required when multiple channels are configured"
  }
]
```

### 4.4 微信推送追踪（Delivery Log）

**新增（2026-05-26）：** 记录 `message()` 工具的返回状态

```python
def log_delivery(job_id, message_id, status="sent", error="")
```

**记录内容：**
- 时间戳、发送状态（sent/failed）
- `messageId`（微信返回的唯一标识）
- 失败原因（如有）

**追加到：** `logs/{job_id}.log` 末尾

**CLI 调用：**
```bash
python3 scripts/cron_logger.py delivery water-reminder-daytime \
  openclaw-weixin:xxx sent
```

---

## 五、Cron 任务 Payload 设计

### 5.1 两步完成原则

```
1. 运行脚本获取内容
2. 发送结果到微信
3. （新增）记录 delivery 状态
```

**禁止：** 让 agent 额外生成内容（脚本已输出完整报告，直接发送即可）

### 5.2 多通道配置修复

**问题：** 当系统配置多个通道（feishu/weixin/kimi-claw）时，`delivery: null` 会导致 `Channel is required` 错误

**修复：** 每个 cron job 必须显式指定 `delivery`：
```json
{
  "delivery": {
    "channel": "openclaw-weixin",
    "to": "o9cq80_B0lSf5g4qI_Yq_kLkaGAc@im.wechat",
    "mode": "send"
  }
}
```

### 5.3 Gateway 重启验证

**注意：** `openclaw gateway restart` 返回 exit code 1（配置警告）**不等于启动失败**

**正确验证：**
```bash
pgrep -f "openclaw gateway"   # 确认进程存在
python3 scripts/cron_logger.py summary  # 确认 cron 调度正常
```

---

## 六、任务拆分与 Subagent 使用

### 6.1 区分两种机制

| 机制 | 谁触发 | 怎么创建 | 生命周期 | 用途 |
|------|--------|---------|---------|------|
| **`sessions_spawn`** | 主 session 主动调用 | 我敲 `sessions_spawn` 工具 | 我管着它，可发指令、收结果 | 异步长任务、上下文隔离、并发执行 |
| **Cron `agentId: worker`** | Gateway 自动触发 | 闹钟响了 gateway 自己开 | 跑完就销毁，我不直接控制 | 定时推送、无需人工干预 |

### 6.2 适用场景

- **Cron job**：定时推送（五行分析、喝水提醒、AI 周刊），无需实时交互
- **Spawn**：需要主 session 实时反馈的任务（如"帮我分析这个文件"）

---

## 七、故障排查清单

### 7.1 常见问题

| 现象 | 排查步骤 |
|------|---------|
| 推送没收到 | 1. 查 `logs/{job_id}.log` 脚本是否执行成功 2. 查末尾是否有 `DELIVERY` 记录 3. 查 `cron-summary.json` 连续失败次数 |
| 连续失败 | 1. 查 `logs/cron-alerts.json` 2. 查 stderr 中的错误信息 3. 常见原因：`delivery.channel` 未配置、脚本语法错误、API rate limit |
| 数据不对 | 1. 查 `state/*.json` 的 date 字段是否过期 2. 确认是否走了 `load_state()` 日期检查 |
| Gateway 重启失败 | `pgrep -f "openclaw gateway"` 确认进程存在，不要只看 exit code |

### 7.2 快速查询命令

```bash
# 查看所有任务状态
python3 -c "from workspace.scripts.cron_logger import get_summary; import json; print(json.dumps(get_summary(), indent=2, ensure_ascii=False))"

# 查看告警
python3 -c "from workspace.scripts.cron_logger import get_alerts; import json; print(json.dumps(get_alerts(), indent=2, ensure_ascii=False))"

# 查看某任务详细日志
tail -20 ~/.openclaw/workspace/logs/water-reminder-daytime.log

# 查看 cron 配置
cat ~/.openclaw/cron/jobs.json
```

---

## 八、文件清单

| 文件 | 作用 | 状态 |
|------|------|------|
| `scripts/daily_wuxing.py` | 五行分析+求职建议+首饰推荐 | ✅ 含日志 |
| `scripts/water_tracker.py` | 喝水状态追踪+提醒消息生成 | ✅ 含日志 |
| `scripts/weekly_newsletter.py` | AI 周刊读取+分段输出 | ✅ 含日志 |
| `scripts/spine_reminder.py` | 脊柱预约提醒生成 | ✅ 含日志 |
| `scripts/cron_logger.py` | **统一日志记录器**（execution + summary + alerts + delivery） | ✅ |
| `scripts/state_tool.py` | 原子状态读写（fcntl 锁） | ✅ |
| `state/water.json` | 每日喝水记录 | ✅ |
| `state/spine.json` | 脊柱预约状态 | ✅ |
| `logs/cron-summary.json` | 聚合执行状态 | ✅ |
| `logs/cron-alerts.json` | 连续失败告警 | ✅ |
| `logs/{job_id}.log` | 各任务详细执行日志+delivery追踪 | ✅ |
| `cron/jobs.json` | Cron 任务配置（含 payload + delivery） | ✅ |

---

*整理完成于 2026-05-26*  
*当前运行任务：五行分析、喝水提醒、AI 周刊（每周一）、脊柱提醒（每周六）*