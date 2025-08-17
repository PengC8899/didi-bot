#!/bin/bash
# rsync部署脚本 - 直接同步文件到VPS
# 使用方法：./deploy_rsync.sh

set -e  # 遇到错误立即退出

# 配置变量（请根据实际情况修改）
VPS_USER="your-username"          # VPS用户名
VPS_HOST="your-vps-ip"            # VPS IP地址
VPS_PATH="/home/$VPS_USER/DDGL_bot"  # VPS上的项目路径
LOCAL_PATH="$(pwd)"               # 本地项目路径

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查配置
check_config() {
    print_info "检查配置..."
    
    if [ "$VPS_USER" = "your-username" ] || [ "$VPS_HOST" = "your-vps-ip" ]; then
        print_error "请先修改脚本中的VPS配置信息！"
        print_info "需要修改的变量："
        echo "  - VPS_USER: VPS用户名"
        echo "  - VPS_HOST: VPS IP地址或域名"
        exit 1
    fi
    
    # 检查rsync是否安装
    if ! command -v rsync &> /dev/null; then
        print_error "rsync未安装！请先安装rsync"
        print_info "macOS安装: brew install rsync"
        print_info "Ubuntu安装: sudo apt-get install rsync"
        exit 1
    fi
    
    print_success "配置检查通过"
}

# 检查SSH连接
check_ssh_connection() {
    print_info "检查SSH连接..."
    
    if ! ssh -o ConnectTimeout=10 "$VPS_USER@$VPS_HOST" "echo 'SSH连接正常'" > /dev/null 2>&1; then
        print_error "无法连接到VPS！"
        print_info "请检查："
        echo "  - VPS IP地址是否正确"
        echo "  - SSH服务是否运行"
        echo "  - 防火墙是否允许SSH连接"
        echo "  - SSH密钥是否配置正确"
        exit 1
    fi
    
    print_success "SSH连接正常"
}

# 创建VPS目录
create_vps_directory() {
    print_info "创建VPS项目目录..."
    
    ssh "$VPS_USER@$VPS_HOST" "mkdir -p '$VPS_PATH'"
    
    print_success "VPS目录创建完成"
}

# 同步文件到VPS
sync_files() {
    print_info "同步文件到VPS..."
    
    # 显示将要同步的文件
    print_info "预览同步内容..."
    rsync -avz --dry-run --delete \
        --exclude='.git/' \
        --exclude='.venv/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='*.pyo' \
        --exclude='.pytest_cache/' \
        --exclude='.coverage' \
        --exclude='.env' \
        --exclude='data/' \
        --exclude='logs/' \
        --exclude='images/' \
        --exclude='*.log' \
        --exclude='.DS_Store' \
        --exclude='Thumbs.db' \
        "$LOCAL_PATH/" "$VPS_USER@$VPS_HOST:$VPS_PATH/" | head -20
    
    echo
    read -p "确认同步以上文件？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "用户取消同步"
        exit 0
    fi
    
    # 执行实际同步
    print_info "开始同步文件..."
    
    if rsync -avz --delete --progress \
        --exclude='.git/' \
        --exclude='.venv/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='*.pyo' \
        --exclude='.pytest_cache/' \
        --exclude='.coverage' \
        --exclude='.env' \
        --exclude='data/' \
        --exclude='logs/' \
        --exclude='images/' \
        --exclude='*.log' \
        --exclude='.DS_Store' \
        --exclude='Thumbs.db' \
        "$LOCAL_PATH/" "$VPS_USER@$VPS_HOST:$VPS_PATH/"; then
        print_success "文件同步完成"
    else
        print_error "文件同步失败！"
        exit 1
    fi
}

# 处理环境变量文件
handle_env_file() {
    print_info "处理环境变量文件..."
    
    # 检查VPS上是否有.env文件
    if ssh "$VPS_USER@$VPS_HOST" "[ -f '$VPS_PATH/.env' ]"; then
        print_success "VPS上已存在.env文件"
    else
        print_warning "VPS上不存在.env文件"
        
        # 检查是否有.env.example
        if ssh "$VPS_USER@$VPS_HOST" "[ -f '$VPS_PATH/.env.example' ]"; then
            print_info "从.env.example创建.env文件..."
            ssh "$VPS_USER@$VPS_HOST" "cd '$VPS_PATH' && cp .env.example .env"
            print_warning "请登录VPS编辑.env文件并填入正确的配置！"
            echo "  ssh $VPS_USER@$VPS_HOST"
            echo "  cd $VPS_PATH"
            echo "  vim .env"
        else
            print_error "未找到.env.example文件！"
            print_info "请手动创建.env文件"
        fi
    fi
}

