---
name: wechat-water-reminder
description: Create and manage fully customized, interactive water drinking reminder systems via WeChat or other channels. Use when the user says "喝水提醒", "设置喝水", "water reminder", "帮我提醒喝水", "定制喝水计划", or wants to create/modify/stop water intake tracking reminders. The skill first consults the user about their drinking background, goals, conditions, and frequency, then designs a personalized daily hydration plan, sets up push channels (WeChat by default), and runs a daily feedback loop: remind → ask for intake feedback → dynamically adjust remaining reminders → bedtime summary. Supports any target amount, any schedule, any channel the user prefers.
---

# WeChat Water Reminder — Customized Hydration Coach

## Overview
A fully personalized water-drinking reminder system. Not a one-size-fits-all plan. The skill first interviews the user, then designs a custom daily hydration schedule, deploys it via their preferred channel, and runs an interactive feedback loop every day.

## Trigger Conditions
Activate when user says any of:
- 喝水提醒, 设置喝水, water reminder, 帮我提醒喝水
- 定制喝水计划, 个性化喝水, 我的喝水计划
- 修改喝水, 更新喝水, 换喝水方案, 调整提醒
- 停止喝水提醒, 关掉喝水
- 查看喝水进度, 今天喝了多少, 喝水总结

## Philosophy
The user must **feel** how much they drink each day. Every message shows:
- **Today's total so far**
- **Progress toward daily goal**
- **Visual progress bar**
- **How much remains**

## Workflow

### Phase 1: Consultation (Key Node — Always Ask First)
Before creating anything, interview the user. Present questions clearly, one at a time or in a concise batch.

**Required questions:**
1. **喝水背景** (Background)
   - "你平时喝水习惯怎么样？容易忘记还是不喜欢喝？"
   - "有没有特殊情况？比如吃肌酸、健身、服药、孕期、医嘱限水？"
2. **喝水目标** (Goal)
   - "你每天想喝多少水？（单位：ml 或 杯）"
   - "有没有短期目标？比如改善皮肤、减脂、配合运动？"
3. **喝水条件** (Conditions)
   - "你用什么杯子？有刻度/吸管/大容量杯吗？"
   - "主要在什么场景喝水？家里、办公室、外出？"
   - "有没有固定无法喝水的时间？比如开会、通勤、午睡？"
4. **喝水频率/提醒偏好** (Frequency & Channel)
   - "你希望每天提醒几次？ roughly 几次？"
   - "提醒时间偏好？早上、工作时、饭后、睡前？"
   - "推送渠道？微信（默认）、QQ、短信、或其他？"

**Consultation output:**
Compile into a brief "喝水档案" and present to user for confirmation:

```
你的定制喝水计划预览：
━━━━━━━━━━━━━━━━━━━━━━
🎯 日目标：{X}ml（约{X/250}杯）
⏰ 提醒时间：{时间列表}
📱 推送渠道：{渠道}
📝 特殊备注：{肌酸/健身/医嘱等}
━━━━━━━━━━━━━━━━━━━━━━
确认后生效，明天开始推送。
```

### Phase 2: Plan Design
Based on consultation, design the schedule:

**Default design principles:**
- Morning (09:00): Start the day, 1 large drink
- Noon (12:00): **Checkpoint — ask for morning feedback**
- Afternoon (13:00): Post-l refill
- Evening (18:00): **Checkpoint — ask for afternoon feedback**
- Night (21:00): Final push toward goal
- Bedtime (22:30): **Summary — today's total + tomorrow preview**

**Adjust based on user conditions:**
- Office worker → reminders aligned with work breaks
- Gym days → extra reminder pre/post workout
- Creatine user → 17:00 creatine + water reminder
- Hates plain water → suggest infusion, tea, count those
- Small cup → more frequent, smaller amounts
- Always forgets → aggressive morning push, evening catch-up

### Phase 3: Deploy Cron Jobs
Write to `~/.openclaw/cron/jobs.json`:
- `water-reminder-daytime`: cron expr matching planned times
- `water-reminder-night`: bedtime summary (22:30 default, adjustable)
- Payload calls `water_tracker.py` to generate dynamic messages

