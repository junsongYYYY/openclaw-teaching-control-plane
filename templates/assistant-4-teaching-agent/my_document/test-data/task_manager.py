#!/usr/bin/env python3
"""
统一任务管理
- publish: 发布新任务（自动清理过期 + 原子写入 + 文件锁）
- summary: 汇总任务（归档 + 移除）
- clean: 清理过期任务
- submit: 更新学生提交状态（通过统一入口，禁止直接写 active_test.json）

用法：
  python3 task_manager.py publish --type text_answers --file test_xxx.json --target 第1组
  python3 task_manager.py publish --type text_answers --file test_xxx.json --groups oc_xxx
  python3 task_manager.py submit --task-id test_xxx --group oc_xxx --student-id ou_xxx
  python3 task_manager.py summary --task-id test_xxx --reason summary
  python3 task_manager.py clean [--task-id <id>] [--dry-run]
"""

import json, os, sys, tempfile, argparse, re
from datetime import datetime, timedelta, timezone

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.abspath(__file__))
ACTIVE_TEST = os.path.join(BASE, "active_test.json")
ARCHIVE_DIR = os.path.join(BASE, "archive")
TESTS_DIR = os.path.join(BASE, "tests")
TASKS_DIR = os.path.join(BASE, "tasks")
GROUPS_FILE = os.path.join(BASE, "..", "..", "memory", "groups.md")
DEFAULT_EXPIRY = timedelta(hours=24)


def now():
    return datetime.now(TZ)


def parse_time(s):
    if not s:
        return None
    try:
        from dateutil import parser as du_parser
        return du_parser.parse(s)
    except:
        return None


# ── 锁和原子写入 ──

def acquire_lock(filepath):
    lock_path = filepath + '.lock'
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    if fcntl:
        fcntl.flock(fd, fcntl.LOCK_EX)
    elif msvcrt:
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
    return fd


def release_lock(fd, lock_path):
    try:
        if fcntl:
            fcntl.flock(fd, fcntl.LOCK_UN)
        elif msvcrt:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)
    except:
        pass
    try:
        os.unlink(lock_path)
    except:
        pass


def atomic_write(filepath, data):
    dirpath = os.path.dirname(filepath)
    os.makedirs(dirpath, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dirpath, suffix='.tmp')
    try:
        content = json.dumps(data, indent=2, ensure_ascii=False)
        json.loads(content)
        os.write(fd, content.encode('utf-8'))
        os.close(fd)
        os.rename(tmp_path, filepath)
    except Exception as e:
        try: os.close(fd)
        except: pass
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise e


# ── 事务式状态更新（读-改-写全程持锁） ──

def transactional_update(updater_fn):
    """
    事务式更新 active_test.json。
    updater_fn: 接收 data dict，返回修改后的 data dict。
    读、改、写在同一锁内完成。
    """
    lock_fd = acquire_lock(ACTIVE_TEST)
    try:
        if not os.path.exists(ACTIVE_TEST):
            data = {"active_tasks": [], "note": "多任务队列结构。统一 24h 过期。"}
        else:
            with open(ACTIVE_TEST, "r", encoding="utf-8") as f:
                data = json.load(f)
        data = updater_fn(data)
        atomic_write(ACTIVE_TEST, data)
        return data
    finally:
        release_lock(lock_fd, ACTIVE_TEST + '.lock')


# 兼容旧接口：read_active_test 和 write_active_test 内部也走事务
def read_active_test():
    return transactional_update(lambda d: d)


def write_active_test(data):
    transactional_update(lambda d: data)


# ── 群名称解析 ──

