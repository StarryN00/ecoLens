# 樟巢螟智能检测系统 - 使用说明

## 📋 项目简介

**樟巢螟智能检测系统**是一个面向城市绿化管理部门的无人机航拍 + AI 自动检测平台。系统能够自动完成：

- ✅ 香樟树识别
- ✅ 虫巢检测
- ✅ 重叠去重
- ✅ 报告生成

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React + TypeScript + Ant Design | 管理后台 |
| 后端 | Python + FastAPI | 高性能异步 API |
| 数据库 | SQLite / PostgreSQL | 数据存储（当前使用 SQLite） |
| AI推理 | PyTorch + YOLOv8 | 虫巢检测 |
| 任务队列 | Celery + Redis | 异步处理（可选） |

---

## 🚀 快速开始

### 1. 环境要求

- **操作系统**: macOS / Linux / Windows
- **Python**: 3.9+
- **Node.js**: 18+
- **内存**: 建议 8GB+
- **磁盘**: 建议 10GB+ 可用空间

### 2. 目录结构

```
nest-detection-system/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/               # API 路由
│   │   ├── core/              # 核心配置
│   │   ├── models/            # 数据库模型
│   │   ├── services/          # 业务逻辑
│   │   └── main.py            # 应用入口
│   ├── models/                # AI 模型文件目录
│   ├── uploads/               # 上传图片存储
│   ├── thumbnails/            # 缩略图存储
│   ├── venv/                  # Python 虚拟环境
│   └── requirements.txt       # 依赖列表
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── pages/             # 页面组件
│   │   └── services/          # API 调用
│   └── package.json
├── .env                        # 环境变量配置
└── README.md
```

---

## 🔧 系统启动

### 方式一：自动启动（推荐）

项目已完成初始化配置，直接运行启动脚本：

```bash
# 1. 进入项目目录
cd /Users/starryn/project/ecoLens

# 2. 启动后端
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. 启动前端（新开终端窗口）
cd frontend
npm run dev
```

### 方式二：后台运行

```bash
# 后端后台运行
cd backend
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/backend.log 2>&1 &

# 前端后台运行
cd frontend
nohup npm run dev > /tmp/frontend.log 2>&1 &
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端界面 | http://localhost:5173 | 管理后台 |
| 后端 API | http://localhost:8000 | REST API |
| API 文档 | http://localhost:8000/docs | Swagger UI |

---

## 📖 使用流程

### 第一步：登录系统

1. 打开浏览器访问 http://localhost:5173
2. 使用默认账号登录（开发模式无需密码）

### 第二步：创建巡检任务

1. 点击 **"新建任务"** 按钮
2. 填写任务信息：
   - 任务名称
   - 巡检区域
   - 操作员
3. 点击 **"创建"**

### 第三步：上传图片

1. 进入任务详情页
2. 点击 **"上传图片"**
3. 选择无人机拍摄的图片（支持批量上传）
4. 系统会自动解析图片 EXIF 信息（GPS、拍摄时间等）

### 第四步：启动 AI 检测

1. 在任务详情页点击 **"开始检测"**
2. 系统会依次执行：
   - 树种识别（判断是否包含香樟树）
   - 虫巢检测（定位虫巢位置）
   - GPS 反算（像素坐标转地理坐标）
   - 去重合并（DBSCAN 空间聚类）
3. 等待检测完成

### 第五步：查看结果

1. 查看检测到的虫巢列表
2. 在地图上查看虫巢分布
3. 导出检测报告（PDF/Excel）

---

## 🤖 AI 模型配置

### 模型文件放置

将训练好的 AI 模型文件放入以下目录：

```bash
backend/models/
├── nest_det.pt          # YOLOv8 虫巢检测模型
└── tree_seg.pt          # DeepLabV3+ 树种识别模型
```

### 模型格式要求

- **格式**: PyTorch `.pt` 文件
- **检测模型**: YOLOv8 目标检测模型
- **分割模型**: DeepLabV3+ 语义分割模型

### 无模型模式

如果暂时没有模型文件，系统会：
- ✅ 正常运行其他功能
- ✅ 接收图片上传
- ⚠️ AI 检测返回空结果

---

## 🔌 API 接口

### 核心接口

#### 1. 任务管理

```http
# 创建任务
POST /api/v1/tasks
Content-Type: application/json

{
  "task_name": "巡检任务-001",
  "area_name": "人民公园",
  "operator": "张三"
}

# 查询任务列表
GET /api/v1/tasks

# 查询任务详情
GET /api/v1/tasks/{task_id}

# 删除任务
DELETE /api/v1/tasks/{task_id}

# 查询任务状态
GET /api/v1/tasks/{task_id}/status
```

#### 2. 图片管理

```http
# 上传图片
POST /api/v1/tasks/{task_id}/images
Content-Type: multipart/form-data

