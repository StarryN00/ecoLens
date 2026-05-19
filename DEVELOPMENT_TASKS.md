# ecoLens 开发任务清单

> 基于合同 10 项功能评估 + 用户追加 2 项需求生成。
> 报告日期：2026-05-19
> 关联文档：[UPGRADE_REPORT_P0_P3.md](UPGRADE_REPORT_P0_P3.md)（已完成 P0-P3）+ [OPTIMIZATION_PLAN.md](OPTIMIZATION_PLAN.md)

---

## 任务汇总

| 编号 | 任务 | 优先级 | 估时 | 状态 |
|------|------|--------|------|------|
| **T1** | 多级目录架构（市→区→街镇）| 🔴 P0 | 2-3 人天 | 待开发 |
| **T2** | 地块管理（面积+林业局小班号）| 🔴 P0 | 1 人天 | 待开发 |
| **T3** | 图片压缩 + 中等预览 + 原图按需 | 🟠 P1 | 0.5-1 人天 | 待开发 |
| **T4** | 虫巢标注框红色加粗 | 🟢 P2 | 0.5 小时 | 待开发 |
| **T5** | Word (.docx) 报告格式 | 🟡 待客户确认 | 1-2 人天 | 待评估 |
| **T6** | GeoJSON / KML / Shapefile 导出 | 🟡 待客户确认 | 1-2 人天 | 待评估 |
| **T7** | 操作手册（带截图）+ API 文档 | 🟡 待客户确认 | 1 人天 | 待评估 |
| **T8** | 用户管理 UI（admin 视角）| 🟢 P2 | 1 人天 | 待开发 |
| **W1** | 锁定 bcrypt==4.0.1 到 requirements.txt | 🟢 工程清理 | 0.5 小时 | 待开发 |
| **W2** | 解决 starlette / prometheus 版本冲突 | 🟢 工程清理 | 0.5 小时 | 待开发 |
| **W3** | 重写 test_api.py / test_inference.py 适配新鉴权 | 🟢 工程清理 | 0.5 人天 | 待开发 |
| **W4** | 模型 .pt 文件上传到生产 | 🔴 阻塞 AI 功能 | 0.5 小时 | 待开发 |
| **M1** | 训练 / 微调虫巢检测模型 | ⚪ ML 工作 | 5-15 人天 | 待完成 |
| **M2** | 建立测试集 + 模型验收（准确率 ≥80%）| ⚪ ML 工作 | 2-5 人天 | 待完成 |
| **M3** | 标注数据收集 + 标注流程 | ⚪ ML 工作 | 视数据量 | 待完成 |

**总计**：纯开发 ~7-10 人天 + ML ~7-20 人天

---

# 一、合同新增功能（必做）

## T1. 多级目录架构（市→区→街镇）

**合同条款**：建立"市→区→街镇"三级行政区域目录结构，替代单级项目模式。

**现状**：`InspectionTask.area_name = Column(String(200))` 是单文本字段。

**目标**：建树形区域结构，任务挂在叶子节点上，前端用级联选择器。

**拆解**：

### 后端（约 1.5 人天）
1. 新增模型 `backend/app/models/__init__.py`：
   ```python
   class Region(Base):
       __tablename__ = "regions"
       id = Column(String(36), primary_key=True, default=generate_uuid)
       name = Column(String(100), nullable=False)
       level = Column(String(10), nullable=False)  # 'city' | 'district' | 'town'
       parent_id = Column(String(36), ForeignKey("regions.id"), nullable=True, index=True)
       full_path = Column(String(500))  # 冗余存"上海市/浦东新区/陆家嘴街道"便于显示
       created_at = Column(DateTime, default=func.now())
   ```
2. `InspectionTask` 加 `region_id = Column(String(36), ForeignKey("regions.id"), index=True)`
3. 新增 `backend/app/api/regions.py`：
   - `GET /api/v1/regions/tree` — 返回完整三级树
   - `GET /api/v1/regions?level=city|district|town&parent_id=...` — 分层查询
   - `POST /api/v1/regions` — 创建（admin only）
   - `PUT /api/v1/regions/{id}` — 重命名/调整层级
   - `DELETE /api/v1/regions/{id}` — 仅允许无子节点+无任务时删
