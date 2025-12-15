# MySQL 初始化步骤

以下命令均在 Windows PowerShell 中示例，实际使用时请根据自己的安装路径调整。默认 root 密码为 `qwertyui793789`。

## 1. 使用 root 登录 MySQL
```powershell
mysql -u root -p
# 输入 qwertyui793789
```

## 2. 创建数据库架构
```sql
CREATE DATABASE `DSL-TodoList`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```
> **说明**：数据库名包含破折号，必须使用反引号包裹。

## 3. 创建业务账号并授权
```sql
CREATE USER 'DSL-TodoListUser'@'localhost'
  IDENTIFIED BY 'qwertyui793789';

GRANT ALL PRIVILEGES ON `DSL-TodoList`.*
  TO 'DSL-TodoListUser'@'localhost';
FLUSH PRIVILEGES;
```

## 4. 切换至目标数据库
```sql
USE `DSL-TodoList`;
```

## 5. 建表
```sql
CREATE TABLE IF NOT EXISTS todos (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  details TEXT NULL,
  due_at DATETIME NULL,
  status ENUM('pending','completed') NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_due_at(due_at),
  INDEX idx_status(status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 6. 初始化示例数据（可选）
```sql
INSERT INTO todos (title, details, due_at, status) VALUES
('形势与政策第八周作业', '整理课件笔记并总结案例', '2025-11-28 12:00:00', 'pending'),
('毛概社会实践调查报告提交', '完善调研结论，统一排版', '2026-06-25 00:00:00', 'pending'),
('计算机组成原理第八周作业', '刷完指定题库', '2025-10-20 18:00:00', 'completed');
```

## 7. 使用新账号验证
```powershell
mysql -u DSL-TodoListUser -p DSL-TodoList
# 输入 qwertyui793789
SELECT COUNT(*) FROM todos;
```
若能查询出结果，说明账号与授权已生效。
