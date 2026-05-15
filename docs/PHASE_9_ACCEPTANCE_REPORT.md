# Phase 9 Acceptance Report

## Goal

Expose an agent supervisor shell with workflows, tasks, steps, tool calls, approval requests, logs, and diff/test placeholders.

## Modification Scope

- `services/workflow/*`
- `services/supervisor/*`
- `services/tool-gateway/*`
- `apps/web/app/supervisor/page.tsx`
- `apps/web/app/workflow/page.tsx`
- `apps/api/main.py` supervisor routes

## Minimal Usable Slice

- Workflow, AgentTask, AgentStep, ToolCallLog, and ApprovalRequest schemas exist.
- Tool execution defaults to disabled/dry-run.
- High-risk tool calls require approval.
- Supervisor UI shows plan, tasks, tool calls, approvals, logs, and placeholders.

## Validation

- `python -c "from services.supervisor import build_default_supervisor_snapshot; s=build_default_supervisor_snapshot(); assert s['tool_calls'][0]['execution_disabled'] is True"`
- `python -m compileall apps/api services`
- `npm run web:lint`
- `npm run web:build`

Result on 2026-05-12: passed.

## Rollback

- Restore `/supervisor` and `/workflow` to Phase 3 shell pages.
- Remove supervisor/workflow/tool-gateway service files.
- Remove supervisor routes from `apps/api/main.py`.

## Stop-on-Failure Rule

If high-risk calls are not blocked by default, stop and do not continue to acceptance testing.
