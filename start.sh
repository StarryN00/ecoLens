#!/bin/bash
# 樟巢螟智能检测系统 - 启动脚本
# 使用方法: ./start.sh [start|stop|status|logs]

PROJECT_DIR="/Users/starryn/project/ecoLens"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

color_green() { echo -e "\033[32m$1\033[0m"; }
color_red() { echo -e "\033[31m$1\033[0m"; }
color_yellow() { echo -e "\033[33m$1\033[0m"; }

start_backend() {
    color_green "正在启动后端服务..."
    cd "$BACKEND_DIR"
    source venv/bin/activate
    nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/backend.log 2>&1 &
    sleep 3
    if curl -s http://localhost:8000/health > /dev/null; then
        color_green "✅ 后端服务已启动: http://localhost:8000"
    else
        color_red "❌ 后端服务启动失败，请检查日志: /tmp/backend.log"
    fi
}

start_frontend() {
    color_green "正在启动前端服务..."
    cd "$FRONTEND_DIR"
    nohup npm run dev > /tmp/frontend.log 2>&1 &
    sleep 4
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/ | grep -q "200"; then
        color_green "✅ 前端服务已启动: http://localhost:5173"
    else
        color_red "❌ 前端服务启动失败，请检查日志: /tmp/frontend.log"
    fi
}

stop_services() {
    color_yellow "正在停止服务..."
    pkill -f "uvicorn app.main:app" 2>/dev/null
    lsof -ti:5173 | xargs kill -9 2>/dev/null
    color_green "✅ 服务已停止"
}

check_status() {
    color_yellow "=== 服务状态检查 ==="
    
    # 检查后端
    if curl -s http://localhost:8000/health > /dev/null; then
        color_green "✅ 后端服务: 运行中 (http://localhost:8000)"
        curl -s http://localhost:8000/ | jq -r '"   API: \(.message) | 版本: \(.version)"' 2>/dev/null
    else
        color_red "❌ 后端服务: 未运行"
    fi
    
    # 检查前端
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/ | grep -q "200"; then
        color_green "✅ 前端服务: 运行中 (http://localhost:5173)"
    else
        color_red "❌ 前端服务: 未运行"
    fi
    
    # 检查数据库
    if [ -f "$BACKEND_DIR/nestdb.sqlite" ]; then
        color_green "✅ 数据库: 已创建 ($(ls -lh $BACKEND_DIR/nestdb.sqlite | awk '{print $5}'))"
    fi
    
    # 检查模型
    if ls $BACKEND_DIR/models/*.pt 1> /dev/null 2>&1; then
        color_green "✅ AI 模型: 已配置"
        ls -lh $BACKEND_DIR/models/*.pt | awk '{print "   - " $9 " (" $5 ")"}'
    else
        color_yellow "⚠️  AI 模型: 未配置 (检测功能将不可用)"
    fi
}

show_logs() {
    color_yellow "=== 日志查看 ==="
    color_green "后端日志 (Ctrl+C 退出):"
    tail -f /tmp/backend.log &
    TAIL_PID=$!
    sleep 1
    read -p "按回车键停止查看日志..."
    kill $TAIL_PID 2>/dev/null
}

case "${1:-start}" in
    start)
        start_backend
        start_frontend
        echo ""
        color_green "🎉 系统启动完成!"
        color_green "   前端: http://localhost:5173"
        color_green "   后端: http://localhost:8000"
        color_green "   API 文档: http://localhost:8000/docs"
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 2
        start_backend
        start_frontend
        ;;
    status)
        check_status
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "使用方法: $0 [start|stop|restart|status|logs]"
        echo ""
        echo "命令说明:"
        echo "  start   - 启动前后端服务 (默认)"
        echo "  stop    - 停止所有服务"
        echo "  restart - 重启服务"
        echo "  status  - 查看服务状态"
        echo "  logs    - 查看后端日志"
        ;;
esac
