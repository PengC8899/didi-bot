#!/usr/bin/env python3
"""
Webhook自动部署脚本
监听GitHub/GitLab的Webhook请求，自动部署DDGL订单机器人

使用方法：
1. 配置环境变量或修改配置部分
2. 运行脚本: python webhook_deploy.py
3. 在GitHub/GitLab中配置Webhook URL: http://your-server:8080/webhook

安全建议：
- 使用HTTPS
- 配置Webhook密钥验证
- 限制访问IP
- 使用防火墙保护
"""

import os
import sys
import json
import hmac
import hashlib
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify
import threading
import time

# 配置部分 - 请根据实际情况修改
CONFIG = {
    # 服务配置
    'HOST': os.getenv('WEBHOOK_HOST', '0.0.0.0'),
    'PORT': int(os.getenv('WEBHOOK_PORT', 8080)),
    'DEBUG': os.getenv('WEBHOOK_DEBUG', 'False').lower() == 'true',
    
    # 项目配置
    'PROJECT_PATH': os.getenv('PROJECT_PATH', '/home/user/DDGL_bot'),
    'REPO_URL': os.getenv('REPO_URL', 'https://github.com/your-username/DDGL_bot.git'),
    'BRANCH': os.getenv('DEPLOY_BRANCH', 'main'),
    
    # 安全配置
    'WEBHOOK_SECRET': os.getenv('WEBHOOK_SECRET', ''),  # GitHub/GitLab Webhook密钥
    'ALLOWED_IPS': os.getenv('ALLOWED_IPS', '').split(',') if os.getenv('ALLOWED_IPS') else [],
    
    # 部署配置
    'DEPLOYMENT_TYPE': os.getenv('DEPLOYMENT_TYPE', 'git'),  # git, docker
    'AUTO_RESTART': os.getenv('AUTO_RESTART', 'True').lower() == 'true',
    'BACKUP_ENABLED': os.getenv('BACKUP_ENABLED', 'True').lower() == 'true',
    
    # 通知配置
    'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN', ''),
    'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID', ''),
}

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('webhook_deploy.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class DeploymentManager:
    """部署管理器"""
    
    def __init__(self, config):
        self.config = config
        self.project_path = Path(config['PROJECT_PATH'])
        self.is_deploying = False
        
    def verify_webhook_signature(self, payload, signature):
        """验证Webhook签名"""
        if not self.config['WEBHOOK_SECRET']:
            return True  # 如果没有配置密钥，跳过验证
            
        if not signature:
            return False
            
        # GitHub格式: sha256=...
        if signature.startswith('sha256='):
            expected_signature = 'sha256=' + hmac.new(
                self.config['WEBHOOK_SECRET'].encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected_signature)
            
        # GitLab格式: 直接是hash值
        expected_signature = hmac.new(
            self.config['WEBHOOK_SECRET'].encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    
    def check_ip_allowed(self, ip):
        """检查IP是否允许访问"""
        if not self.config['ALLOWED_IPS']:
            return True  # 如果没有配置IP限制，允许所有IP
        return ip in self.config['ALLOWED_IPS']
    
    def run_command(self, command, cwd=None):
        """执行命令"""
        try:
            logger.info(f"执行命令: {command}")
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd or self.project_path,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.info(f"命令执行成功: {result.stdout}")
                return True, result.stdout
            else:
                logger.error(f"命令执行失败: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            logger.error(f"命令执行超时: {command}")
            return False, "命令执行超时"
        except Exception as e:
            logger.error(f"命令执行异常: {e}")
            return False, str(e)
    
    def backup_current_version(self):
        """备份当前版本"""
        if not self.config['BACKUP_ENABLED']:
            return True, "备份已禁用"
            
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = self.project_path.parent / f"DDGL_bot_backup_{timestamp}"
            
            success, output = self.run_command(
                f"cp -r {self.project_path} {backup_path}",
                cwd=self.project_path.parent
            )
            
            if success:
                logger.info(f"备份创建成功: {backup_path}")
                return True, f"备份创建成功: {backup_path}"
            else:
                return False, f"备份创建失败: {output}"
                
        except Exception as e:
            logger.error(f"备份过程异常: {e}")
            return False, str(e)
    
    def deploy_git(self):
        """Git部署"""
        steps = []
        
        try:
            # 检查项目目录
            if not self.project_path.exists():
                logger.info("项目目录不存在，克隆仓库...")
                success, output = self.run_command(
                    f"git clone {self.config['REPO_URL']} {self.project_path}",
                    cwd=self.project_path.parent
                )
                if not success:
                    return False, f"克隆仓库失败: {output}"
                steps.append("✅ 克隆仓库成功")
            else:
                # 更新代码
                logger.info("更新代码...")
                commands = [
                    "git fetch origin",
                    f"git reset --hard origin/{self.config['BRANCH']}",
                    "git clean -fd"
                ]
                
                for cmd in commands:
                    success, output = self.run_command(cmd)
                    if not success:
                        return False, f"更新代码失败: {output}"
                
                steps.append("✅ 代码更新成功")
            
            # 检查.env文件
            env_file = self.project_path / '.env'
            if not env_file.exists():
                env_example = self.project_path / '.env.example'
                if env_example.exists():
                    success, output = self.run_command("cp .env.example .env")
                    if success:
                        steps.append("⚠️  已创建.env文件，请检查配置")
                    else:
                        return False, f"创建.env文件失败: {output}"
                else:
                    return False, "未找到.env或.env.example文件"
            
            # 重启服务
            if self.config['AUTO_RESTART']:
                logger.info("重启服务...")
                commands = [
                    "docker-compose down",
                    "docker-compose up -d --build"
                ]
                
                for cmd in commands:
                    success, output = self.run_command(cmd)
                    if not success:
                        return False, f"重启服务失败: {output}"
                
                steps.append("✅ 服务重启成功")
                
                # 等待服务启动
                time.sleep(10)
                
                # 健康检查
                success, output = self.run_command(
                    "docker-compose exec -T orderbot python -c 'print(\"Bot is running\")'"
                )
                if success:
                    steps.append("✅ 服务健康检查通过")
                else:
                    steps.append("⚠️  服务健康检查失败，请手动检查")
            
            return True, "\n".join(steps)
            
        except Exception as e:
            logger.error(f"Git部署异常: {e}")
            return False, str(e)
    
    def deploy_docker(self):
        """Docker部署"""
        # 这里可以实现Docker镜像部署逻辑
        # 由于复杂性，这里只提供基本框架
        return False, "Docker部署功能待实现"
    
    def deploy(self):
        """执行部署"""
        if self.is_deploying:
            return False, "部署正在进行中，请稍后再试"
        
        self.is_deploying = True
        
        try:
            logger.info("开始部署...")
            
            # 备份当前版本
            if self.config['BACKUP_ENABLED']:
                backup_success, backup_msg = self.backup_current_version()
                if not backup_success:
                    logger.warning(f"备份失败，继续部署: {backup_msg}")
            
            # 根据配置选择部署方式
            if self.config['DEPLOYMENT_TYPE'] == 'git':
                success, message = self.deploy_git()
            elif self.config['DEPLOYMENT_TYPE'] == 'docker':
                success, message = self.deploy_docker()
            else:
                success, message = False, f"不支持的部署类型: {self.config['DEPLOYMENT_TYPE']}"
            
            if success:
                logger.info(f"部署成功: {message}")
            else:
                logger.error(f"部署失败: {message}")
            
            return success, message
            
        finally:
            self.is_deploying = False
    
    def send_telegram_notification(self, success, message, commit_info=None):
        """发送Telegram通知"""
        if not self.config['TELEGRAM_BOT_TOKEN'] or not self.config['TELEGRAM_CHAT_ID']:
            return
        
        try:
            import requests
            
            status_emoji = "✅" if success else "❌"
            status_text = "成功" if success else "失败"
            
            text = f"{status_emoji} DDGL Bot 自动部署{status_text}\n\n"
            
            if commit_info:
                text += f"📋 提交信息:\n"
                text += f"- 分支: {commit_info.get('branch', 'unknown')}\n"
                text += f"- 提交者: {commit_info.get('author', 'unknown')}\n"
                text += f"- 消息: {commit_info.get('message', 'unknown')}\n\n"
            
            text += f"📝 详情:\n{message}\n\n"
            text += f"🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/sendMessage"
            data = {
                'chat_id': self.config['TELEGRAM_CHAT_ID'],
                'text': text,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram通知发送成功")
            else:
                logger.error(f"Telegram通知发送失败: {response.text}")
                
        except Exception as e:
            logger.error(f"发送Telegram通知异常: {e}")

# 创建部署管理器实例
deployment_manager = DeploymentManager(CONFIG)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook端点"""
    try:
        # 检查IP限制
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if not deployment_manager.check_ip_allowed(client_ip):
            logger.warning(f"IP访问被拒绝: {client_ip}")
            return jsonify({'error': 'Access denied'}), 403
        
        # 获取请求数据
        payload = request.get_data()
        signature = request.headers.get('X-Hub-Signature-256') or request.headers.get('X-Gitlab-Token')
        
        # 验证签名
        if not deployment_manager.verify_webhook_signature(payload, signature):
            logger.warning("Webhook签名验证失败")
            return jsonify({'error': 'Invalid signature'}), 403
        
        # 解析JSON数据
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("无效的JSON数据")
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # 提取提交信息
        commit_info = {}
        
        # GitHub格式
        if 'commits' in data and data['commits']:
            commit = data['commits'][0]
            commit_info = {
                'branch': data.get('ref', '').replace('refs/heads/', ''),
                'author': commit.get('author', {}).get('name', 'unknown'),
                'message': commit.get('message', 'unknown')
            }
        
        # GitLab格式
        elif 'project' in data and 'commits' in data:
            if data['commits']:
                commit = data['commits'][0]
                commit_info = {
                    'branch': data.get('ref', '').replace('refs/heads/', ''),
                    'author': commit.get('author', {}).get('name', 'unknown'),
                    'message': commit.get('message', 'unknown')
                }
        
        # 检查分支
        target_branch = commit_info.get('branch', '')
        if target_branch and target_branch != CONFIG['BRANCH']:
            logger.info(f"忽略非目标分支的推送: {target_branch}")
            return jsonify({'message': f'Ignored push to {target_branch}'}), 200
        
        # 异步执行部署
        def deploy_async():
            success, message = deployment_manager.deploy()
            deployment_manager.send_telegram_notification(success, message, commit_info)
        
        thread = threading.Thread(target=deploy_async)
        thread.daemon = True
        thread.start()
        
        logger.info("部署任务已启动")
        return jsonify({'message': 'Deployment started'}), 200
        
    except Exception as e:
        logger.error(f"Webhook处理异常: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/status', methods=['GET'])
def status():
    """状态检查端点"""
    return jsonify({
        'status': 'running',
        'is_deploying': deployment_manager.is_deploying,
        'config': {
            'project_path': str(deployment_manager.project_path),
            'deployment_type': CONFIG['DEPLOYMENT_TYPE'],
            'branch': CONFIG['BRANCH']
        }
    })

@app.route('/deploy', methods=['POST'])
def manual_deploy():
    """手动部署端点"""
    try:
        success, message = deployment_manager.deploy()
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 500
        
    except Exception as e:
        logger.error(f"手动部署异常: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 检查配置
    if not CONFIG['PROJECT_PATH']:
        logger.error("请配置PROJECT_PATH")
        sys.exit(1)
    
    if not CONFIG['REPO_URL']:
        logger.error("请配置REPO_URL")
        sys.exit(1)
    
    logger.info(f"启动Webhook部署服务...")
    logger.info(f"监听地址: {CONFIG['HOST']}:{CONFIG['PORT']}")
    logger.info(f"项目路径: {CONFIG['PROJECT_PATH']}")
    logger.info(f"部署分支: {CONFIG['BRANCH']}")
    logger.info(f"部署类型: {CONFIG['DEPLOYMENT_TYPE']}")
    
    app.run(
        host=CONFIG['HOST'],
        port=CONFIG['PORT'],
        debug=CONFIG['DEBUG']
    )