4. `backend/scripts/seed_regions.py` 种几个常见的市/区/街镇示例（可选）
5. 单元测试：树形 CRUD + 父子约束

### 前端（约 1 人天）
1. `frontend/src/services/api.ts` 加 `regionApi`
2. `TaskCreate.tsx` 用 `<antd Cascader>` 三级级联选择器替代 `area_name` 单文本框
3. `TaskList.tsx` 加按区域筛选（顶部加 Cascader filter）
4. `TaskOverview.tsx` 在任务详情显示完整路径"上海市/浦东新区/陆家嘴街道"
5. 新增 `frontend/src/pages/RegionAdmin.tsx`（admin 才能进）—— 管理区域树的 CRUD 页面
6. 路由 `/admin/regions`，加到用户菜单（仅 admin 可见）

### 验收标准
- 普通用户建任务时必须选完整三级（不允许只选市不选街镇）
- admin 能在 UI 创建/编辑/删除区域
- 删除有任务挂载的区域应阻止（友好提示）
- API 返回 `region_id` + `region_path` 两个字段
- 报告里显示完整路径

---

## T2. 地块管理（面积 + 林业局小班号）

**合同条款**：支持手动输入地块面积、林业局小班号。

**现状**：`InspectionTask` 无这两个字段。

### 后端（约 0.3 人天）
1. `InspectionTask` 加字段：
   ```python
   plot_area_mu = Column(Float, nullable=True)            # 地块面积（亩）
   forestry_sub_compartment = Column(String(50), nullable=True)  # 林业局小班号 (如 'A-12-3')
   ```
2. 写迁移脚本 `backend/scripts/add_plot_fields.py`（参照已有 `add_missing_indexes.py` 的幂等风格）
3. `tasks.py` 的 POST/GET 都把这两个字段透传
4. Pydantic schema 加这两个字段（可选输入）

### 前端（约 0.5 人天）
1. `TaskCreate.tsx` 加 2 个输入框：
   - 地块面积（数字输入 + "亩"后缀）
   - 林业局小班号（普通文本，可选）
2. `TaskOverview.tsx` 显示这两个值
3. `ReportGenerator.tsx` 报告里加这两个字段
4. `taskApi.createTask` 传参补这两个字段

### 验收标准
- 创建任务时这两个字段可选（不填也能建）
- 任务详情页正确显示
- 导出报告（PDF/Excel）含这两个字段
- 迁移脚本对存量任务把字段补 NULL（不报错）

---

# 二、用户追加需求

## T3. 图片压缩 + 中等预览 + 原图按需

**用户原话**：图片压缩，现在加载图片太慢，建议压缩，除非点击原图。

**根因分析**：
- 列表用 `/thumbnail`（300×300，已经够小）✅ 不是问题
- **打开标注查看器时调 `/annotated`，后端把原图（10-15MB）画完框后用 quality=90 JPEG 返回**，仍然 10MB 左右 → 慢
- 同样 `/images/{id}` 原图也直传不压缩

### 后端（约 0.3 人天）

`backend/app/api/images.py`：

1. **`/annotated` 加 `?max_width` query 参数**，默认 1920：
   ```python
   @router.get("/images/{image_id}/annotated")
   async def get_image_annotated(
       image_id: str,
       max_width: int = 1920,  # 0 表示原图
       db: AsyncSession = Depends(get_db),
       _user = Depends(get_current_user),
   ):
       # ... 打开原图、画框 ...
       if max_width > 0 and image.width > max_width:
           ratio = max_width / image.width
           image = image.resize((max_width, int(image.height * ratio)), PILImage.LANCZOS)
       img_io = io.BytesIO()
       image.save(img_io, format="JPEG", quality=82, optimize=True)
   ```

