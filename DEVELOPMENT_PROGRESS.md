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
| W1 | in_review | 0519d19 | 2026-05-19 | requirements.txt 加 bcrypt==4.0.1，passlib 1.7.4 不兼容 bcrypt 5.x |
| W2 | in_review | eb23ed9 | 2026-05-20 | prometheus-fastapi-instrumentator 锁 6.1.0，7.x 与 fastapi 0.104.1 的 starlette==0.27 冲突 |

> Note: W1 prior BLOCKED entry removed manually by user — wrapper bug rolled back W1 implementation. W1 will be retried at next fire.
| T2 | in_review | 23d248f | 2026-05-20 | 地块面积(plot_area_mu)和林业局小班号(forestry_sub_compartment)全栈实现：model/service/API/migration/frontend |
| T8 | in_review | 107c444 | 2026-05-20 | admin user management: GET/POST/PUT/DELETE /api/v1/admin/users + UserAdmin.tsx page + AdminRoute guard |
| T3 | retry | — | 2026-05-20 | **RETRY — prior attempt failed Codex review.** Specific issues to fix: (1) The "view original" button was added to an unused/orphan component, not to the ACTUAL annotated UI users see. The real annotated viewer lives in `frontend/src/components/AuthedImage.tsx` and is used by the image list / annotated thumbnail flow — wire the button there. (2) Backend `/images/{id}?max_width=1920` was added as OPTIONAL — must be DEFAULT behavior: every request to `/images/{id}` and `/images/{id}/annotated` should return 1920-max compressed by default, and only `?max_width=0` returns full. Search for ALL image-rendering usages in frontend to verify the compressed path is taken. |
| T1 | retry | — | 2026-05-20 | **RETRY — prior attempt failed Codex review.** Specific issues: (1) Task creation form does not ENFORCE picking a complete town-level region — backend must reject task POST if `region_id` is missing OR points to a non-town region (level != 'town'). Use pydantic validator. (2) Frontend Cascader must be `required` and validate that 3 levels are picked. (3) Region path display (full "市/区/街镇" string) must update everywhere a task is shown (TaskList table, TaskDetail header, ReportGenerator). |
| W3 | retry | — | 2026-05-20 | **RETRY — prior attempt failed Codex review.** Specific issue: rewriting `tests/test_api.py` and `tests/test_inference.py` is only half the job — you MUST also remove `--ignore=tests/test_api.py --ignore=tests/test_inference.py` from `.github/workflows/ci.yml` so they actually run in CI. The autodev script also has those ignores in `DEV_PROMPT` test command — that's fine to keep for autodev itself, but CI must run them. Verify by running pytest tests/ (no ignores) locally before commit. |
| T3 | BLOCKED | — | 2026-05-20 | images/{id}` still returns uncompressed original files by default for images at or below 1920px wide |
| T1 | BLOCKED | — | 2026-05-20 | T1 is incomplete: TaskList region filtering and required region CRUD/constraint tests are missing, and hierarchy/path update logic is flawed. |
| W3 | BLOCKED | — | 2026-05-20 | test_inference.py still contains no-op placeholder tests, so W3 is not genuinely complete. |
