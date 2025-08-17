#!/bin/bash

# Telegram 订单管理机器人 Docker 部署脚本
# 使用方法: ./deploy.sh [start|stop|restart|logs|build|clean]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否运行
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker 守护进程未运行，请先启动 Docker Desktop"
        log_info "在 macOS 上，请打开 Docker Desktop 应用程序"
        exit 1
    fi
}

# 检查环境变量文件
check_env() {
    if [ ! -f ".env" ]; then
        log_warning ".env 文件不存在"
        if [ -f ".env.example" ]; then
            log_info "正在从 .env.example 创建 .env 文件..."
            cp .env.example .env
            log_warning "请编辑 .env 文件并填入正确的配置信息"
            log_info "必填项: BOT_TOKEN, BOT_USERNAME, CHANNEL_ID, ALLOWED_ADMIN_IDS"
            return 1
        else
            log_error ".env.example 文件也不存在，无法创建配置文件"
            exit 1
        fi
    fi
}

# 创建必要目录
setup_directories() {
    log_info "创建必要的目录..."
    mkdir -p data images logs
    log_success "目录创建完成"
}

# 构建镜像
build_image() {
    log_info "构建 Docker 镜像..."
    docker-compose build --no-cache
    log_success "镜像构建完成"
}

# 启动服务
start_service() {
    log_info "启动服务..."
    docker-compose -f "$COMPOSE_FILE" up -d
    log_success "服务启动完成"
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 5
    
    # 检查服务状态
    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_success "机器人服务正在运行"
        log_info "使用 './deploy.sh logs $([ "$COMPOSE_FILE" = "docker-compose.prod.yaml" ] && echo "--prod" || echo "--dev")' 查看日志"
    else
        log_error "服务启动失败，请检查日志"
        docker-compose -f "$COMPOSE_FILE" logs --tail=20
    fi
}

# 停止服务
stop_service() {
    log_info "停止服务..."
    docker-compose -f "$COMPOSE_FILE" down
    log_success "服务已停止"
}

# 重启服务
restart_service() {
    log_info "重启服务..."
    docker-compose -f "$COMPOSE_FILE" restart
    log_success "服务已重启"
}

# 查看日志
show_logs() {
    log_info "显示服务日志 (按 Ctrl+C 退出)..."
    docker-compose -f "$COMPOSE_FILE" logs -f --tail=100
}

# 清理资源
clean_resources() {
    log_warning "这将删除所有容器、镜像和数据，确定要继续吗? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        log_info "停止并删除容器..."
        docker-compose -f "$COMPOSE_FILE" down --rmi all --volumes --remove-orphans
        
        log_info "清理数据目录..."
        rm -rf data/* logs/*
        
        log_success "清理完成"
    else
        log_info "取消清理操作"
    fi
}

# 显示服务状态
show_status() {
    log_info "服务状态:"
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo
    log_info "资源使用情况:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $(docker-compose -f "$COMPOSE_FILE" ps -q) 2>/dev/null || log_warning "无运行中的容器"
}

# 管理监控服务
manage_monitoring() {
    if [ ! -f "docker-compose.monitoring.yaml" ]; then
        log_error "监控配置文件不存在: docker-compose.monitoring.yaml"
        exit 1
    fi
    
    # 检查监控服务状态
    if docker-compose -f docker-compose.monitoring.yaml ps | grep -q "Up"; then
        echo -e "${YELLOW}监控服务正在运行，是否停止? (y/N)${NC}"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            log_info "停止监控服务..."
            docker-compose -f docker-compose.monitoring.yaml down
            log_success "监控服务已停止"
        fi
    else
        echo -e "${YELLOW}监控服务未运行，是否启动? (Y/n)${NC}"
        read -r response
        if [[ "$response" =~ ^([nN][oO]|[nN])$ ]]; then
            log_info "取消启动监控服务"
        else
            log_info "启动监控服务..."
            docker-compose -f docker-compose.monitoring.yaml up -d
            
            if [ $? -eq 0 ]; then
                log_success "监控服务启动成功!"
                echo -e "${BLUE}访问地址:${NC}"
                echo "  Prometheus: http://localhost:9090"
                echo "  Grafana: http://localhost:3000 (admin/admin123)"
                echo "  cAdvisor: http://localhost:8080"
                echo "  Node Exporter: http://localhost:9100"
            else
                log_error "监控服务启动失败!"
                exit 1
            fi
        fi
    fi
}

# 显示帮助信息
show_help() {
    echo -e "${BLUE}Telegram订单管理机器人 Docker部署脚本${NC}"
    echo -e "${GREEN}使用方法: $0 [命令] [选项]${NC}"
    echo
    echo "可用命令:"
    echo "  start     - 启动机器人服务"
    echo "  stop      - 停止机器人服务"
    echo "  restart   - 重启机器人服务"
    echo "  logs      - 查看实时日志"
    echo "  build     - 构建Docker镜像"
    echo "  status    - 查看服务状态"
    echo "  monitor   - 启动/停止监控服务"
    echo "  clean     - 清理所有容器和镜像"
    echo "  help      - 显示此帮助信息"
    echo
    echo "选项:"
    echo "  --prod    - 使用生产环境配置 (docker-compose.prod.yaml)"
    echo "  --dev     - 使用开发环境配置 (docker-compose.yaml, 默认)"
    echo
    echo -e "${YELLOW}首次部署步骤:${NC}"
    echo "1. 复制 .env.example 为 .env 并配置环境变量"
    echo "2. 运行: $0 build"
    echo "3. 运行: $0 start [--prod|--dev]"
    echo
    echo -e "${YELLOW}示例:${NC}"
    echo "  $0 start --prod    # 生产环境启动"
    echo "  $0 logs --dev      # 开发环境日志"
}

# 解析命令行参数
parse_args() {
    COMPOSE_FILE="docker-compose.yaml"
    COMMAND=""
    
    for arg in "$@"; do
        case $arg in
            --prod)
                COMPOSE_FILE="docker-compose.prod.yaml"
                ;;
            --dev)
                COMPOSE_FILE="docker-compose.yaml"
                ;;
            start|stop|restart|logs|build|status|monitor|clean|help)
                COMMAND="$arg"
                ;;
        esac
    done
    
    if [ -z "$COMMAND" ]; then
        COMMAND="${1:-help}"
    fi
}

# 主函数
main() {
    parse_args "$@"
    
    case "$COMMAND" in
        start)
            check_docker
            if ! check_env; then
                exit 1
            fi
            setup_directories
            build_image
            log_info "使用配置文件: $COMPOSE_FILE"
            start_service
            ;;
        stop)
            check_docker
            log_info "使用配置文件: $COMPOSE_FILE"
            stop_service
            ;;
        restart)
            check_docker
            log_info "使用配置文件: $COMPOSE_FILE"
            restart_service
            ;;
        logs)
            check_docker
            log_info "使用配置文件: $COMPOSE_FILE"
            show_logs
            ;;
        build)
            check_docker
            build_image
            ;;
        status)
            check_docker
            log_info "使用配置文件: $COMPOSE_FILE"
            show_status
            ;;
        monitor)
            check_docker
            manage_monitoring
            ;;
        clean)
            check_docker
            clean_resources
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $COMMAND"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"