def load_group_map():
    """
    从 memory/groups.md 解析群名称 → chat_id 映射。
    返回 dict，如 {"第1组": "oc_b12...", "测试群": "oc_beb..."}
    """
    groups = {}
    if not os.path.exists(GROUPS_FILE):
        return groups
    with open(GROUPS_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    # 匹配格式：## 第X组 / ## 测试群
    # 然后找 - **chat_id:** oc_xxx
    sections = re.split(r'##\s+', content)
    for section in sections:
        lines = section.strip().split('\n')
        if not lines:
            continue
        group_name = lines[0].strip().rstrip(':')
        chat_id_match = None
        for line in lines[1:]:
            # 兼容 markdown 格式：- **chat_id:** oc_xxx、oc_GROUP_01 或真实 Feishu chat_id
            m = re.search(r'(?:chat_)?id[:\*\s]*[:\*\s]*\s*(oc_[A-Za-z0-9_]+)', line)
            if m:
                chat_id_match = m.group(1)
                break
        if group_name and chat_id_match:
            groups[group_name] = chat_id_match
    return groups


def resolve_targets(target_names=None, groups=None):
    """
    解析目标群。优先使用 target_names（组名列表），其次使用 groups（chat_id 列表）。
    target_names: ["第1组", "测试群"]
    groups: ["oc_b12...", "oc_beb..."]
    返回 chat_id 列表。
    """
    if target_names:
        group_map = load_group_map()
        resolved = []
        for name in target_names:
            if name in group_map:
                resolved.append(group_map[name])
            else:
                print(f"❌ 未知群名称: {name}")
                print(f"   可用群: {', '.join(group_map.keys())}")
                return None
        return resolved
    elif groups:
        return groups
    return None


# ── 过期检查 ──

def is_expired(task):
    expires = parse_time(task.get("expires_at"))
    if not expires:
        published = parse_time(task.get("published_at"))
        if published:
            expires = published + DEFAULT_EXPIRY
    return expires and now() > expires


def archive_task_item(task, reason="expired"):
    today = now().strftime("%Y%m%d")
    archive_path = os.path.join(ARCHIVE_DIR, f"auto_{today}")
    os.makedirs(archive_path, exist_ok=True)
    task["close_reason"] = reason
    if not task.get("completed_at"):
        task["completed_at"] = now().isoformat()
    archive_file = os.path.join(archive_path, f"{task['id']}.json")
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(task, f, indent=2, ensure_ascii=False)
    return archive_file


# ── publish ──

def publish_task(task_file, task_type, groups, question_count=None, photo_count=None):
    _result = {"task_id": None, "entry": None}

    def _update(data):
        # 清理过期
        expired = [t for t in data.get("active_tasks", []) if is_expired(t)]
        if expired:
            for t in expired:
                if not t.get("completed"):
                    t["completed"] = True
                    t["completed_at"] = now().isoformat()
                    t["auto_completed_reason"] = "超时自动关闭"
                archive_task_item(t, "expired")
            data["active_tasks"] = [t for t in data["active_tasks"] if not is_expired(t)]

        # 读任务文件
        task_path = os.path.join(TESTS_DIR if task_type == "text_answers" else TASKS_DIR, task_file)
        if not os.path.exists(task_path):
            raise FileNotFoundError(f"任务文件不存在: {task_path}")
        with open(task_path, "r", encoding="utf-8") as f:
            task_content = json.load(f)

        task_id = task_content.get("id", task_content.get("task_id", task_file.replace(".json", "")))

        # 查重
        for t in data.get("active_tasks", []):
            if t["id"] == task_id:
                raise ValueError(f"任务 {task_id} 已存在，跳过")

        entry = {
            "id": task_id,
            "file": task_file,
            "type": task_type,
            "published_at": now().isoformat(),
            "expires_at": (now() + DEFAULT_EXPIRY).isoformat(),
            "groups": groups,
            "submitted_students": [],
            "completed": False,
        }
        if task_type == "text_answers":
            entry["question_count"] = question_count if question_count is not None else len(task_content.get("questions", []))
        elif task_type == "photo_submission":
            entry["photo_count"] = photo_count if photo_count is not None else task_content.get("photo_count", 1)

        data.setdefault("active_tasks", []).append(entry)
        _result["task_id"] = task_id
        _result["entry"] = entry
        return data

    try:
        transactional_update(_update)
        print(f"✅ 任务已发布: {_result['task_id']}")
        print(f"   type: {task_type}, groups: {groups}, expires: {_result['entry']['expires_at']}")
        return True
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return False
    except ValueError as e:
        print(f"⚠️ {e}")
        return False


# ── submit ──

def submit_student(task_id, group_chat_id, student_id):
    """
    通过统一入口更新学生提交状态。
    禁止直接写 active_test.json！
    """
    def _update(data):
        for t in data.get("active_tasks", []):
            if t["id"] == task_id and group_chat_id in t.get("groups", []):
                if student_id not in t.get("submitted_students", []):
                    t.setdefault("submitted_students", []).append(student_id)
                    print(f"✅ 已记录提交: {student_id} → {task_id}")
                    return data
                else:
                    print(f"⚠️ 学生 {student_id} 已提交任务 {task_id}，不重复记录")
                    return data
        print(f"❌ 未找到匹配的任务: task_id={task_id}, group={group_chat_id}")
        return data

    try:
        transactional_update(_update)
        return True
    except Exception as e:
        print(f"❌ 更新提交状态失败: {e}")
        return False


# ── summary ──

def summary_task(task_id, reason="summary"):
    def _update(data):
        tasks = data.get("active_tasks", [])
        target = next((t for t in tasks if t["id"] == task_id), None)
        if not target:
            raise ValueError(f"任务不存在: {task_id}")

        target["completed"] = True
        target["completed_at"] = now().isoformat()
        target["close_reason"] = reason

        archive_file = archive_task_item(target, reason)
        data["active_tasks"] = [t for t in tasks if t["id"] != task_id]
        print(f"📦 归档: {archive_file}")
        return data

    try:
        transactional_update(_update)
        print(f"✅ 任务 {task_id} 已汇总并归档")
        return True
    except ValueError as e:
        print(f"❌ {e}")
        return False


# ── clean ──

def clean_tasks(task_id=None, dry_run=False, reason=None):
    def _update(data):
        tasks = data.get("active_tasks", [])
        kept, removed = [], []

        for t in tasks:
            if task_id and t["id"] != task_id:
                kept.append(t)
                continue
            if t.get("close_reason"):
                kept.append(t)
                continue
            if is_expired(t):
                if not t.get("completed"):
                    t["completed"] = True
                    t["completed_at"] = now().isoformat()
                    t["auto_completed_reason"] = "超时自动关闭"
                removed.append(t)
            else:
                kept.append(t)

        print(f"当前 {len(tasks)} 个任务 → 保留 {len(kept)} 个，清理 {len(removed)} 个")
        if removed:
            for t in removed:
                r = t.get("auto_completed_reason", t.get("close_reason", "expired"))
                print(f"  ⏰ {t['id']} → {r}")
            if not dry_run:
                for t in removed:
                    af = archive_task_item(t, reason or "expired")
                    print(f"  📦 归档: {af}")
                data["active_tasks"] = kept
            else:
                print("🔍 dry-run 模式，未修改文件")
        else:
            print("✅ 无需清理")
        return data

    try:
        transactional_update(_update)
        return True
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        return False


# ── CLI ──

def main():
    parser = argparse.ArgumentParser(description="统一任务管理")
    sub = parser.add_subparsers(dest="command")

    # publish
    p = sub.add_parser("publish")
    p.add_argument("--type", required=True, choices=["text_answers", "photo_submission"])
    p.add_argument("--file", required=True)
    p.add_argument("--groups", nargs="+", help="直接传 chat_id（兼容旧接口）")
    p.add_argument("--target", nargs="+", help="群名称，如 第1组 测试群（推荐）")
    p.add_argument("--question-count", type=int)
    p.add_argument("--photo-count", type=int)

    # submit
    s = sub.add_parser("submit")
    s.add_argument("--task-id", required=True)
    s.add_argument("--group", required=True, help="群 chat_id")
    s.add_argument("--student-id", required=True)

    # summary
    sm = sub.add_parser("summary")
    sm.add_argument("--task-id", required=True)
    sm.add_argument("--reason", default="summary")

    # clean
    c = sub.add_parser("clean")
    c.add_argument("--task-id")
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--reason")

    args = parser.parse_args()
    if args.command == "publish":
        groups = resolve_targets(target_names=args.target, groups=args.groups)
        if not groups:
            print("❌ 未指定有效目标群。使用 --target <群名> 或 --groups <chat_id>")
            sys.exit(1)
        publish_task(args.file, args.type, groups, args.question_count, args.photo_count)
    elif args.command == "submit":
        submit_student(args.task_id, args.group, args.student_id)
    elif args.command == "summary":
        summary_task(args.task_id, args.reason)
    elif args.command == "clean":
        clean_tasks(args.task_id, args.dry_run, args.reason)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