# 查询图片列表
GET /api/v1/tasks/{task_id}/images

# 查询图片详情
GET /api/v1/images/{image_id}

# 获取缩略图
GET /api/v1/images/{image_id}/thumbnail
```

#### 3. 检测接口

```http
# 启动检测任务
POST /api/v1/tasks/{task_id}/detect

# 查询检测结果
GET /api/v1/tasks/{task_id}/detections

# 导出报告
GET /api/v1/tasks/{task_id}/report?format=pdf
```

### 完整 API 文档

访问 http://localhost:8000/docs 查看交互式 API 文档。

---

## ⚙️ 配置说明

### 环境变量

编辑 `.env` 文件修改配置：

```bash
# 数据库配置
DATABASE_URL=sqlite+aiosqlite:///./nestdb.sqlite

# Redis 配置（可选）
REDIS_URL=redis://localhost:6379/0

# 文件存储
UPLOAD_DIR=./uploads
THUMBNAIL_DIR=./thumbnails

# AI 模型路径
NEST_DETECTION_MODEL_PATH=./models/nest_det.pt
TREE_CLASSIFICATION_MODEL_PATH=./models/tree_seg.pt

# 应用配置
DEBUG=True
APP_NAME=樟巢螟智能检测系统
```

### 数据库切换

当前使用 **SQLite**，如需切换到 **PostgreSQL**：

1. 修改 `.env`：
```bash
DATABASE_URL=postgresql+asyncpg://nestuser:nestpass@localhost:5432/nestdb
```

2. 恢复 PostgreSQL 模型（需要修改 `backend/app/models/__init__.py`）：
   - 将 `String(36)` 改回 `UUID(as_uuid=True)`
   - 添加 `Geometry` 空间字段支持

---

## 🔍 故障排除

### 问题 1：端口被占用

```bash
# 查找占用端口的进程
lsof -ti:8000  # 后端端口
lsof -ti:5173  # 前端端口

# 终止进程
kill -9 <PID>
```

### 问题 2：后端无法启动

```bash
# 检查日志
cat /tmp/backend.log

# 常见解决
pip install greenlet  # 如果提示缺少 greenlet
cd backend && source venv/bin/activate  # 确保在虚拟环境中
```

### 问题 3：前端无法启动

```bash
# 重新安装依赖
cd frontend
rm -rf node_modules
npm install
npm install react-leaflet  # 如果缺少地图组件
```

### 问题 4：模型加载失败

```bash
# 检查模型文件是否存在
ls -lh backend/models/*.pt

# 确认模型路径配置
cat backend/.env | grep MODEL_PATH
```

---

## 📊 性能优化

### 1. 提高并发处理能力

编辑 `docker-compose.prod.yml`（如果使用 Docker）：

```yaml
worker:
  command: celery -A app.core.celery_app worker --loglevel=info --concurrency=4
```

### 2. 数据库优化

SQLite 适合小型项目，数据量大时建议迁移到 PostgreSQL。

### 3. M4 Mac 性能调优

M4 芯片已自动启用 Metal Performance Shaders (MPS) 加速：

```python
# PyTorch 会自动检测并使用 MPS
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
```

---

## 🛠️ 开发扩展

### 添加新的 AI 模型

1. 将模型文件放入 `backend/models/`
2. 在 `backend/app/services/` 创建服务类
3. 在 `backend/app/api/` 添加 API 路由

### 修改数据库模型

1. 编辑 `backend/app/models/__init__.py`
2. 重启后端服务，自动创建新表

### 前端开发

```bash
cd frontend
npm run dev      # 开发模式
npm run build    # 构建生产版本
npm run preview  # 预览生产版本
```

---

## 📝 注意事项

1. **生产环境部署**
   - 修改 `SECRET_KEY`
   - 使用 HTTPS
   - 配置防火墙
   - 定期备份数据库

2. **AI 模型**
   - 模型文件较大（100MB-1GB），请勿提交到 Git
   - 确保模型版本与代码兼容

3. **图片存储**
   - 上传的图片保存在 `uploads/` 目录
   - 定期清理或备份历史数据

4. **数据库备份**
   ```bash
   # SQLite 备份
   cp backend/nestdb.sqlite backup_$(date +%Y%m%d).sqlite
   ```

---

## 📞 技术支持

如有问题，请：
1. 查看 API 文档: http://localhost:8000/docs
2. 检查日志文件: `/tmp/backend.log`, `/tmp/frontend.log`
3. 提交 Issue 到项目仓库

---

**版本**: V1.0.0  
**更新日期**: 2026-03-08  
**适用平台**: macOS / Linux / Windows
