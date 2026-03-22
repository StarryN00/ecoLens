#!/bin/bash
# 樟巢螟智能检测系统 - 开发监控脚本
# 用法: ./monitor.sh [间隔秒数]

INTERVAL=${1:-600}  # 默认600秒(10分钟)
PROJECT_DIR="/Users/starryn/project/ecoLens"

echo "🚀 启动开发监控系统"
echo "项目目录: $PROJECT_DIR"
echo "检查间隔: ${INTERVAL}秒"
echo "按 Ctrl+C 停止"
echo "========================================="

while true; do
    clear
    echo "📊 $(date '+%Y-%m-%d %H:%M:%S') 开发状态检查"
    echo "========================================="
    
    # 检查目录结构
    echo ""
    echo "📁 项目结构:"
    if [ -d "$PROJECT_DIR/backend" ]; then
        echo "  ✅ backend/ 目录已创建"
        PY_FILES=$(find $PROJECT_DIR/backend -name "*.py" 2>/dev/null | wc -l)
        echo "     Python文件: $PY_FILES 个"
    else
        echo "  ⏳ backend/ 目录待创建"
    fi
    
    if [ -d "$PROJECT_DIR/frontend" ]; then
        echo "  ✅ frontend/ 目录已创建"
        TS_FILES=$(find $PROJECT_DIR/frontend -name "*.tsx" -o -name "*.ts" 2>/dev/null | wc -l)
        echo "     TypeScript文件: $TS_FILES 个"
    else
        echo "  ⏳ frontend/ 目录待创建"
    fi
    
    if [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
        echo "  ✅ docker-compose.yml 已创建"
    else
        echo "  ⏳ docker-compose.yml 待创建"
    fi
    
    # 检查最近修改
    echo ""
    echo "📝 最近修改的文件:"
    find $PROJECT_DIR -type f \( -name "*.py" -o -name "*.tsx" -o -name "*.ts" -o -name "*.yml" -o -name "*.json" \) -mtime -1 2>/dev/null | head -10 | while read file; do
        echo "  - $(basename $file)"
    done
    
    echo ""
    echo "========================================="
    echo "下次检查: $(date -v+${INTERVAL}S '+%H:%M:%S')"
    echo "========================================="
    
    sleep $INTERVAL
done
