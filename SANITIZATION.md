# Sanitization Note

This repository is a public, sanitized architecture reference with a minimal implementation template. It is not a full export of the original local workspace.

## Removed

- Local editor state such as `.obsidian/`.
- Historical archive documents and troubleshooting drafts.
- Personal agent files such as `USER.md`, `TOOLS.md`, `SOUL.md`, `IDENTITY.md`, and `HEARTBEAT.md`.
- Runtime caches, context snapshots, full answer/report archives, full task history, real student rosters, real group registries, and historical task archives.

## Replaced

- Feishu `chat_id`, `open_id`, and `appId` values were replaced with stable placeholders such as `oc_GROUP_01`, `ou_USER_01`, and `cli_APP_01`.
- Teacher and student names were replaced with role placeholders.
- Host names and port values were replaced with `HOST_PLACEHOLDER` and `PORT_PLACEHOLDER`.

## Preserved

- The public architecture document under `docs/architecture.md`.
- A minimal sanitized teaching-agent template under `templates/assistant-4-teaching-agent/`.
- The state schema, task schema, task manager, knowledge-base helper, and small placeholder examples needed to understand the architecture.

Before implementing the architecture, create your own private runtime workspace and replace every placeholder with values from your own OpenClaw and Feishu environment.
