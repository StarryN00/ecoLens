# 生产环境部署指南

## 快速开始

### 1. 准备环境

```bash
# 安装Docker和Docker Compose
# 确保Docker版本 >= 20.10, Docker Compose >= 2.0

# 克隆项目
git clone <your-repo>
cd nest-detection-system
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，设置安全密码
nano .env
```

**必需的环境变量：**
```env
POSTGRES_USER=nestuser
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=nestdb
REDIS_PASSWORD=your-secure-password
SECRET_KEY=your-random-secret-key
FRONTEND_PORT=80
```

### 3. 准备AI模型

将训练好的模型文件放入 `models/` 目录：
```
models/
├── nest_det.pt          # YOLOv8虫巢检测模型
└── tree_seg.pt          # DeepLabV3+树种识别模型
```

### 4. 启动服务

```bash
# 基础部署（包含所有核心服务）
docker-compose -f docker-compose.prod.yml up -d

# 带Nginx反向代理的部署
docker-compose -f docker-compose.prod.yml --profile with-nginx up -d
```

### 5. 验证部署

```bash
# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f backend

# 健康检查
curl http://localhost:8000/health
curl http://localhost/
```

## 服务架构

```
┌─────────────────┐
│     Nginx       │  ← 可选，提供HTTPS和负载均衡
│   (Port 8080)   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐  ┌──▼────┐
│Frontend│  │Backend│
│  :80   │  │ :8000 │
└───┬────┘  └──┬────┘
    │          │
    │    ┌─────┴─────┐
    │    │           │
┌───▼────▼─┐    ┌────▼────┐
│ Postgres │    │  Redis  │
│  :5432   │    │  :6379  │
└──────────┘    └─────────┘
```

## 常用命令

### 服务管理
```bash
# 启动
docker-compose -f docker-compose.prod.yml up -d

# 停止
docker-compose -f docker-compose.prod.yml down

# 重启
docker-compose -f docker-compose.prod.yml restart

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f [service-name]

# 更新（拉取最新镜像并重启）
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

### 数据备份
```bash
# 备份数据库
docker exec nest-postgres-prod pg_dump -U nestuser nestdb > backup_$(date +%Y%m%d).sql

# 备份上传的文件
tar -czvf uploads_backup_$(date +%Y%m%d).tar.gz /var/lib/docker/volumes/nest-detection-system_uploads_data/_data
```

### 数据恢复
```bash
# 恢复数据库
cat backup_20240307.sql | docker exec -i nest-postgres-prod psql -U nestuser -d nestdb

# 恢复上传的文件
tar -xzvf uploads_backup_20240307.tar.gz -C /
```

## 性能优化

### 调整Worker数量
编辑 `docker-compose.prod.yml`：
```yaml
worker:
  command: celery -A app.core.celery_app worker --loglevel=info --concurrency=4
```

### 数据库优化
在 `postgres` 服务中添加：
```yaml
command: postgres -c 'max_connections=200' -c 'shared_buffers=256MB'
```

### 启用GPU加速（可选）
如果有NVIDIA GPU，修改 `worker` 服务：
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

## 安全建议

1. **使用HTTPS**
   - 配置Nginx SSL证书
   - 使用Let's Encrypt免费证书

2. **防火墙设置**
   ```bash
   # 只开放必要的端口
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

3. **定期更新**
   ```bash
   # 更新基础镜像
   docker-compose -f docker-compose.prod.yml pull
   docker-compose -f docker-compose.prod.yml up -d
   ```

4. **监控和告警**
   - 配置日志收集（ELK/Loki）
   - 设置资源监控（Prometheus/Grafana）

## 故障排除

### 服务无法启动
```bash
# 查看详细日志
docker-compose -f docker-compose.prod.yml logs --tail=100 [service-name]

# 检查端口占用
netstat -tulpn | grep 80
```

### 数据库连接失败
```bash
# 检查数据库状态
docker exec nest-postgres-prod pg_isready -U nestuser

# 重置数据库（会丢失数据！）
docker-compose -f docker-compose.prod.yml down -v
docker-compose -f docker-compose.prod.yml up -d
```

### Worker不处理任务
```bash
# 检查Worker状态
docker exec nest-worker-prod celery -A app.core.celery_app inspect stats

# 重启Worker
docker-compose -f docker-compose.prod.yml restart worker
```

## 升级指南

### 更新应用代码
```bash
# 1. 拉取最新代码
git pull origin main

# 2. 重新构建镜像
docker-compose -f docker-compose.prod.yml build

# 3. 重启服务
docker-compose -f docker-compose.prod.yml up -d
```

### 更新模型
```bash
# 1. 替换模型文件
# 2. 重启Worker
docker-compose -f docker-compose.prod.yml restart worker
```
