# OpenClaw Teaching Control Plane

A sanitized architecture reference and minimal implementation template for an OpenClaw-style teaching control plane.

The document describes a two-layer agent setup:

- `main` acts as a thin platform hub for routing, protocol handoff, and cross-agent maintenance.
- `assistant-4 / Xiaolan` handles teaching-task orchestration inside its own domain, including group sessions, answer grading, and task state updates.

This repository keeps the architecture-relevant files needed to understand and reproduce the design. Historical archives, personal agent persona files, local editor state, and private runtime data are not included.

## Quick Start

```bash
git clone https://github.com/junsongYYYY/openclaw-teaching-control-plane.git
cd openclaw-teaching-control-plane
```

Read the architecture first:

```text
docs/architecture.md
```

Then inspect the minimal teaching-agent template:

```text
templates/assistant-4-teaching-agent/
```

## Repository Layout

```text
.
├── README.md
├── SANITIZATION.md
├── docs/
│   └── architecture.md
└── templates/
    └── assistant-4-teaching-agent/
        ├── AGENTS.md
        ├── MEMORY.md
        ├── memory/
        │   ├── groups.md
        │   └── students.md
        └── my_document/
            └── test-data/
                ├── active_test.json
                ├── active_test_empty.json
                ├── active_test_schema.md
                ├── task_file_schema.md
                ├── photo_workflow.md
                ├── task_manager.py
                ├── kb_tool.py
                ├── answers/
                ├── reports/
                ├── tasks/
                └── tests/
```

## Included

- Public architecture notes for the OpenClaw platform control layer.
- Public architecture notes for the teaching-agent control/execution layer.
- A minimal sanitized `assistant-4` teaching-agent template that shows the state bus, task schemas, group mapping, and task-management scripts.
- `active_test.json` contains a sanitized active-task example, while `active_test_empty.json` can be copied as the empty runtime initialization template.
- Sanitization notes explaining what was removed or replaced.

## Excluded

- Historical archive documents.
- Personal agent files such as `USER.md`, `TOOLS.md`, `SOUL.md`, `IDENTITY.md`, and `HEARTBEAT.md`.
- Runtime caches, full task history, full answer archives, full reports, real student rosters, and real group registries.
- Real Feishu `chat_id`, `open_id`, `appId`, host details, names, tokens, or secrets.

## Verification

Before publication, the repository was checked so the public file tree contains only the architecture reference and the minimal sanitized template needed to reproduce the design.
