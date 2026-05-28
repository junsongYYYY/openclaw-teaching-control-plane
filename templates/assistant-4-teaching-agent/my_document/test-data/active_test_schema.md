# active_test.json 结构说明

## 数据结构

```json
{
  "active_tasks": [
    {
      "id": "test_20260526_100000",
      "file": "test_20260526_100000.json",
      "type": "text_answers",
      "published_at": "2026-05-26T10:00:00+08:00",
      "expires_at": "2026-05-27T10:00:00+08:00",
      "groups": ["oc_b12..."],
      "question_count": 3,
      "submitted_students": ["ou_xxx"],
      "completed": false
    },
    {
      "id": "task_20260526_100000",
      "file": "task_20260526_100000.json",
      "type": "photo_submission",
      "published_at": "2026-05-26T10:00:00+08:00",
      "expires_at": "2026-05-27T10:00:00+08:00",
      "groups": ["oc_b12..."],
      "photo_count": 1,
      "submitted_students": [],
      "completed": false
    }
  ],
  "note": "多任务队列结构。统一 24h 过期。"
}
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | `test/task_YYYYMMDD_HHMMSS` |
| `file` | string | ✅ | 任务文件名 |
| `type` | string | ✅ | `text_answers` 或 `photo_submission` |
| `published_at` | string | ✅ | ISO-8601 |
| `expires_at` | string | ✅ | `published_at + 24h` |
| `groups` | array | ✅ | 群 chat_id 列表 |
| `question_count` | number | 条件 | text_answers 时必填 |
| `photo_count` | number | 条件 | photo_submission 时必填 |
| `submitted_students` | array | — | 已提交学生 open_id |
| `completed` | boolean | — | 默认 false |
| `completed_at` | string | 条件 | completed=true 时写入 |
| `close_reason` | string | 条件 | summary / expired / manual |
| `auto_completed_reason` | string | 条件 | 超时自动关闭 |

## 原子写入

```python
def atomic_write(filepath, data):
    dirpath = os.path.dirname(filepath)
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
        if os.path.exists(tmp_path): os.unlink(tmp_path)
        raise e
```

## 并发安全

**已实现 flock 文件锁**（`task_manager.py` 的 `acquire_lock` / `release_lock`），所有读写均通过 `transactional_update()` 统一入口，读-改-写全程持锁。

**⚠️ 禁止直接通过 python/bash 脚本修改 active_test.json！** 所有状态变更（发布、汇总、清理、提交记录）必须通过 `task_manager.py` 的对应子命令执行。任何绕过统一入口的写入都可能导致数据丢失或并发冲突。

**统一入口命令：**
- 发布：`python3 task_manager.py publish --type <类型> --file <文件名> --target <群名>`
- 提交：`python3 task_manager.py submit --task-id <任务ID> --group <群 chat_id 占位符> --student-id <学生 open_id 占位符>`
- 汇总：`python3 task_manager.py summary --task-id <任务ID>`
- 清理：`python3 task_manager.py clean`

## 规则索引

- 匹配规则 → `AGENTS.md` 核心工作流
- 清理规则 → `AGENTS.md` 任务清理规则
- 归档路径 → `archive/auto_YYYYMMDD/{task_id}.json`
