# ecoLens 优化建议方案

> 生成日期：2026-05-17
> 适用版本：commit 2f34a7c（claude/condescending-darwin-2d5ccb 分支基线）
> 范围：架构、安全、性能、代码质量、运维、前端体验

---

## 优先级速览

| 优先级 | 类别 | 数量 | 处置 |
|--------|------|------|------|
| 🔴 P0 | 安全 / 数据风险 | 5 项（#1–#5） | 必须立即修复 |
| 🟠 P1 | 稳定性 / 功能性能 | 6 项（#6–#11） | 2 周内 |
| 🟡 P2 | 仓库卫生 / 工程化 | 6 项（#12–#17） | 1 个月内 |
| 🟢 P3 | 体验 / 长期演进 | 6 项（#18–#23） | 持续 |

---

## 🔴 P0 — 必须立即修复

### #1 生产服务器明文密码已提交进 Git
- **位置**：[server.md](server.md)
  ```
  ip：81.68.224.178
  username：ubuntu
  password: ***REDACTED-ROTATED***
  ```
- **风险**：已 push 到 `origin/main`，等同公开泄露。
- **处置步骤**：
  1. **立即修改服务器密码 + 改用 SSH key**（先做这一步，不要先改 Git）
  2. `git rm server.md`
  3. 用 git-filter-repo 改写历史：
     ```bash
     pip install git-filter-repo
     git filter-repo --path server.md --invert-paths --force
     git push --force-with-lease origin main
     ```
  4. 创建 `server.md.example` 模板
  5. 通知所有曾 clone 过仓库的人重新 clone

### #2 .env 未被 gitignore
- **位置**：[.env](.env)、[.gitignore](.gitignore)
- **现状**：`.gitignore` 中没有 `.env` 一行，当前虽是占位 `SECRET_KEY=dev-secret-key-change-in-production`，但极易被生产值覆盖后误提交
- **处置**：
  - 加 `.env`、`.env.*`、`!.env.example` 到 `.gitignore`
  - 扫描历史确认 `.env` 未被提交（`git log --all -- .env`）

### #3 CORS 完全放开 + 无认证体系
- **位置**：[backend/app/main.py:29-35](backend/app/main.py:29)、[frontend/src/App.tsx](frontend/src/App.tsx)
- **问题**：
  - `allow_origins=["*"]` + `allow_credentials=True` 是 CORS 规范禁止的组合
  - `PrivateRoute` 仅检查 localStorage token 存在，从未验证
  - 后端任何 API 都不需要登录
- **处置**：
  - 后端：从 env 读 `CORS_ALLOWED_ORIGINS` 白名单
  - 后端：JWT 鉴权（python-jose）+ `Depends(get_current_user)` 加到写接口
  - 前端：登录页接真实 `/api/v1/auth/login`，沿用现有 401 拦截器

### #4 图片接口无访问控制
- **位置**：[backend/app/api/images.py:88-103, 132-152, 155-214](backend/app/api/images.py:88)
- **风险**：知道 `image_id` 即可下载任意原图（含 GPS）
- **处置**：所有 `/images/{image_id}*` 接口加鉴权 + 校验图片归属

### #5 上传文件零校验
- **位置**：[backend/app/api/images.py:15-42](backend/app/api/images.py:15)、[backend/app/services/upload_service.py:30-83](backend/app/services/upload_service.py:30)
- **缺失**：MIME / 后缀 / 大小 / 文件名净化均无
- **处置**：
  - 白名单后缀 `{.jpg, .jpeg, .png}`
  - Pillow `verify()` 二次确认
  - `secure_filename` 或 `re.sub(r'[^\w.\-]', '_', name)`
  - `Content-Length` 上限：单图 30MB，单批 2GB
  - 分块写入 + 累计大小校验

---

## 🟠 P1 — 影响线上稳定性

### #6 上传与异步任务竞态
- **位置**：[backend/app/api/images.py:23-27](backend/app/api/images.py:23)、[upload_service.py:80](backend/app/services/upload_service.py:80)
- **问题**：每张图 +1 后即 commit，Celery 任务可能在所有图入库前就触发去重
- **处置**：批量 add 后统一 commit；trigger 接受 image_id 列表而非查表

### #7 去重任务双重触发
- **位置**：[inference_tasks.py:138-164, 265-271](backend/app/tasks/inference_tasks.py:138)
- **问题**：`_check_and_trigger_deduplication` + `apply_async(countdown=300)` 两条路径都会触发去重
- **处置**：改用 Celery `chord(group(process_image_task...), process_task_deduplication.s())`；删掉 countdown 路径

