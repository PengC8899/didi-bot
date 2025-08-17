#!/bin/bash
# Docker镜像部署脚本 - 构建镜像并部署到VPS
# 使用方法：./deploy_docker.sh

set -e  # 遇到错误立即退出

# 配置变量（请根据实际情况修改）
VPS_USER="your-username"          # VPS用户名
VPS_HOST="your-vps-ip"            # VPS IP地址
IMAGE_NAME="ddgl-orderbot"        # Docker镜像名称
IMAGE_TAG="latest"                # 镜像标签
REGISTRY=""                       # Docker Registry（可选，如：your-registry.com/）
CONTAINER_NAME="orderbot"         # 容器名称
VPS_PATH="/home/$VPS_USER/DDGL_bot"  # VPS上的项目路径

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
    
    # 检查Docker是否安装
    if ! command -v docker &> /dev/null; then
        print_error "Docker未安装！请先安装Docker"
        exit 1
    fi
    
    # 检查Docker是否运行
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker未运行！请启动Docker服务"
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

# 构建Docker镜像
build_image() {
    print_info "构建Docker镜像..."
    
    # 检查Dockerfile是否存在
    if [ ! -f "Dockerfile" ]; then
        print_error "未找到Dockerfile！"
        exit 1
    fi
    
    # 构建镜像
    FULL_IMAGE_NAME="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}"
    
    print_info "构建镜像: $FULL_IMAGE_NAME"
    
    if docker build -t "$FULL_IMAGE_NAME" .; then
        print_success "镜像构建成功"
    else
        print_error "镜像构建失败！"
        exit 1
    fi
    
    # 显示镜像信息
    print_info "镜像信息："
    docker images "$FULL_IMAGE_NAME"
}

# 保存镜像到文件
save_image() {
    print_info "保存镜像到文件..."
    
    FULL_IMAGE_NAME="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}"
    IMAGE_FILE="${IMAGE_NAME}-${IMAGE_TAG}.tar"
    
    if docker save -o "$IMAGE_FILE" "$FULL_IMAGE_NAME"; then
        print_success "镜像已保存到: $IMAGE_FILE"
        
        # 显示文件大小
        FILE_SIZE=$(du -h "$IMAGE_FILE" | cut -f1)
        print_info "文件大小: $FILE_SIZE"
    else
        print_error "镜像保存失败！"
        exit 1
    fi
}

# 上传镜像到VPS
upload_image() {
    print_info "上传镜像到VPS..."
    
    IMAGE_FILE="${IMAGE_NAME}-${IMAGE_TAG}.tar"
    
    # 创建VPS目录
    ssh "$VPS_USER@$VPS_HOST" "mkdir -p '$VPS_PATH'"
    
    # 上传镜像文件
    if scp "$IMAGE_FILE" "$VPS_USER@$VPS_HOST:$VPS_PATH/"; then
        print_success "镜像上传成功"
    else
        print_error "镜像上传失败！"
        exit 1
    fi
    
    # 清理本地镜像文件
    rm -f "$IMAGE_FILE"
    print_info "本地镜像文件已清理"
}

# 在VPS上加载镜像
load_image_on_vps() {
    print_info "在VPS上加载镜像..."
    
    IMAGE_FILE="${IMAGE_NAME}-${IMAGE_TAG}.tar"
    FULL_IMAGE_NAME="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}"
    
    LOAD_SCRIPT="
set -e
cd '$VPS_PATH'

echo '📦 加载Docker镜像...'
if docker load -i '$IMAGE_FILE'; then
    echo '✅ 镜像加载成功'
else
    echo '❌ 镜像加载失败'
    exit 1
fi

echo '🗑️  清理镜像文件...'
rm -f '$IMAGE_FILE'

echo '📋 镜像列表：'
docker images '$FULL_IMAGE_NAME'
"
    
    if ssh "$VPS_USER@$VPS_HOST" "$LOAD_SCRIPT"; then
        print_success "镜像加载完成"
    else
        print_error "镜像加载失败！"
        exit 1
    fi
}

# 上传配置文件
upload_configs() {
    print_info "上传配置文件..."
    
    # 上传docker-compose文件
    if [ -f "docker-compose.prod.yaml" ]; then
        scp "docker-compose.prod.yaml" "$VPS_USER@$VPS_HOST:$VPS_PATH/docker-compose.yaml"
        print_success "生产环境docker-compose文件已上传"
    elif [ -f "docker-compose.yaml" ]; then
        scp "docker-compose.yaml" "$VPS_USER@$VPS_HOST:$VPS_PATH/"
        print_success "docker-compose文件已上传"
    else
        print_warning "未找到docker-compose文件"
    fi
    
    # 检查.env文件
    if ssh "$VPS_USER@$VPS_HOST" "[ ! -f '$VPS_PATH/.env' ]"; then
        if [ -f ".env.example" ]; then
            scp ".env.example" "$VPS_USER@$VPS_HOST:$VPS_PATH/"
            ssh "$VPS_USER@$VPS_HOST" "cd '$VPS_PATH' && cp .env.example .env"
            print_warning "已创建.env文件，请登录VPS编辑配置！"
        else
            print_warning "请手动创建VPS上的.env文件"
        fi
    else
        print_success "VPS上已存在.env文件"
    fi
}

