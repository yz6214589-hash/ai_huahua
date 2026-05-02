# Errors

Command failures and integration errors.

---
## [ERR-20260430-001] brew_install_python311_requires_approval

**Logged**: 2026-04-30T00:00:00Z
**Priority**: medium
**Status**: pending
**Area**: infra

### Summary
在执行 brew 安装 python@3.11 的命令时，因需要用户审批导致命令未实际执行

### Error
命令返回非 0 退出码且无输出（通常是“需要审批但未获批准”的情况）

### Context
- Command: brew list --versions python@3.11 || brew install python@3.11

### Suggested Fix
- 在界面提示时允许执行该命令，或改用手动方式安装 Python 3.11（Python.org / pyenv）

---
## [ERR-20260430-002] brew_install_python311_permission_denied

**Logged**: 2026-04-30T00:00:00Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Homebrew 安装 python@3.11 因 /usr/local 目录权限问题失败

### Error
Error: /usr/local/Cellar is not writable

### Context
- Command: brew install python@3.11

### Suggested Fix
- 按 brew 提示使用 sudo 修复 /usr/local 下相关目录 owner/权限后再重试

---
