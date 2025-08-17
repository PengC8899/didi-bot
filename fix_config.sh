#!/bin/bash
# 自动生成的配置修复脚本
echo '开始修复配置问题...'

chmod +x deploy.sh
echo '✅ 已添加 deploy.sh 执行权限'
chmod +x healthcheck.py
echo '✅ 已添加 healthcheck.py 执行权限'

echo '❌ 请手动设置 BOT_TOKEN:'
echo '1. 联系 @BotFather 获取机器人令牌'
echo '2. 编辑 .env 文件，替换 BOT_TOKEN 值'
echo '3. 重新运行此检查脚本'

echo '修复脚本执行完成'
echo '请检查上述输出并手动完成剩余配置'