### #8 Celery worker 中 asyncio.run 模式
- **位置**：[inference_tasks.py:43, 193, 239](backend/app/tasks/inference_tasks.py:43)
- **问题**：每任务新建 event loop + 重建 asyncpg 连接，并发 worker 下会异常
- **处置**：worker 内任务改用同步 SQLAlchemy session

### #9 推理流程每张图重载模型
- **位置**：[nest_detector.py:51-198](backend/app/services/nest_detector.py:51)、[inference_tasks.py:77, 88](backend/app/tasks/inference_tasks.py:77)
- **处置**：模块级单例 + `worker_process_init` 信号预热

### #10 EXIF 硬编码 sensor_width=13.2
- **位置**：[upload_service.py:170-172](backend/app/services/upload_service.py:170)
- **影响**：非 1 英寸传感器机型 GSD 误差 ~2x，GPS 反算系统性偏移
- **处置**：读 EXIF `Make+Model` 建立机型→传感器宽度表；或用 `FocalPlaneXResolution` 真实计算

### #11 缺索引 + 潜在 N+1
- **位置**：[backend/app/api/images.py:45-85](backend/app/api/images.py:45)、`backend/app/models/__init__.py`
- **处置**：模型上 `index=True` 显式声明外键索引

---

## 🟡 P2 — 仓库卫生 & 工程化

### #12 27.8MB JPG 被 Git 跟踪
- 根目录 `result_*.jpg`、`test_*.jpg`、`test_annotated.jpg`、`test9_result.jpg`、`pics/001.jpg`
- 处置：`git rm --cached` + `.gitignore` 补充

### #13 三个 docker-compose 文件用途不清
- [docker-compose.yml](docker-compose.yml) / [.prod.yml](docker-compose.prod.yml) / [.server.yml](docker-compose.server.yml)
- 处置：DEPLOY.md 顶部加说明，或合并为 override 模式

### #14 配置默认值会误连开发库
- [backend/app/core/config.py:13-20](backend/app/core/config.py:13)
- 处置：DATABASE_URL / CELERY_BROKER_URL 改为无默认必填

### #15 缺 lint / format / type 检查
- 处置：加 `pyproject.toml` ruff 配置，CI 跑 `ruff check && pytest`

### #16 测试覆盖只够 smoke
- 优先补：`pixel_to_gps`、`deduplicate_nests` 单元测试；end-to-end happy path

### #17 CI/CD 空白
- 处置：建 `.github/workflows/ci.yml`，跑 lint + 测试 + 构建前端

---

## 🟢 P3 — 体验 & 长期演进

### #18 TaskDetail.tsx 507 行单体组件
- 拆 `<TaskOverview/>` `<NestMap/>` `<NestListTab/>` `<ImageListTab/>` `<UploadMoreTab/>`
- 用 React Query / SWR 替代 Promise.all + .catch(() => null)

### #19 缺长任务进度刷新
- `processing` 状态下轮询 `/tasks/{id}/status`，或加 SSE

### #20 切片推理未启用
- [image_utils.py](backend/app/utils/image_utils.py) 已有 `slice_image / white_balance_correction`，但推理流程没用
- 大分辨率航拍图被 YOLO resize 到 640，小目标漏检严重 → 检测精度最大杠杆点

### #21 best.pt 同时当虫巢和树种模型
- [config.py:27, 31, 36-37](backend/app/core/config.py:27) 默认值需更正
- 删除 `TREE_MODEL_PATH` / `NEST_MODEL_PATH` 兼容字段

### #22 零可观测性
- 接 `prometheus-fastapi-instrumentator` + Sentry + 结构化日志

### #23 三个部署脚本散乱
- 统一为 GitHub Actions 或 Ansible

---

## 执行节奏建议

| 周期 | 必做 | 应做 |
|------|------|------|
| **本周** | #1 #2 #3 #4 #12 | #5 |
| **2 周内** | #6 #7 #9 #11 | #8 #10 #14 #17 |
| **1 个月内** | #16 #18 #19 #20 | #15 #21 #22 |

---

## P0 执行清单（本次启动）

- [ ] **用户**：登录 81.68.224.178，立即修改 ubuntu 密码 + 配置 SSH key
- [ ] **Dev Team A（仓库卫生）**：删 server.md、`.env` 入 ignore、创建 server.md.example
- [ ] **Dev Team B（安全骨架）**：CORS 白名单 + JWT 认证 + 图片接口鉴权 + 上传文件校验
- [ ] **Review Team**：独立审查 Team A / Team B 全部变更
- [ ] **用户**：确认无误后执行 `git filter-repo` + `git push --force-with-lease origin main`
