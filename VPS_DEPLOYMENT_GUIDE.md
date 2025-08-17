# VPS部署指南 - 确保代码同步

本指南介绍如何将DDGL订单机器人部署到VPS，并确保上传的代码与本地保持一致。

## 🎯 核心目标

确保VPS上运行的代码与本地开发环境完全一致，避免因代码不同步导致的问题。

## 📋 部署方案对比

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| Git部署 | 版本控制、回滚容易、团队协作 | 需要Git仓库 | ⭐⭐⭐⭐⭐ |
| rsync同步 | 简单直接、支持增量同步 | 无版本控制 | ⭐⭐⭐ |
| Docker镜像 | 环境一致性最佳 | 镜像构建时间长 | ⭐⭐⭐⭐ |
| SCP/SFTP | 最简单 | 手动操作、易出错 | ⭐⭐ |

---

## 🚀 方案一：Git部署（推荐）

### 优势
- ✅ 版本控制，可追踪每次部署
- ✅ 支持回滚到任意版本
- ✅ 团队协作友好
- ✅ 自动化部署容易实现

### 部署步骤

#### 1. 本地准备Git仓库

```bash
# 如果还没有初始化Git仓库
cd /Users/pccc/DDGL_bot
git init
git add .
git commit -m "Initial commit"

# 添加远程仓库（GitHub/GitLab/Gitee等）
git remote add origin https://github.com/yourusername/DDGL_bot.git
git push -u origin main
```

#### 2. VPS上克隆代码

```bash
# 登录VPS
ssh user@your-vps-ip

# 克隆代码
git clone https://github.com/yourusername/DDGL_bot.git
cd DDGL_bot

# 复制环境变量文件
cp .env.example .env
# 编辑.env文件，填入正确的配置
vim .env
```

#### 3. 部署脚本

创建自动化部署脚本：

```bash
#!/bin/bash
# deploy.sh

set -e  # 遇到错误立即退出

echo "🚀 开始部署..."

# 拉取最新代码
echo "📥 拉取最新代码..."
git fetch origin
git reset --hard origin/main

# 停止现有容器
echo "🛑 停止现有服务..."
docker-compose down

# 重新构建并启动
echo "🔨 重新构建并启动服务..."
docker-compose up -d --build

# 检查服务状态
echo "✅ 检查服务状态..."
docker-compose ps
docker-compose logs --tail=20

echo "🎉 部署完成！"
```

#### 4. 使用部署脚本

```bash
# 本地推送代码
git add .
git commit -m "Update features"
git push origin main

# VPS上部署
ssh user@your-vps-ip
cd DDGL_bot
./deploy.sh
```

---

## 🔄 方案二：rsync同步

### 适用场景
- 不想使用Git
- 需要快速同步文件
- 临时部署测试

### 同步脚本

```bash
#!/bin/bash
# sync_to_vps.sh

VPS_USER="your-username"
VPS_HOST="your-vps-ip"
VPS_PATH="/home/$VPS_USER/DDGL_bot"
LOCAL_PATH="/Users/pccc/DDGL_bot"

echo "🔄 同步代码到VPS..."

# 排除不需要同步的文件
rsync -avz --delete \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='data/' \
  --exclude='logs/' \
  --exclude='images/' \
  "$LOCAL_PATH/" "$VPS_USER@$VPS_HOST:$VPS_PATH/"

echo "✅ 同步完成！"

# 远程重启服务
echo "🔄 重启服务..."
ssh "$VPS_USER@$VPS_HOST" "cd $VPS_PATH && docker-compose down && docker-compose up -d --build"

echo "🎉 部署完成！"
```

### 使用方法

```bash
# 给脚本执行权限
chmod +x sync_to_vps.sh

# 执行同步
./sync_to_vps.sh
```

---

## 🐳 方案三：Docker镜像部署

### 优势
- ✅ 环境完全一致
- ✅ 依赖隔离
- ✅ 可以使用Docker Hub等镜像仓库

### 构建和推送镜像

```bash
# 本地构建镜像
docker build -t yourusername/ddgl-bot:latest .

# 推送到Docker Hub
docker login
docker push yourusername/ddgl-bot:latest
```

### VPS上拉取和运行

```bash
# VPS上拉取镜像
docker pull yourusername/ddgl-bot:latest

# 修改docker-compose.yaml使用远程镜像
# image: yourusername/ddgl-bot:latest

# 启动服务
docker-compose up -d
```

---

## 🔧 自动化部署配置

### GitHub Actions示例

创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy to VPS

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - name: Deploy to VPS
      uses: appleboy/ssh-action@v0.1.5
      with:
        host: ${{ secrets.VPS_HOST }}
        username: ${{ secrets.VPS_USER }}
        key: ${{ secrets.VPS_SSH_KEY }}
        script: |
          cd DDGL_bot
          git pull origin main
          docker-compose down
          docker-compose up -d --build
```

### Webhook自动部署

在VPS上设置webhook服务：

```python
# webhook_server.py
from flask import Flask, request
import subprocess
import hmac
import hashlib

app = Flask(__name__)
SECRET = "your-webhook-secret"

@app.route('/webhook', methods=['POST'])
def webhook():
    # 验证签名
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        return 'Unauthorized', 401
    
    # 执行部署
    subprocess.run(['./deploy.sh'], cwd='/path/to/DDGL_bot')
    return 'OK', 200

def verify_signature(payload, signature):
    expected = 'sha256=' + hmac.new(
        SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000)
```

---

## 📝 部署检查清单

### 部署前检查
- [ ] 本地代码已提交并推送
- [ ] 环境变量文件已配置
- [ ] Docker和docker-compose已安装
- [ ] 防火墙端口已开放
- [ ] SSL证书已配置（如需要）

### 部署后验证
- [ ] 容器正常运行：`docker-compose ps`
- [ ] 日志无错误：`docker-compose logs`
- [ ] 机器人响应正常
- [ ] 数据库连接正常
- [ ] 文件上传功能正常

### 常见问题排查

```bash
# 检查容器状态
docker-compose ps

# 查看详细日志
docker-compose logs -f orderbot

# 进入容器调试
docker-compose exec orderbot bash

# 检查网络连接
docker-compose exec orderbot ping api.telegram.org

# 重新构建镜像
docker-compose build --no-cache
```

---

## 🔒 安全建议

1. **使用SSH密钥认证**
   ```bash
   ssh-keygen -t rsa -b 4096
   ssh-copy-id user@your-vps-ip
   ```

2. **设置防火墙**
   ```bash
   ufw allow ssh
   ufw allow 80
   ufw allow 443
   ufw enable
   ```

3. **定期备份**
   ```bash
   # 备份数据库
   docker-compose exec orderbot sqlite3 /app/data/orderbot.db ".backup /app/data/backup.db"
   
   # 备份到本地
   scp user@vps:/path/to/backup.db ./backups/
   ```

4. **环境变量安全**
   - 不要将`.env`文件提交到Git
   - 使用强密码和随机密钥
   - 定期更换敏感信息

---

## 📚 总结

**推荐部署流程：**

1. 使用Git进行版本控制
2. 创建自动化部署脚本
3. 配置CI/CD自动部署
4. 定期备份重要数据
5. 监控服务运行状态

这样可以确保VPS上的代码与本地完全一致，并且支持快速部署和回滚。