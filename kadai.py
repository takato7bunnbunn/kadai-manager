"""課題・締切管理ツール

使い方:
    python kadai.py add "課題名" 11/20 [--time 17:00] [--subject 科目名]
    python kadai.py list [--all]
    python kadai.py done 番号
    python kadai.py delete 番号
"""

import argparse
import json
import unicodedata
from datetime import date, datetime
from pathlib import Path

# 課題データの保存先（このファイルと同じフォルダ）
DATA_FILE = Path(__file__).with_name("kadai.json")
WEEKDAYS = "月火水木金土日"


# ---------- データの読み書き ----------

def load_tasks():
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def save_tasks(tasks):
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def find_task(tasks, task_id):
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None


# ---------- 日付の処理 ----------

def parse_deadline(date_text, time_text):
    """'2026-11-20' や '11/20' と '17:00' から締切の日時を作る"""
    parts = date_text.replace("/", "-").split("-")
    today = date.today()

    if len(parts) == 2:  # 年を省略したとき
        month, day = int(parts[0]), int(parts[1])
        d = date(today.year, month, day)
        if d < today:  # もう過ぎている日付なら来年とみなす
            d = date(today.year + 1, month, day)
    elif len(parts) == 3:
        d = date(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        raise ValueError

    hour, minute = map(int, time_text.split(":"))
    return datetime(d.year, d.month, d.day, hour, minute)


def format_deadline(deadline):
    """例: 11/20(金) 23:59"""
    weekday = WEEKDAYS[deadline.weekday()]
    return f"{deadline:%m/%d}({weekday}) {deadline:%H:%M}"


def format_remaining(deadline, now):
    """締切までの残り時間を「あと3日」のような文字列にする"""
    seconds = (deadline - now).total_seconds()
    if seconds < 0:
        return "期限切れ"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"あと{hours}時間"
    return f"あと{hours // 24}日"


def urgency_mark(deadline, now):
    """締切が近いほど目立つ印を付ける"""
    seconds = (deadline - now).total_seconds()
    if seconds < 0:
        return "!!!"
    if seconds < 24 * 3600:
        return "!!"
    if seconds < 3 * 24 * 3600:
        return "!"
    return ""


# ---------- 表示の整形 ----------

def display_width(text):
    """全角文字を幅2、半角文字を幅1として表示幅を数える"""
    return sum(2 if unicodedata.east_asian_width(c) in "FW" else 1 for c in text)


def pad(text, width):
    """表示幅が width になるよう右側を空白で埋める"""
    return text + " " * max(width - display_width(text), 0)


# ---------- 各コマンド ----------

def add_task(tasks, title, deadline, subject):
    new_id = max((t["id"] for t in tasks), default=0) + 1
    tasks.append({
        "id": new_id,
        "title": title,
        "subject": subject,
        "deadline": deadline.isoformat(timespec="minutes"),
        "done": False,
    })
    save_tasks(tasks)
    print(f"追加しました: [{new_id}] {title}（締切 {format_deadline(deadline)}）")


def list_tasks(tasks, show_all):
    targets = tasks if show_all else [t for t in tasks if not t["done"]]
    if not targets:
        print("課題はありません。")
        return

    targets = sorted(targets, key=lambda t: t["deadline"])
    now = datetime.now()

    print(pad("番号", 6) + pad("締切", 18) + pad("残り", 12) + pad("科目", 14) + "課題")
    print("-" * 66)
    for t in targets:
        deadline = datetime.fromisoformat(t["deadline"])
        if t["done"]:
            remaining, mark = "完了", ""
        else:
            remaining = format_remaining(deadline, now)
            mark = urgency_mark(deadline, now)
        print(
            pad(str(t["id"]), 6)
            + pad(format_deadline(deadline), 18)
            + pad(remaining, 12)
            + pad(t["subject"], 14)
            + f"{t['title']} {mark}".rstrip()
        )


def mark_done(tasks, task_id):
    task = find_task(tasks, task_id)
    if task is None:
        print(f"番号 {task_id} の課題はありません。")
        return
    task["done"] = True
    save_tasks(tasks)
    print(f"完了にしました: [{task_id}] {task['title']}")


def delete_task(tasks, task_id):
    task = find_task(tasks, task_id)
    if task is None:
        print(f"番号 {task_id} の課題はありません。")
        return
    tasks.remove(task)
    save_tasks(tasks)
    print(f"削除しました: [{task_id}] {task['title']}")


# ---------- コマンドライン引数の受け取り ----------

def main():
    parser = argparse.ArgumentParser(description="課題の締切を管理するツール")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="課題を追加する")
    p_add.add_argument("title", help="課題名")
    p_add.add_argument("date", help="締切日（例: 2026-11-20、11/20）")
    p_add.add_argument("--time", default="23:59", help="締切時刻（省略時 23:59）")
    p_add.add_argument("--subject", default="", help="科目名")

    p_list = sub.add_parser("list", help="締切が近い順に表示する")
    p_list.add_argument("--all", action="store_true", help="完了した課題も表示する")

    p_done = sub.add_parser("done", help="課題を完了にする")
    p_done.add_argument("id", type=int, help="課題の番号")

    p_delete = sub.add_parser("delete", help="課題を削除する")
    p_delete.add_argument("id", type=int, help="課題の番号")

    args = parser.parse_args()
    tasks = load_tasks()

    if args.command == "add":
        try:
            deadline = parse_deadline(args.date, args.time)
        except ValueError:
            parser.error("日付は 2026-11-20 や 11/20、時刻は 17:00 の形で入力してください")
        add_task(tasks, args.title, deadline, args.subject)
    elif args.command == "list":
        list_tasks(tasks, args.all)
    elif args.command == "done":
        mark_done(tasks, args.id)
    elif args.command == "delete":
        delete_task(tasks, args.id)


if __name__ == "__main__":
    main()
