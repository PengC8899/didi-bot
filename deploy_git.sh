#!/bin/bash
# Git部署脚本 - 确保VPS代码与本地一致
# 使用方法：./deploy_git.sh

set -e  # 遇到错误立即退出

# 配置变量（请根据实际情况修改）
VPS_USER="ubuntu"          # VPS用户名
VPS_HOST="18.142.231.74"            # VPS IP地址
VPS_PATH="/home/$VPS_USER/didi-bot"  # VPS上的项目路径
SSH_KEY="/Users/pccc/LT_bot/didi-bot/didi.pem"  # SSH密钥文件路径
GIT_BRANCH="main"                 # Git分支名

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
    
    print_success "配置检查通过"
}

# 检查本地Git状态
check_local_git() {
    print_info "检查本地Git状态..."
    
    # 检查是否在Git仓库中
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "当前目录不是Git仓库！"
        print_info "请先初始化Git仓库："
        echo "  git init"
        echo "  git add ."
        echo "  git commit -m 'Initial commit'"
        echo "  git remote add origin <your-repo-url>"
        echo "  git push -u origin main"
        exit 1
    fi
    
    # 检查是否有未提交的更改
    if ! git diff-index --quiet HEAD --; then
        print_warning "检测到未提交的更改！"
        echo "未提交的文件："
        git status --porcelain
        echo
        read -p "是否要提交这些更改？(y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            read -p "请输入提交信息: " commit_msg
            git add .
            git commit -m "$commit_msg"
        else
            print_error "请先提交或暂存更改后再部署！"
            exit 1
        fi
    fi
    
    print_success "本地Git状态正常"
}

# 推送到远程仓库
push_to_remote() {
    print_info "推送代码到远程仓库..."
    
    if ! git push origin $GIT_BRANCH; then
        print_error "推送失败！请检查网络连接和Git配置"
        exit 1
    fi
    
    print_success "代码推送成功"
}

# 在VPS上部署
deploy_to_vps() {
    print_info "连接VPS并部署..."
    
    # 创建远程执行脚本
    REMOTE_SCRIPT="
set -e
echo '🚀 开始VPS部署...'

# 检查项目目录是否存在
if [ ! -d '$VPS_PATH' ]; then
    echo '📁 项目目录不存在，正在克隆仓库...'
    git clone https://github.com/PengC8899/didi-bot.git '$VPS_PATH'
fi

cd '$VPS_PATH'

# 拉取最新代码
echo '📥 拉取最新代码...'
git fetch origin
git reset --hard origin/$GIT_BRANCH

# 检查环境变量文件
if [ ! -f '.env' ]; then
    echo '⚠️  .env文件不存在，从示例文件复制...'
    if [ -f '.env.example' ]; then
        cp .env.example .env
        echo '❗ 请编辑.env文件并填入正确的配置！'
    else
        echo '❌ .env.example文件也不存在！'
        exit 1
    fi
fi

# 停止现有服务
echo '🛑 停止现有服务...'
docker-compose down || true

# 强制删除可能存在的容器
echo '🗑️  清理旧容器...'
docker rm -f orderbot || true

# 重新构建并启动
echo '🔨 重新构建并启动服务...'
docker-compose up -d --build

# 等待服务启动
echo '⏳ 等待服务启动...'
sleep 10

# 检查服务状态
echo '🔍 检查服务状态...'
docker-compose ps

echo '📋 最近日志：'
docker-compose logs --tail=20

echo '🎉 VPS部署完成！'
"

    # 执行远程脚本
    if ! ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" "$REMOTE_SCRIPT"; then
        print_error "VPS部署失败！"
        exit 1
    fi
    
    print_success "VPS部署成功"
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
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" "$VERIFY_SCRIPT"
    
    print_success "部署验证完成"
}

# 主函数
main() {
    echo "==========================================="
    echo "🚀 DDGL Bot Git部署脚本"
    echo "==========================================="
    echo
    
    check_config
    check_local_git
    push_to_remote
    deploy_to_vps
    verify_deployment
    
    echo
    echo "==========================================="
    print_success "🎉 部署完成！"
    echo "==========================================="
    echo
    print_info "有用的命令："
    echo "  查看日志: ssh $VPS_USER@$VPS_HOST 'cd $VPS_PATH && docker-compose logs -f'"
    echo "  重启服务: ssh $VPS_USER@$VPS_HOST 'cd $VPS_PATH && docker-compose restart'"
    echo "  进入容器: ssh $VPS_USER@$VPS_HOST 'cd $VPS_PATH && docker-compose exec orderbot bash'"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi