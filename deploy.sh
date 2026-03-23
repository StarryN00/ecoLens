#!/bin/bash
# 服务器部署脚本 - deploy.sh
# 在服务器上执行: bash deploy.sh

set -e

echo "=== 樟巢螟智能检测系统部署脚本 ==="

# 1. 安装依赖
echo "[1/6] 安装系统依赖..."
sudo apt-get update -qq
sudo apt-get install -y -qq docker.io docker-compose git redis-server
sudo systemctl start docker redis-server
sudo usermod -aG docker $USER

# 2. 克隆项目
echo "[2/6] 克隆项目..."
cd ~
if [ -d "ecoLens" ]; then
    cd ecoLens && git pull origin main
else
    git clone https://github.com/StarryN00/ecoLens.git
    cd ecoLens
fi

# 3. 配置环境
echo "[3/6] 配置环境..."
cat > backend/.env << 'EOF'
DATABASE_URL=sqlite+aiosqlite:///./nestdb.sqlite
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=sqla+sqlite:///celerydb.sqlite
CELERY_RESULT_BACKEND=db+sqlite:///celerydb.sqlite
UPLOAD_DIR=./uploads
THUMBNAIL_DIR=./thumbnails
TREE_MODEL_PATH=./models/best.pt
NEST_MODEL_PATH=./models/best.pt
NEST_DETECTION_MODEL_PATH=./models/best.pt
TREE_CLASSIFICATION_MODEL_PATH=./models/best.pt
CONFIDENCE_THRESHOLD=0.005
DEBUG=False
APP_NAME=樟巢螟智能检测系统
EOF

# 4. 创建模型目录
echo "[4/6] 准备模型目录..."
mkdir -p backend/models uploads thumbnails

# 5. 构建并启动 Docker 容器
echo "[5/6] 构建并启动服务..."
sudo docker-compose down 2>/dev/null || true
sudo docker-compose up --build -d

# 6. 检查状态
echo "[6/6] 检查服务状态..."
sleep 5
sudo docker-compose ps

echo ""
echo "=== 部署完成 ==="
echo "前端访问: http://81.68.224.178:5173"
echo "后端 API: http://81.68.224.178:8000"
echo "API文档: http://81.68.224.178:8000/docs"
echo ""
echo "查看日志: sudo docker-compose logs -f"
echo "停止服务: sudo docker-compose down"
echo "重启服务: sudo docker-compose restart"