2. **`/images/{image_id}` 同样加 `?max_width`**，默认 1920，原图通过 `max_width=0`

3. 缓存可选优化：把 resize 后的 buffer 缓存到 `thumbnails/preview_{image_id}_1920.jpg`，下次直接 FileResponse（避免每次重复 resize）

### 前端（约 0.3 人天）

`frontend/src/components/AuthedImage.tsx`：

1. `fetchAuthedImageUrl` 在 path 上自动追加 `?max_width=1920`（除非 `previewExtra.fullSize === true`）

`frontend/src/components/ImageAnnotationViewer.tsx`：

1. Modal 主图用压缩版（默认 max_width=1920）
2. 加一个**"查看原图"按钮**（小图标 / 文字），点击后 fetch `/annotated?max_width=0`（原图）
3. 切换时显示 Loading + 提示"原图较大，加载中..."

### 验收标准
- 1920 宽压缩后 JPEG quality=82，体积通常 200-800KB（从 10MB 降到 5% 左右）
- 标注查看器 Modal 打开 → 1 秒内出图
- "查看原图"按钮可用，加载完显示原始分辨率
- 缩略图列表行为不变（保持快速）

---

## T4. 虫巢标注框红色加粗

**用户原话**：虫巢位置现在是用的绿色方框，不显眼，换成红色框标注，框线条加粗。

**现状**：
- 后端 `backend/app/api/images.py` `/annotated`：`color_map = {"severe": "red", "medium": "orange", "light": "green"}` width=3
- 前端 `frontend/src/components/ImageAnnotationViewer.tsx`：同样 severity 着色 lineWidth=3

绿色框出现的原因：当前生产模型缺失 → 默认所有检测都归类为 `light`（轻度）→ 绿色。

### 改动（约 30 分钟）

**方案 A（统一红色，简单）**：
- 后端：`color_map = {"severe": "red", "medium": "red", "light": "red"}` + `width=5`
- 前端 canvas：strokeStyle 同样统一红色，`lineWidth=5`

**方案 B（保留 severity 区分但都用偏红色）**：
- 后端：`{"severe": "#d40000", "medium": "#ff6b00", "light": "#ff3333"}` + `width=5`
- 前端同上
- 优点：保留视觉提示哪个最严重；缺点：颜色差异不大

**推荐 A**（用户原话明确"换成红色框"），后端 + 前端两处同时改。

### 文件清单
- `backend/app/api/images.py` ~ 第 195-205 行（color_map + width）
- `frontend/src/components/ImageAnnotationViewer.tsx` ~ drawAnnotations 函数（colorMap + lineWidth）

### 验收
- 缩略图列表的"标注图"列 → 红框
- 点开 Modal 大图 → 红框 + 明显加粗
- 不同 severity 仍然能从置信度数字区分（保留 severity 字段，仅视觉统一）

---

# 三、合同剩余功能（待客户确认细节）

## T5. Word (.docx) 报告格式 — 1-2 人天

**现状**：已有 PDF + Excel 报告（前端 jsPDF + xlsx）。

**如客户要求 Word**：
- 后端方案：装 `python-docx`，新增 `GET /tasks/{id}/report.docx` 端点，服务端生成
- 前端方案：装 `docx` (npm 包)，前端生成 Word
- **推荐后端方案**：能加大图、地图截图、复杂模板

待确认：客户是否真需要 Word，还是 PDF 已经够。

---

## T6. GeoJSON / KML / Shapefile 导出 — 1-2 人天

**现状**：经纬度点位已包含在 Excel 报告里。

**如客户要 GIS 标准格式**：
- GeoJSON：纯 Python `json` 模块即可，最简
- KML：装 `simplekml` 库，方便 Google Earth / 高德 / 百度地图导入
- Shapefile：装 `pyshp`，ArcGIS 行业标准

新增 API `GET /tasks/{id}/export?format=geojson|kml|shp`。

待确认：客户用什么 GIS 工具，对应选格式。

---

## T7. 操作手册（带截图）+ API 文档 — 1 人天

