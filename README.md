# 樟巢螟智能检测系统

面向城市绿化管理部门的 **无人机航拍 + AI自动检测** 系统。无人机拍完照上传后，系统自动完成香樟树识别、虫巢检测、重叠去重和报告生成，全程无需人工判读。

## 🚀 快速开始

### 环境要求

- Docker 20.10+
- Docker Compose 2.0+

### 一键启动

```bash
cd /Users/starryn/project/ecoLens
docker-compose up -d
```

### 访问服务

- 前端界面: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

## 📁 项目结构

```
nest-detection-system/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/               # API 路由层
│   │   │   ├── tasks.py       # 任务管理API
│   │   │   └── images.py      # 图片上传API
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py      # 配置管理
│   │   │   └── database.py    # 数据库连接
│   │   ├── models/            # ORM 数据模型
│   │   ├── services/          # 业务逻辑层
│   │   │   ├── task_service.py
│   │   │   └── upload_service.py
│   │   ├── utils/             # 工具函数
│   │   │   ├── geo_utils.py   # GPS反算
│   │   │   └── dedup_utils.py # DBSCAN去重
│   │   └── main.py            # 应用入口
│   ├── tests/                 # 测试用例
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── pages/             # 页面组件
│   │   │   ├── Login.tsx
│   │   │   ├── TaskList.tsx
│   │   │   ├── TaskCreate.tsx
│   │   │   └── TaskDetail.tsx
│   │   ├── services/          # API 调用
│   │   │   └── api.ts
│   │   └── App.tsx            # 路由配置
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml          # Docker编排
└── README.md
```

## 🏗️ 系统架构

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React + TypeScript + Ant Design | 管理后台 |
| 后端 | Python + FastAPI | 高性能异步 API |
| 数据库 | PostgreSQL 15 + PostGIS | 空间数据存储 |
| 缓存 | Redis | 任务队列缓存 |
| AI推理 | PyTorch + YOLOv8 + DeepLabV3+ | 虫巢检测 |
| GPS去重 | scikit-learn (DBSCAN) + haversine | 空间聚类 |

### 数据流转

```
无人机拍摄
    │
    ▼
[上传图片] ──→ 对象存储 (本地文件系统)
    │
    ▼
[EXIF解析] ──→ images 表 (GPS、焦距、高度)
    │
    ▼
[任务入队] ──→ Celery 异步队列
    │
    ▼
[预处理] ──→ 白平衡 → 切片 (640×640)
    │
    ▼
[阶段1: 树种识别] ──→ 有香樟树?
    │                      │
    │ 有                   │ 无
    ▼                      ▼
[阶段2: 虫巢检测]    image_detections
    │
    ▼
[像素→GPS反算]
    │
    ▼
[DBSCAN空间聚类] ──→ unique_nests 表
    │
    ▼
[报告生成] ──→ PDF / Excel
```

## 📊 数据库模型

### 核心表结构

1. **inspection_tasks** - 巡检任务表
2. **images** - 图片元数据表
3. **image_detections** - 图片级检测结果表
4. **raw_nest_detections** - 虫巢原始检测表
5. **unique_nests** - 去重后的唯一虫巢表

## 🔌 API 接口

### 任务管理

```
POST   /api/v1/tasks              创建巡检任务
GET    /api/v1/tasks              查询任务列表
GET    /api/v1/tasks/{id}         查询任务详情
DELETE /api/v1/tasks/{id}         删除任务
GET    /api/v1/tasks/{id}/status  查询任务状态
```

### 图片管理

```
POST   /api/v1/tasks/{id}/images   批量上传图片
GET    /api/v1/tasks/{id}/images   查询图片列表
GET    /api/v1/images/{id}         查询图片详情
GET    /api/v1/images/{id}/thumbnail  获取缩略图
```

## 🧪 测试

```bash
cd backend
pytest tests/ -v
```

## 📦 部署

### 生产环境部署

```bash
# 1. 构建镜像
docker-compose build

# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

### 环境变量

创建 `.env` 文件:

```env
DATABASE_URL=postgresql+asyncpg://nestuser:nestpass@postgres:5432/nestdb
REDIS_URL=redis://redis:6379/0
UPLOAD_DIR=./uploads
THUMBNAIL_DIR=./thumbnails
```

## 📝 开发计划

- [x] M1: 基础框架、数据库、基础API
- [ ] M2: AI推理集成、异步队列
- [ ] M3: GPS反算 + DBSCAN去重
- [ ] M4: Web后台、任务管理、报告导出
- [ ] M5: 测试优化
- [ ] M6: 部署上线

## 👥 团队成员

- 技术负责人: 架构设计、代码审查
- 后端工程师: API开发、数据库设计
- 前端工程师: 界面开发、交互实现
- QA工程师: 测试用例、质量保证
- DevOps工程师: 部署配置、CI/CD

## 📄 许可证

MIT License

## 🤝 联系方式

如有问题，请提交 Issue 或联系开发团队。

---

**版本**: V1.0.0 | **日期**: 2026-03-07
