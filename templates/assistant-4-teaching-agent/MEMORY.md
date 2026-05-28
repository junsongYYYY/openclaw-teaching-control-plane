# MEMORY.md - Teaching Agent Template Memory

Use this file for durable, deployment-specific notes after you adapt the template.

Do not store secrets, raw access tokens, private student records, or unmanaged chat logs here.

## Identity Placeholders

- **Feishu appId:** `cli_APP_01`
- **Agent accountId:** `xiaolan`
- **Agent open_id:** `ou_AGENT_01`
- **Teacher open_id:** `ou_TEACHER_01`

The actual sender identity must always come from the current Feishu event payload. Do not treat the teacher account, the agent account, and a student account as interchangeable.

## File Index

| File | Purpose |
|------|---------|
| `memory/groups.md` | Group names and `chat_id` placeholders |
| `memory/students.md` | Example roster structure |
| `my_document/test-data/task_file_schema.md` | Task file schema |
| `my_document/test-data/photo_workflow.md` | Photo submission workflow |
| `my_document/test-data/active_test_schema.md` | Active task state schema |
| `my_document/test-data/task_manager.py` | Publish, submit, summarize, and clean tasks |

## Operational Lessons

- Persist cross-session task state to files; do not rely on conversation memory.
- Read `active_test.json` for every incoming group message before matching a task.
- Iterate through all active tasks; do not stop at the first task when message types differ.
- Grade and save a submission before marking the student as submitted.
- For image submissions, limit repeated image analysis calls and fall back to manual review when extraction is uncertain.

## Deployment Notes

Add environment-specific tools, model choices, channel settings, and operational lessons here only after replacing the placeholders with your own deployment values.
