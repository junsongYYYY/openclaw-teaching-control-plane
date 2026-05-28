# 图片任务处理规则

> 收到学生图片时必读。

---

## 🔴 铁律

### 1. 高效验算（核心规则）
- 每张照片**最多调 1 次 image 工具**，调完进入验算+评分
- image 读取学生填写的数据 → **快速验算正确性** → 给出对错判断
- **验算一次就出结论**，算完直接给分，不反复验证
- **不一致不重调 image**——image 说学生填的是 -13，那就是 -13。我算出来不同，判"计算错误"即可，不怀疑 OCR
- **抽样验算**：每个计算列抽查 2-3 行，不需要逐行全验
- **thinking 控制在 10 行以内**——算完直接给分，不写推导过程
- **连续 2 次 thinking 内容相似 → 立刻停止，直接出结论**
- **每张照片处理上限：3 个 tool call**（读文件 → image → 保存回复）

### 2. 执行顺序
**批改 → 保存answers → 标记提交 → 回复**，严禁先标记提交再批改。

### 3. 任务匹配
必须遍历 **ALL** active_tasks 寻找 type=`photo_submission` 的匹配任务，不能只看第一个就下结论。

### 4. image 失败保护
image 失败时：**禁止编造评价、禁止给结论** → 保存 answers（result=pending_review）→ 回复"图片分析工具暂时不可用，等待教师复核"。

---

## image prompt 模板

> 根据 grading_criteria 动态填充，只提取 checklist 需要的信息。

```
请分析这张图片，按以下结构输出（精简）：

【表头】测站名=__ 日期=__ 天气=__ 仪器=__ 观测者=__ 记录者=__（无则填"无"）
【数据】按行列出：目标 | 盘左 | 盘右 | 2C | 平均方向值 | 归零方向值
【质量】清晰度=清晰/模糊 遮挡=无/有 完整性=完整/缺页

注意：
1. 只提取图片中实际看到的内容
2. 输出精简，不要长篇解释
3. 看不清的字段填"看不清"
```

---

## 验算规则

### 验算范围

| 计算列 | 公式 | 抽样策略 |
|--------|------|---------|
| 2C值 | 2C = 盘左 - (盘右 ± 180°) | 抽查 2-3 行（起始方向 + 1-2 个目标） |
| 平均方向值 | (盘左 + 盘右±180°) / 2 | 抽查 2 行 |
| 归零方向值 | 平均方向值 - 起始方向平均值 | 抽查 2 行 |
| 2C互差 | max(2C) - min(2C) | 读完所有 2C 值后直接比大小 |
| 测回互差 | 两测回同一方向的差值 | 读完直接比大小 |

### 验算流程

```
1. image 提取数据 → 读取学生填写的 2C、平均值、归零值
2. 抽查 2-3 行：用盘左+盘右 快速算一遍 → 对比学生填写值
3. 一致 → ✓ 通过；不一致 → ✗ 错误
4. 算完直接打分，不反复验算同一数据点
```

### 关键约束

- **同一个数据点最多验算 1 次**
- **image 读取值就是学生填写值，不怀疑、不重读**
- **验算不一致 → 判错 → 结束，不再调 image 确认**

---

## 量化打分模板

### 打分规则

| 规则 | 说明 |
|------|------|
| 权重均分 | 每项 weight 按 checks 数量均分（如 weight=20、4条checks → 每条 5 分） |
| 通过判定 | 验算结果 + image 提取 → 逐条判断 ✓/✗ |
| 部分通过 | 如 4 个信息写了 2 个 → 按比例给分（50%） |
| 禁止感觉分 | 最终得分 = 各项得分之和，每条必须写明 `[check] ✓/✗ → +X分` |

### 评分输出模板

```
- [checklist项名]：X/weight
  - [check1内容] ✓/✗ → +X分（理由）
  - [check2内容] ✓/✗ → +X分（理由）
  ...
```

---

## 处理流程

```
收到图片 →
1. 读 active_test.json → 遍历 ALL tasks，匹配 type=photo_submission
   └─ 无匹配 → 轻量回复"当前没有活跃图片任务"，停止
2. 读任务文件（tasks/）→ 获取 grading_criteria
3. 调 image 工具分析图片（仅此一次！用精简 prompt）
4. 验算 2-3 个数据点 → 对照 checklist 逐条打分
5. 保存 answers/ → 通过 task_manager.py 标记提交 → 回复学生
```

---

## answers 保存格式

**image 成功时：**
```json
{
  "task_id": "task_XXXXX", "task_type": "photo_submission",
  "group_chat_id": "oc_xxx", "sender_id": "ou_xxx",
  "submitted_media": ["图片描述"],
  "image_tool_status": "success",
  "grading": {
    "checklist": [
      { "id": "xxx", "name": "名称", "score": 12.5, "weight": 25, "details": "check1 ✓ +12.5 | check2 ✗ +0" }
    ],
    "total_score": 57, "max_score": 100, "result": "不合格"
  },
  "feedback": "简要评语", "timestamp": "ISO-8001"
}
```

**image 失败时：** result="pending_review"，evaluation 写明等待人工复核。

**文件名：** `answers/{task_id}_{chat_id}_{sender_id}.json`

---

## 更新提交状态

```bash
python3 task_manager.py submit --task-id <ID> --group <chat_id> --student-id <open_id>
```
禁止直接写 active_test.json，必须通过 task_manager.py。