**现状**：
- ✅ `USER_GUIDE.md`（无截图）
- ✅ `产品设计与开发说明.md`（架构文档）
- ✅ `樟巢螟智能检测系统_技术方案V2.docx`（已有 docx 技术方案）
- ❌ 用户操作截图手册
- ❌ API OpenAPI 文档导出

**补齐**：
1. 用 Loom / OBS 录屏关键流程，截图嵌入 `OPERATION_MANUAL.docx`：
   - 登录
   - 创建任务（含区域选择 + 地块信息，需先做 T1+T2）
   - 上传图片
   - 查看结果（列表 + 标注图 + 地图）
   - 导出报告
   - 修改密码
2. FastAPI 自带 `/docs`（Swagger UI），用 `redoc-cli` 或 `widdershins` 导出 PDF / Markdown 静态版
3. 数据库 ER 图：用 SchemaSpy 或 dbdiagram.io 生成

待确认：客户是否要纸质版 / 电子版 / 视频教程。

---

## T8. 用户管理 UI（admin 视角） — 1 人天

**现状**：只有自助修改密码（普通用户），admin 想加新用户/重置别人密码必须走 SQL 或 create_admin.py 脚本。

**目标**：admin 登录后能看到一个 "/admin/users" 页面：
- 用户列表（username、email、created_at、is_admin、is_active）
- 创建用户按钮 → 弹 Modal 输入 username/password/email
- 重置密码（admin 可改任何用户密码）
- 禁用 / 启用 / 升级为 admin

后端：
- `GET /admin/users`（admin only）
- `POST /admin/users`（admin 直接造账号，绕过自助注册）
- `PUT /admin/users/{id}`（改 is_active / is_admin / 重置密码）
- `DELETE /admin/users/{id}`（软删 = is_active=False）

前端：新增 `frontend/src/pages/admin/UserAdmin.tsx`，路由 `/admin/users`。

---

# 四、工程清理（来自 P0-P3 review 遗留）

## W1. 锁定 bcrypt==4.0.1 到 requirements.txt — 30 分钟

**现状**：生产 venv 手动锁 `bcrypt==4.0.1`（因 5.0 与 passlib 1.7.4 不兼容），但 `backend/requirements.txt` 没显式写 bcrypt 版本（被 passlib[bcrypt] 间接拉，pip 默认装最新）。

**改**：
```diff
- passlib[bcrypt]==1.7.4
+ passlib[bcrypt]==1.7.4
+ bcrypt==4.0.1  # passlib 1.7.4 与 bcrypt 5.x 不兼容，必须锁 4.x
```

## W2. 解决 starlette / prometheus 版本冲突 — 30 分钟

**现状**：
```
prometheus-fastapi-instrumentator 7.1.0 要 starlette>=0.30.0
fastapi 0.104.1 锁了 starlette==0.27.0
→ pip 警告，但实际运行 OK
```

**改**：requirements.txt 把 `prometheus-fastapi-instrumentator` 降到兼容老 starlette 的版本（6.x）：
```
prometheus-fastapi-instrumentator==6.1.0  # 7.x 要 starlette>=0.30 与 fastapi 0.104 冲突
```

## W3. 重写 test_api.py / test_inference.py 适配新鉴权 — 0.5 人天

**现状**：旧测试在 P0 加鉴权后会全 401 失败，CI 中已 `--ignore=tests/test_api.py --ignore=tests/test_inference.py` 跳过。

**改**：
1. 用 fixture 自动建 admin + 拿 token（参考 `tests/test_auth.py` 的 `_login_admin`）
2. 所有请求加 `headers={"Authorization": f"Bearer {token}"}`
3. CI 移除 `--ignore` 让它们一起跑

## W4. 模型 .pt 文件上传到生产 — 30 分钟

**现状**：生产 `/home/ubuntu/ecoLens/models/` 在早期 rsync `--delete` 时被清空，AI 检测目前返空结果。