# 部署容器
deploy_container() {
    print_info "部署容器..."
    
    FULL_IMAGE_NAME="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}"
    
    DEPLOY_SCRIPT="
set -e
cd '$VPS_PATH'

echo '🛑 停止现有容器...'
docker-compose down || true

echo '🗑️  清理旧容器和镜像...'
docker container prune -f || true
docker image prune -f || true

echo '🚀 启动新容器...'
if [ -f 'docker-compose.yaml' ]; then
    # 更新docker-compose中的镜像名称
    sed -i.bak \"s|image:.*orderbot.*|image: $FULL_IMAGE_NAME|g\" docker-compose.yaml
    docker-compose up -d
else
    # 直接运行容器
    docker run -d \\
        --name '$CONTAINER_NAME' \\
        --restart unless-stopped \\
        --env-file .env \\
        -v \$(pwd)/data:/app/data \\
        -v \$(pwd)/logs:/app/logs \\
        -v \$(pwd)/images:/app/images \\
        '$FULL_IMAGE_NAME'
fi

echo '⏳ 等待容器启动...'
sleep 10

echo '🔍 检查容器状态...'
if [ -f 'docker-compose.yaml' ]; then
    docker-compose ps
    docker-compose logs --tail=20
else
    docker ps --filter name='$CONTAINER_NAME'
    docker logs --tail=20 '$CONTAINER_NAME'
fi

echo '🎉 容器部署完成！'
"
    
    if ssh "$VPS_USER@$VPS_HOST" "$DEPLOY_SCRIPT"; then
        print_success "容器部署成功"
    else
        print_error "容器部署失败！"
        exit 1
    fi
}

# 验证部署
verify_deployment() {
    print_info "验证部署结果..."
    
    VERIFY_SCRIPT="
cd '$VPS_PATH'

echo '容器状态：'
if [ -f 'docker-compose.yaml' ]; then
    docker-compose ps
else
    docker ps --filter name='$CONTAINER_NAME'
fi

echo
echo '服务健康检查：'
if [ -f 'docker-compose.yaml' ]; then
    if docker-compose exec -T orderbot python -c 'print(\"Bot is running\")' 2>/dev/null; then
        echo '✅ 机器人服务正常'
    else
        echo '❌ 机器人服务异常'
        echo '错误日志：'
        docker-compose logs --tail=10 orderbot
    fi
else
    if docker exec '$CONTAINER_NAME' python -c 'print(\"Bot is running\")' 2>/dev/null; then
        echo '✅ 机器人服务正常'
    else
        echo '❌ 机器人服务异常'
        echo '错误日志：'
        docker logs --tail=10 '$CONTAINER_NAME'
    fi
fi
"
    
    ssh "$VPS_USER@$VPS_HOST" "$VERIFY_SCRIPT"
    
    print_success "部署验证完成"
}

# 清理本地资源
cleanup_local() {
    print_info "清理本地资源..."
    
    # 可选：删除本地镜像以节省空间
    read -p "是否删除本地Docker镜像以节省空间？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        FULL_IMAGE_NAME="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}"
        docker rmi "$FULL_IMAGE_NAME" || true
        print_success "本地镜像已删除"
    else
        print_info "保留本地镜像"
    fi
}

# 显示部署信息
show_deployment_info() {
    print_info "部署信息总结..."
    
    FULL_IMAGE_NAME="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}"
    
    echo "部署详情："
    echo "  镜像名称: $FULL_IMAGE_NAME"
    echo "  VPS地址: $VPS_HOST"
    echo "  项目路径: $VPS_PATH"
    echo "  容器名称: $CONTAINER_NAME"
    echo
    
    # 获取VPS上的镜像信息
    VPS_IMAGE_INFO=$(ssh "$VPS_USER@$VPS_HOST" "docker images '$FULL_IMAGE_NAME' --format 'table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}'" | tail -n +2)
    
    if [ -n "$VPS_IMAGE_INFO" ]; then
        echo "VPS镜像信息："
        echo "  $VPS_IMAGE_INFO"
    fi
}

# 主函数
main() {
    echo "==========================================="
    echo "🐳 DDGL Bot Docker镜像部署脚本"
    echo "==========================================="
    echo
    
    check_config
    check_ssh_connection
    build_image
    save_image
    upload_image
    load_image_on_vps
    upload_configs
    deploy_container
    verify_deployment
    cleanup_local
    show_deployment_info
    
    echo
    echo "==========================================="
    print_success "🎉 Docker镜像部署完成！"
    echo "==========================================="
    echo
    print_info "有用的命令："
    echo "  查看日志: ssh $VPS_USER@$VPS_HOST 'cd $VPS_PATH && docker-compose logs -f'"
    echo "  重启服务: ssh $VPS_USER@$VPS_HOST 'cd $VPS_PATH && docker-compose restart'"
    echo "  进入容器: ssh $VPS_USER@$VPS_HOST 'cd $VPS_PATH && docker-compose exec orderbot bash'"
    echo "  重新部署: ./deploy_docker.sh"
    echo
    print_warning "注意：Docker镜像部署确保了环境一致性，但镜像较大，传输时间较长！"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi