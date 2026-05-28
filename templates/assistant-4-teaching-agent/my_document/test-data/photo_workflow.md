# 图片提交任务通用处理规则

> 收到学生图片时必读。本文件描述通用流程，不绑定某一个具体图片任务；每次评分必须以当前任务文件中的 `evaluation_criteria` 或 `grading_criteria` 为准。

---

## 一、适用范围

图片提交任务用于评价学生上传的实操过程、记录表、测量成果、施工照片、设备状态或其他课程作品。不同课程可以替换 `tasks/*.json` 中的任务名称、图片数量和评分量规，本流程保持不变。

---

## 二、核心原则

- **先匹配任务，再分析图片**：必须先读取 `active_test.json`，遍历全部 `active_tasks`，找到 `type=photo_submission` 且群组匹配、学生未提交、任务未过期的任务。
- **评分依据来自任务文件**：图片分析提示词、检查项和分值均由当前任务文件的 `evaluation_criteria` / `grading_criteria` 动态生成，禁止沿用上一任务的具体字段。
- **一次图片分析优先**：每张图片原则上只调用一次图像分析工具；图片不清晰或工具失败时，记录为 `pending_review`，交由教师复核。
- **先批改再标记提交**：处理顺序固定为“读取任务 -> 分析图片 -> 评分 -> 保存 `answers/` -> 调用 `task_manager.py submit` -> 回复学生”。
- **禁止直接改状态总线**：提交状态只能通过 `task_manager.py submit` 更新，禁止手工改写 `active_test.json`。

---

## 三、通用处理流程

```text
收到图片
  -> 读取 active_test.json
  -> 遍历全部 active_tasks
  -> 匹配 type=photo_submission 的当前群组任务
  -> 读取 tasks/{task.file}
  -> 根据任务文件中的评分量规生成 image prompt
  -> 分析图片并逐项评分
  -> 保存 answers/{task_id}_{chat_id}_{sender_id}.json
  -> task_manager.py submit 标记提交
  -> 回复学生评分结果和改进建议
```

---

## 四、image prompt 通用模板

实际调用图像分析工具时，将 `{task_title}`、`{photo_requirement}`、`{criteria}` 替换为当前任务文件中的内容。

```text
请分析学生提交的图片，并严格依据当前任务评分量规评价。

任务名称：{task_title}
图片要求：{photo_requirement}
评分量规：
{criteria}

请输出：
1. 图片是否清晰、完整，是否满足提交要求；
2. 每个评分项是否达成，并给出简要依据；
3. 每项得分和总分；
4. 对学生的简短反馈。

注意：
- 只依据图片中实际可见内容判断；
- 看不清的内容标记为“无法判断”；
- 不编造图片中没有的信息；
- 不使用其他任务的评分标准。
```

---

## 五、任务文件示例结构

图片任务的具体评价规则写在 `tasks/*.json` 中。不同课程只需要替换任务文件，不需要修改本流程文档。

```json
{
  "id": "photo_submission_sample",
  "title": "验证图片任务",
  "type": "photo_submission",
  "photo_count": 1,
  "evaluation_criteria": {
    "photo1": {
      "name": "气泡照片",
      "check": "气泡居中"
    }
  }
}
```

---

## 六、answers 保存格式

图片分析成功时：

```json
{
  "task_id": "photo_submission_sample",
  "task_type": "photo_submission",
  "group_chat_id": "oc_GROUP_01",
  "sender_id": "ou_USER_01",
  "submitted_media": ["photo_01"],
  "image_tool_status": "success",
  "grading": {
    "items": [
      {
        "name": "评分项名称",
        "score": 20,
        "max_score": 20,
        "evidence": "图片中可见的判断依据"
      }
    ],
    "total_score": 100,
    "max_score": 100,
    "result": "合格"
  },
  "feedback": "简短反馈",
  "timestamp": "2026-05-28T10:05:00+08:00"
}
```

图片分析失败或内容无法判断时：

```json
{
  "task_id": "photo_submission_sample",
  "task_type": "photo_submission",
  "group_chat_id": "oc_GROUP_01",
  "sender_id": "ou_USER_01",
  "image_tool_status": "failed",
  "grading": {
    "result": "pending_review"
  },
  "feedback": "图片暂无法自动判断，等待教师复核。",
  "timestamp": "2026-05-28T10:05:00+08:00"
}
```

---

## 七、提交状态更新

批改结果保存后，再调用统一入口更新提交状态：

```bash
python3 task_manager.py submit --task-id <task_id> --group <chat_id> --student-id <open_id>
```

禁止直接修改 `active_test.json`。