**改**：
```bash
rsync -avz -e "ssh -i /Users/starryn/project/ecoLens/server/testLinux.pem" \
  /path/to/your/local/models/ \
  ubuntu@81.68.224.178:/home/ubuntu/ecoLens/models/

# 重启后端确认加载
ssh -i .../testLinux.pem ubuntu@81.68.224.178 'pm2 restart ecolens-backend ecolens-worker'
```

**前置**：你本地有 `nest_det.pt`（虫巢检测）+ 可选 `tree_seg.pt`（树种识别）的权重文件。

---

# 五、ML 待完成（独立工作流，不在代码 sprint 内）

## M1. 训练 / 微调虫巢检测模型

**目标**：YOLOv8 模型权重 `nest_det.pt`，能在航拍图上识别樟巢螟虫巢，mAP@50 ≥ 0.8。

**输入**：
- 标注数据集（图片 + bbox + class 标签）
- 至少 500-2000 张标注图（视目标类别复杂度）

**步骤**：
1. 数据集划分：train / val / test = 7:2:1
2. 用 ultralytics YOLOv8 训练命令：
   ```bash
   yolo detect train data=nest.yaml model=yolov8m.pt epochs=100 imgsz=640
   ```
3. 训练日志 + 曲线分析 + 超参调优
4. 保存最佳权重到 `models/nest_det.pt`

## M2. 建立测试集 + 模型验收（合同 #10 准确率 ≥80%）

**目标**：出具一份《模型验收报告》证明准确率达标。

**步骤**：
1. 准备验收测试集（与训练集**独立**的 100-500 张航拍图，含标注 ground truth）
2. 运行评估脚本：
   ```python
   from ultralytics import YOLO
   model = YOLO('models/nest_det.pt')
   metrics = model.val(data='nest_test.yaml')
   # 输出 mAP@50、mAP@50:95、precision、recall、F1
   ```
3. 写报告：
   - 总体准确率 / 召回率 / F1
   - 不同场景细分（晴天 / 阴天 / 不同高度 / 不同密度）
   - 失败案例分析（哪类目标漏检 / 误检）

## M3. 标注数据收集 + 标注流程

**前置任务**（如果还没有训练数据）：

1. 与林业局协作，获取**真实航拍样本**（无人机原图含 EXIF GPS）
2. 选标注工具（LabelImg / Roboflow / Label Studio）+ 制定标注规范
3. 找 1-3 名标注员，按规范画 bbox（虫巢边界）
4. 标注后做 QA：抽样审核 + 标注员一致性测试
5. 数据增强（旋转 / 翻转 / 色调 / 模糊），扩充训练集

工作量取决于数据量，**通常 1000 张图需要 2-4 周（含 QA）**。

---

# 六、推荐执行顺序

| 周次 | 任务 | 备注 |
|------|------|------|
| **本周** | T4（红框）+ W4（模型文件）+ W1+W2（pip 锁版本）+ T3（图片压缩） | 见效快，1-2 天 |
| **下周** | T2（地块管理）+ W3（重写旧测试） | 一起做一次迁移 |
| **第三周** | T1（多级目录架构） | 改动较大，单独 sprint |
| **第四周** | T8（用户管理 UI）+ T7（操作手册）| 收尾 |
| **并行（ML 团队）** | M3 → M1 → M2 | 数据 → 训练 → 验收 |
| **客户对齐后** | T5 / T6（如客户要 Word/GIS 格式） | 视客户反馈 |

---

# 七、客户沟通要点

签合同前最好澄清三件事：

1. **#10 准确率 ≥80%**：明确这是模型问题（M1+M2），不属于软件 sprint。需要客户提供训练数据或预算给数据标注，否则准确率无法保证
2. **#4 报告格式**：PDF + Excel 够用？还是必须 Word？
3. **#8 数据导出格式**：Excel 含经纬度 OK？还是需要 GeoJSON/KML 给林业局 GIS 用？
4. **#9 文档形式**：电子 PDF 即可？还是要带截图的纸质操作手册？

---

📍 最后更新：2026-05-19，待客户对齐后开始 T1-T4 sprint。