# 重启VPS服务
restart_services() {
    print_info "重启VPS服务..."
    
    # 创建远程执行脚本
    REMOTE_SCRIPT="
set -e
cd '$VPS_PATH'

echo '🛑 停止现有服务...'
docker-compose down || true

echo '🔨 重新构建并启动服务...'
docker-compose up -d --build

echo '⏳ 等待服务启动...'
sleep 10

echo '🔍 检查服务状态...'
docker-compose ps

echo '📋 最近日志：'
docker-compose logs --tail=20

echo '🎉 服务重启完成！'
"
    
    if ssh "$VPS_USER@$VPS_HOST" "$REMOTE_SCRIPT"; then
        print_success "服务重启成功"
    else
        print_error "服务重启失败！"
        print_info "请手动检查VPS上的服务状态"
        exit 1
    fi
}

# 验证部署
verify_deployment() {
    print_info "验证部署结果..."
    
    # 检查服务状态
    VERIFY_SCRIPT="
cd '$VPS_PATH'
echo '容器状态：'
docker-compose ps
echo
echo '服务健康检查：'
if docker-compose exec -T orderbot python -c 'print(\"Bot is running\")' 2>/dev/null; then
    echo '✅ 机器人服务正常'
else
    echo '❌ 机器人服务异常'
    echo '错误日志：'
    docker-compose logs --tail=10 orderbot
fi
"
    
    ssh "$VPS_USER@$VPS_HOST" "$VERIFY_SCRIPT"
    
    print_success "部署验证完成"
}

# 显示同步统计
show_sync_stats() {
    print_info "同步统计信息..."
    
    # 获取文件数量和大小
    LOCAL_FILES=$(find "$LOCAL_PATH" -type f ! -path "*/.*" ! -path "*/__pycache__/*" ! -path "*/data/*" ! -path "*/logs/*" | wc -l)
    LOCAL_SIZE=$(du -sh "$LOCAL_PATH" 2>/dev/null | cut -f1 || echo "未知")
    
    echo "本地项目统计："
    echo "  文件数量: $LOCAL_FILES"
    echo "  项目大小: $LOCAL_SIZE"
    echo
    
    # 获取VPS上的信息
    VPS_STATS=$(ssh "$VPS_USER@$VPS_HOST" "cd '$VPS_PATH' && echo \"文件数量: \$(find . -type f ! -path './.*' ! -path './__pycache__/*' ! -path './data/*' ! -path './logs/*' | wc -l)\" && echo \"项目大小: \$(du -sh . 2>/dev/null | cut -f1)\"")
    
    echo "VPS项目统计："
    echo "  $VPS_STATS"
}

# 主函数
main() {
    echo "==========================================="
    echo "🔄 DDGL Bot rsync部署脚本"
    echo "==========================================="
    echo
    
    check_config
    check_ssh_connection
    create_vps_directory
    sync_files
    handle_env_file
    restart_services
    verify_deployment
    show_sync_stats
    
    echo
    echo "==========================================="
    print_success "🎉 rsync部署完成！"
    echo "==========================================="
    echo
    print_info "有用的命令："
    echo "  查看日志: ssh $VPS_USER@$VPS_HOST 'cd $VPS_PATH && docker-compose logs -f'"
    echo "  重启服务: ssh $VPS_USER@$VPS_HOST 'cd $VPS_PATH && docker-compose restart'"
    echo "  进入容器: ssh $VPS_USER@$VPS_HOST 'cd $VPS_PATH && docker-compose exec orderbot bash'"
    echo "  再次同步: ./deploy_rsync.sh"
    echo
    print_warning "注意：rsync部署不包含版本控制，建议定期备份重要数据！"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi