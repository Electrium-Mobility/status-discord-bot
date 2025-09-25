# Outline 同步功能使用指南

## 概述

这个功能允许你自动将 Discord 角色同步到 Outline 群组，基于预定义的映射关系。

## 功能特性

- 🔄 自动同步 Discord 角色成员到 Outline 群组
- 🆕 自动创建缺失的 Outline 群组
- 📋 支持灵活的角色映射配置
- 🔧 支持动态重新加载配置
- 📊 提供详细的同步报告

## 角色映射配置

### F25 项目组

| Discord 角色          | Outline 群组               | 描述                   |
| --------------------- | -------------------------- | ---------------------- |
| `Bike-F25`            | `F25-Bike-Team`            | F25 自行车项目团队     |
| `Skateboard-F25`      | `F25-Skateboard-Team`      | F25 滑板项目团队       |
| `MidBike-F25`         | `F25-MidBike-Team`         | F25 中型自行车项目团队 |
| `F25-FW-ELEC-Project` | `F25-Firmware-Electronics` | F25 固件电子项目团队   |

### 领导层角色

| Discord 角色   | Outline 群组    | 描述       |
| -------------- | --------------- | ---------- |
| `team lead`    | `Team-Leads`    | 团队负责人 |
| `project lead` | `Project-Leads` | 项目负责人 |
| `management`   | `Management`    | 管理层     |

### 部门角色

| Discord 角色 | Outline 群组     | 描述   |
| ------------ | ---------------- | ------ |
| `Marketing`  | `Marketing-Team` | 市场部 |
| `coop`       | `Coops-Interns`  | 实习生 |

## 🎮 可用命令

### 1. 测试功能

**命令**: `/test-outline-features`

- **描述**: 综合测试 Outline 功能（配置验证 + 模拟运行）
- **权限**: 需要管理角色权限
- **安全性**: 100%安全，不执行实际操作
- **功能**:
  - 验证所有 Discord 角色映射的有效性
  - 模拟同步操作并显示详细报告
  - 检查配置文件语法和设置

### 2. 正式同步

**命令**: `/sync-outline [dry_run:True/False]`

- **描述**: 同步 Discord 角色到 Outline 群组
- **权限**: 需要管理角色权限
- **参数**:
  - `dry_run`: 可选，设为 True 时进行模拟运行
- **功能**:
  - 创建对应的 Outline 群组
  - 同步角色成员到群组
  - 支持模拟运行模式

### 3. 显示映射

**命令**: `/show-role-mappings`

- **描述**: 显示当前的 Discord 角色到 Outline 群组映射配置
- **权限**: 需要管理角色权限
- **功能**:
  - 展示所有配置的角色映射
  - 显示映射统计信息
  - 查看当前配置状态

### 4. 重载配置

**命令**: `/reload-mappings`

- **描述**: 从配置文件重新加载角色映射
- **权限**: 需要管理角色权限
- **功能**:
  - 重新读取 role_mapping.json 文件
  - 更新内存中的映射配置
  - 无需重启 Bot 即可应用新配置

## 配置文件说明

### role_mapping.json 结构

```json
{
  "f25_projects": {
    "pattern": "f25",
    "mappings": {
      "Bike-F25": "F25-Bike-Team",
      "Skateboard-F25": "F25-Skateboard-Team",
      "MidBike-F25": "F25-MidBike-Team",
      "F25-FW-ELEC-Project": "F25-Firmware-Electronics"
    }
  },
  "leadership": {
    "team lead": "Team-Leads",
    "project lead": "Project-Leads",
    "management": "Management"
  },
  "departments": {
    "Marketing": "Marketing-Team",
    "coop": "Coops-Interns"
  },
  "outline_settings": {
    "auto_create_groups": true,
    "sync_members": true,
    "sync_interval_hours": 24
  }
}
```

### 配置参数说明

- `f25_projects.pattern`: F25 项目的匹配模式
- `f25_projects.mappings`: F25 项目的具体映射关系
- `leadership`: 领导层角色映射
- `departments`: 部门角色映射
- `outline_settings.auto_create_groups`: 是否自动创建群组
- `outline_settings.sync_members`: 是否同步成员
- `outline_settings.sync_interval_hours`: 同步间隔（小时）

## 📋 使用流程

### 快速开始

1. **测试配置**: 运行 `/test-outline-features` 验证所有设置
2. **正式同步**: 运行 `/sync-outline` 执行同步操作
3. **查看结果**: 检查 Outline 中的群组和成员

### 详细流程

#### 第一步：验证配置

```bash
/test-outline-features
```

- 检查所有 Discord 角色是否存在
- 验证配置文件语法
- 模拟同步操作
- 查看详细报告

#### 第二步：执行同步

如果测试通过，执行正式同步：

```bash
/sync-outline
```

或者先进行模拟运行：

```bash
/sync-outline dry_run:True
```

#### 第三步：验证结果

- 登录 Outline 检查群组是否创建成功
- 验证成员是否正确同步
- 检查权限设置是否正确

### 日常使用

1. 当 Discord 角色成员发生变化时，运行`/sync-outline`
2. 如需修改映射关系，编辑`role_mapping.json`后运行`/reload-mappings`
3. 使用`/show-role-mappings`随时查看当前配置

### 故障排除

1. **同步失败**: 检查 Outline API token 是否有效
2. **群组创建失败**: 确认 API 权限是否足够
3. **映射不生效**: 运行`/reload-mappings`重新加载配置

## 注意事项

### 权限要求

- Discord: 需要`manage_roles`权限
- Outline: 需要有创建群组和管理成员的 API 权限

### 安全考虑

- 定期检查同步结果
- 确保敏感群组不在自动同步范围内
- 保护好 Outline API token

### 性能优化

- 避免频繁执行同步命令
- 大量成员同步时可能需要等待较长时间
- 建议在低峰期执行大规模同步

## 技术实现

### 核心文件

- `bot.py`: 主要的 Discord bot 逻辑
- `auto_sync_outline.py`: Outline 同步功能实现
- `role_mapping.json`: 角色映射配置文件

### API 集成

- Discord API: 获取角色和成员信息
- Outline API: 创建群组和管理成员
- 异步处理: 提高同步效率

### 错误处理

- API 调用失败重试机制
- 详细的错误日志记录
- 用户友好的错误消息

## 更新日志

### v1.0.0 (当前版本)

- ✅ 基础角色映射功能
- ✅ 自动群组创建
- ✅ 成员同步功能
- ✅ 配置动态重载
- ✅ 详细的同步报告

### 计划功能

- 🔄 定时自动同步
- 📧 同步结果邮件通知
- 📊 同步历史记录
- 🔍 高级过滤选项
