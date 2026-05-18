import json
import os
import sys
from datetime import datetime
import pytz

STATE_FILE = os.path.expanduser("~/.openclaw/workspace/scripts/.daily_water_state.json")
TZ = pytz.timezone("Asia/Shanghai")
DAILY_TARGET = 1500  # ml

# 每个时间段默认应喝量（用于计算进度）
TIME_SLOTS = {
    "09:00": {"label": "第1杯", "default": 500, "phase": "morning"},
    "12:00": {"label": "检查", "default": 0, "phase": "morning_check"},
    "13:00": {"label": "第2杯", "default": 500, "phase": "afternoon"},
    "18:00": {"label": "检查", "default": 0, "phase": "afternoon_check"},
    "21:00": {"label": "第3杯", "default": 300, "phase": "evening"},
    "22:30": {"label": "睡前", "default": 100, "phase": "night"},
}

PHASES = ["morning", "afternoon", "evening", "night"]
PHASE_TARGETS = {
    "morning": 500,
    "afternoon": 500,
    "evening": 300,
    "night": 100,
}


def load_state():
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    if not os.path.exists(STATE_FILE):
        return {"date": today, "total": 0, "records": {}, "replies": {}}
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
    if state.get("date") != today:
        return {"date": today, "total": 0, "records": {}, "replies": {}}
    return state


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_progress_bar(total, target=DAILY_TARGET):
    pct = min(total / target, 1.0)
    filled = int(pct * 10)
    empty = 10 - filled
    bar = "█" * filled + "░" * empty
    return f"{bar} {total}ml / {target}ml ({int(pct*100)}%)"


def cmd_init():
    state = load_state()
    save_state(state)
    print("Initialized")


def cmd_record(amount):
    state = load_state()
    now = datetime.now(TZ).strftime("%H:%M")
    state["replies"][now] = amount
    state["total"] = sum(state["replies"].values())
    save_state(state)
    print(f"Recorded {amount}ml. Total today: {state['total']}ml")


def cmd_status():
    state = load_state()
    print(json.dumps(state, ensure_ascii=False))


def cmd_message(time_key):
    state = load_state()
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    slot = TIME_SLOTS.get(time_key)
    if not slot:
        print(f"Unknown time key: {time_key}")
        return

    total = state.get("total", 0)
    remaining = max(DAILY_TARGET - total, 0)
    phase = slot["phase"]

    # 12:00 - ask for morning intake
    if time_key == "12:00":
        msg = (
            f"⏰ 喝水检查（中午）\n\n"
            f"{get_progress_bar(total)}\n\n"
            f"上午的500ml水喝了多少？\n"
            f"请回复我具体数字（如：300），我会调整下午和晚上的提醒。"
        )
        print(msg)
        return

    # 18:00 - ask for afternoon intake
    if time_key == "18:00":
        msg = (
            f"⏰ 喝水检查（傍晚）\n\n"
            f"{get_progress_bar(total)}\n\n"
            f"下午的500ml水喝了多少？\n"
            f"请回复我具体数字（如：300），我会调整晚上的提醒。\n"
            f"还剩 {remaining}ml 未完成。"
        )
        print(msg)
        return

    # Normal reminder messages
    phase_labels = {
        "morning": "🥤 第1杯/共3杯",
        "afternoon": "🥤 第2杯/共3杯",
        "evening": "🌙 第3杯/共3杯",
        "night": "🌙 睡前润口",
    }
    label = phase_labels.get(phase, "💧 喝水提醒")
    default_amount = slot["default"]

    # Dynamic adjustment based on remaining
    if remaining <= 0:
        progress_msg = "🎉 今日目标已达成！继续保持~"
    else:
        progress_msg = f"目标1.5L，还剩 {remaining}ml"

    # 13:00 special: adjust if morning was low
    if time_key == "13:00" and total < 500:
        shortfall = 500 - total
        adjusted = 500 + min(shortfall, 200)
        msg = (
            f"{label}\n\n"
            f"{get_progress_bar(total)}\n\n"
            f"上午进度偏低，下午建议接 {adjusted}ml 追赶一下。\n"
            f"下班前喝完，喝不完打包带走。\n"
            f"{progress_msg}"
        )
        print(msg)
        return

    # 21:00 special: dynamic evening amount
    if time_key == "21:00":
        evening_needed = min(remaining, 400)
        msg = (
            f"{label}\n\n"
            f"{get_progress_bar(total)}\n\n"
            f"晚间建议喝 {evening_needed}ml。\n"
            f"算一算今天达标了吗？"
        )
        print(msg)
        return

    # 22:30 special
    if time_key == "22:30":
        if total >= DAILY_TARGET:
            msg = (
                f"{label}\n\n"
                f"{get_progress_bar(total)}\n\n"
                f"🎉 今日1.5L目标达成！最后润口100ml即可。"
            )
        else:
            msg = (
                f"{label}\n\n"
                f"{get_progress_bar(total)}\n\n"
                f"还差 {remaining}ml，润口休息，明天再战。"
            )
        print(msg)
        return

    # Default
    msg = (
        f"{label}\n\n"
        f"{get_progress_bar(total)}\n\n"
        f"接{default_amount}ml水，喝完后进度更新。\n"
        f"{progress_msg}"
    )
    print(msg)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 water_tracker.py [init|record AMOUNT|status|message HH:MM]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "init":
        cmd_init()
    elif cmd == "record" and len(sys.argv) >= 3:
        try:
            amount = int(sys.argv[2])
            cmd_record(amount)
        except ValueError:
            print("Amount must be a number")
            sys.exit(1)
    elif cmd == "status":
        cmd_status()
    elif cmd == "message" and len(sys.argv) >= 3:
        cmd_message(sys.argv[2])
    else:
        print("Unknown command or missing args")
        sys.exit(1)
