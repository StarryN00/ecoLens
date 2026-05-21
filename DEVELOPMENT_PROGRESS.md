# Development Progress (T-Series + W-Series)

Track development of tasks listed in `DEVELOPMENT_TASKS.md`.

> 历史：T4/W1/W2/T2/T8 由 LaunchAgent `com.starryn.ecolens-autodev` 自动完成
> （已下线）；T3/T1/W3 因自动流程反复 BLOCKED，改为对话内人工实现 + Codex 审核。

Verdict flow per task:
- `pending` — 待开发
- `in_review` — 已实现，待 Codex 审核
- `done` — Codex PASS 并已 push 到 main
- `manual` — 需人工操作（agent 物理做不到），跳过
- `BLOCKED` — 审核多次 FAIL，需人工介入

## Task Order (priority queue)

1. ~~T4 虫巢标注框红色加粗~~ ✅
2. W4 模型文件上传到生产（manual）
3. ~~W1 bcrypt==4.0.1 锁版本~~ ✅
4. ~~W2 starlette / prometheus 冲突~~ ✅
5. **T3 — 图片压缩**（人工进行中）
6. ~~T2 地块管理~~ ✅
7. **T1 — 多级目录架构（市→区→街镇）**（人工进行中）
8. ~~W3 重写 test_api.py / test_inference.py~~ ✅
9. ~~T8 用户管理 UI (admin)~~ ✅
10. T7 — 操作手册（截图）+ API 文档（待客户确认）
11. T5 — Word (.docx) 报告格式（待客户确认）
12. T6 — GeoJSON / KML / Shapefile 导出（待客户确认）

## Progress Table

| Task | Status | Commit | Date | Notes |
|------|--------|--------|------|-------|
| T4 | done | 415bc89 | 2026-05-19 | 后端+前端统一红色宽5边框，Codex PASS |
| W1 | done | 0519d19 | 2026-05-19 | requirements.txt 锁 bcrypt==4.0.1（passlib 1.7.4 不兼容 bcrypt 5.x）|
| W2 | done | eb23ed9 | 2026-05-20 | prometheus-fastapi-instrumentator 锁 6.1.0 + starlette==0.27 |
| T2 | done | 23d248f | 2026-05-20 | 地块面积(plot_area_mu) + 林业局小班号(forestry_sub_compartment) 全栈 |
| T8 | done | 107c444 | 2026-05-20 | admin 用户管理：/api/v1/admin/users CRUD + UserAdmin.tsx + AdminRoute |
| W3 | done | b3dc826 | 2026-05-21 | 重写 test_api/test_inference 适配鉴权 + CI 解除 ignore + 全项目 ruff 清理；Codex PASS，py3.11 下 133 passed |
| W4 | manual | — | 2026-05-19 | 需 user 手动 SSH + rsync `.pt` 文件到生产 models/ + restart PM2 |
| T3 | done | c2d7e36 | 2026-05-21 | 后端默认压缩 max_width=1920（quality 82）+ max_width=0 取原图；前端 AuthedImage "原图"按钮；Codex PASS |
| T1 | done | 5dc049e | 2026-05-21 | 市/区/街镇 三级区域全栈：Region 模型+regions API+迁移；任务强制 town 级；TaskList 后端筛选；Cascader+RegionAdmin 页；Codex PASS，153 passed |

## T3 / T1 实现要点（来自 Codex 历次审核反馈）

**T3 图片压缩**：
1. "view original" 按钮要接到**真正在用**的标注查看器（`frontend/src/components/AuthedImage.tsx`），不是孤儿组件。
2. 后端 `/images/{id}` 和 `/images/{id}/annotated` 必须**默认**返回 1920-max 压缩版（quality≈82），只有 `?max_width=0` 才返回原图。`max_width` 要拒绝负值（防 500）。
3. 前端所有图片渲染处都要走压缩路径。

**T1 多级目录架构**：
1. 后端：任务创建必须强制 `region_id` 存在且指向 town 级区域（level=='town'），用 pydantic validator 拒绝缺失/非 town。
2. 前端：Cascader `required`，校验三级都选。
3. 区域完整路径"市/区/街镇"在 TaskList / TaskDetail / ReportGenerator 都要正确显示。
4. TaskList 区域筛选要在**后端**做（不能只在前端已加载的前 20 条上筛）。
5. 需要 region CRUD + 层级约束的测试。
