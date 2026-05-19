# Development Progress (T-Series + W-Series)

Track development of tasks listed in `DEVELOPMENT_TASKS.md` across automated runs.

This is the **single source of truth** for the LaunchAgent
`com.starryn.ecolens-autodev` (fires hourly). Each fire reads this table to
pick the next undone task; **do not edit by hand without coordinating with
the agent** or it may re-do a finished task.

Verdict flow per task:
- `in_review` — Claude implemented, awaiting Codex audit
- `done` — Codex PASSed and pushed to main
- `BLOCKED` — Codex FAILed twice, needs human attention

## Task Order (priority queue)

1. **T4** — 虫巢标注框红色加粗（30 分钟，最快胜利）
2. **W4** — 模型文件上传到生产（手工任务，Claude 会标记"manual: user must rsync"）
3. **W1** — bcrypt==4.0.1 锁版本
4. **W2** — starlette / prometheus 冲突
5. **T3** — 图片压缩
6. **T2** — 地块管理（面积 + 林业局小班号）
7. **T1** — 多级目录架构（市→区→街镇）
8. **W3** — 重写 test_api.py / test_inference.py
9. **T8** — 用户管理 UI (admin)
10. **T7** — 操作手册（截图）+ API 文档
11. **T5** — Word (.docx) 报告格式（如客户需要）
12. **T6** — GeoJSON / KML / Shapefile 导出（如客户需要）

## Progress Table

| Task | Status | Commit | Date | Notes |
|------|--------|--------|------|-------|
| T4 | done | 415bc89 | 2026-05-19 | 后端+前端统一红色宽5边框，Codex PASS |
| W4 | manual | — | 2026-05-19 | agent skip：需要 user 手动 SSH + rsync .pt 文件到生产 + restart PM2 |

> Note: W1 prior BLOCKED entry removed manually by user — wrapper bug rolled back W1 implementation. W1 will be retried at next fire.
