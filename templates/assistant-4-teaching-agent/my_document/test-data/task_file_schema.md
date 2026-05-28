# 任务文件格式规范

> 发布前必须核对。不符合规范的任务不得发布。

---

## 选择题任务（tests/test_xxx.json）

```json
{
  "id": "test_YYYYMMDD_HHMMSS",
  "title": "测试标题",
  "course": "课程名",
  "questions": [
    {
      "id": 1,
      "question": "题干",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "answer": "B",
      "knowledge_point": "知识点名称"
    }
  ]
}
```

**必填字段：** `id`（格式 test_YYYYMMDD_HHMMSS）、`title`、`course`、`questions[]`（至少1题）
**每题必填：** `id`（从1开始）、`question`、`options`（A/B/C/D）、`answer`（单字母）、`knowledge_point`

---

## 图片任务（tasks/task_xxx.json）

```json
{
  "task_id": "task_YYYYMMDD_HHMMSS",
  "task_type": "photo_submission",
  "title": "任务标题",
  "description": "任务描述，包含提交要求",
  "photo_count": 1,
  "grading_criteria": { ... }
}
```

**必填字段：** `task_id`（格式 task_YYYYMMDD_HHMMSS）、`task_type`（固定"photo_submission"）、`title`、`description`、`photo_count`（正整数）、`grading_criteria`

---

## grading_criteria 结构

### 单照片任务

```json
{
  "checklist": [
    {
      "id": "format",
      "name": "格式规范",
      "checks": ["有测站名", "有日期", "有仪器型号"],
      "weight": 15
    },
    {
      "id": "calc_2C",
      "name": "2C值计算",
      "formula": "2C = 盘左 - (盘右 ± 180°)",
      "checks": ["逐行计算正确", "2C互差 ≤ 13″"],
      "weight": 25
    }
  ],
  "pass_rule": "总分 ≥ 70 为合格，60-69 为部分合格，＜60 为不合格"
}
```

**每项必填：** `id`（英文下划线）、`name`（中文）、`checks[]`（检查点字符串数组）、`weight`（数字）
**可选：** `formula`（计算公式）
**所有 checklist 项 weight 之和 = 100**

### 多照片任务

```json
{
  "per_photo_checklist": {
    "photo1": {
      "name": "测回法记录表",
      "checklist": [ ... ],
      "tolerance": "上下半测回较差 ≤ 36″",
      "weight": 40
    },
    "photo2": { "name": "...", "checklist": [ ... ], "weight": 40 },
    "photo3": { "name": "...", "checklist": [ ... ], "weight": 10 },
    "photo4": { "name": "...", "checklist": [ ... ], "weight": 10 }
  },
  "pass_rule": "总分 ≥ 70 为合格，且 photo1、photo2 必须提交"
}
```

**每张照片必填：** `name`、`checklist[]`、`weight`（所有照片 weight 之和 = 100）
**可选：** `tolerance`（限差）

### 评分计算

- 检查项所有 checks 都通过 → 100% 达标
- 部分通过 → 50% 达标
- 全部不通过 → 0%
- 总分 = Σ(项权重 × 达标比例)

---

## 发布前检查清单

- [ ] ID 格式正确（test_/task_YYYYMMDD_HHMMSS）
- [ ] 必填字段无遗漏
- [ ] 图片任务：`grading_criteria` 存在，checklist 有 `id`/`name`/`checks`/`weight`
- [ ] weight 之和 = 100
- [ ] 选择题：每题有 `answer` 且在 options 中

## 历史任务兼容

- 活跃任务 → 逐步迁移
- 已归档任务 → 不改
- 新任务 → 必须符合本规范