Initialize state: `python3 scripts/water_tracker.py init --target {X}`

### Phase 4: Daily Interactive Loop

**Every reminder message must include:**
```
🥤 喝水提醒
━━━━━━━━━━━━━━━━━━━━━━
███░░░░░░░ 500ml / 1500ml (33%)

⏰ 本次：喝 {amount}ml
🎯 还剩：{remaining}ml
━━━━━━━━━━━━━━━━━━━━━━

喝完后回复我数字，我帮你记录。
```

**Checkpoint reminders (12:00, 18:00):**
```
⏰ 喝水检查
━━━━━━━━━━━━━━━━━━━━━━
███░░░░░░░ 500ml / 1500ml (33%)

上午/下午的目标 {target}ml 喝了多少？
请回复具体数字（如：300），我调整后面的提醒。
```

**User replies with number → record:**
```bash
python3 scripts/water_tracker.py record {amount}
```

**Bedtime summary (22:30):**
```
🌙 今日喝水总结
━━━━━━━━━━━━━━━━━━━━━━
████████░░ 1300ml / 1500ml (86%)

✅ 达成率：86%
📊 分段记录：上午500 | 下午400 | 晚间300 | 睡前100
📝 明日建议：上午多喝100ml，争取100%达标
━━━━━━━━━━━━━━━━━━━━━━

明天继续当前计划？回复"继续"或"调整"。
```

### Phase 5: Next-Day Kickoff
If user replies "继续" → re-init state, same plan
If user replies "调整" → return to Phase 1 consultation

## Scripts
- `scripts/water_tracker.py`: State management + message generation
  - `init --target X`: Reset daily state with custom target
  - `record AMOUNT`: Log user-reported ml
  - `status`: Show current state JSON
  - `message HH:MM`: Generate reminder text for that time slot
  - `summary`: Generate bedtime summary

State file: `~/.openclaw/workspace/scripts/.daily_water_state.json`

## Channel Setup
**Default: WeChat (`openclaw-weixin`)**
- If not configured, guide user through `openclaw channels login --channel openclaw-weixin`
- If user prefers other channel (QQ/短信), note it and warn about available integrations

**Fallback if WeChat down:**
- Log error
- Try alternative channel if configured
- Notify user next time they chat

## Message Design Rules
1. **Every message shows total + progress bar + remaining**
2. **Checkpoint messages explicitly ask for feedback**
3. **Use simple numbers, no decimals**
4. **Friendly, not nagging. Celebrate progress.**
5. **Bedtime summary is mandatory, not optional**

## Edge Cases
- User replies non-numeric at checkpoint: ask again gently
- No reply before next reminder: assume default phase amount, continue
- User says "今天不喝了": set remaining to 0, send "收到，休息一天"
- State file corrupted: auto-init with default target
- User changes goal mid-day: run `init --target NEW_AMOUNT`, inform user reset
- Channel unavailable: queue messages, retry on next heartbeat

## Example Consultation Flow

**User**: "帮我设置喝水提醒"

**Assistant**:
```
好，先了解一下你的情况：

1. 你平时喝水习惯怎么样？容易忘还是不喜欢喝？
2. 每天想喝多少？（一般建议1500-2000ml）
3. 有没有特殊情况？比如健身、吃肌酸、服药？
4. 希望什么时间提醒？（默认：09:00/12:00/13:00/18:00/21:00/22:30）
5. 推送渠道：微信可以吗？

回复任意一条，我们边聊边定。
```

**User**: "我健身，吃肌酸，目标2L，微信"

**Assistant**:
```
收到。定制计划预览：
━━━━━━━━━━━━━━━━━━━━━━
🎯 日目标：2000ml
⏰ 提醒：09:00/12:00/13:00/17:00(肌酸)/18:00/21:00/22:30
📱 渠道：微信
📝 备注：17:00肌酸+300ml水
━━━━━━━━━━━━━━━━━━━━━━

确认后明天生效。回复"确认"。
```

**User**: "确认"

**Assistant**: Deploys cron jobs, confirms next push time.
