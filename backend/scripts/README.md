# backend/scripts

后端的一次性运维 / bootstrap 脚本。**不属于业务运行时**，只在部署或运维时
手动执行。

## create_admin.py — 创建/提升管理员

### 背景

旧版 `POST /api/v1/auth/register` 用 `count(User)==0 -> is_admin=True` 的
逻辑给"第一个注册的用户"自动 admin 权限。这是一个 TOCTOU race：两个并发
的注册请求都能读到 count==0，两边都把 `is_admin` 设成 True，从而出现意外
的多管理员。

修复方案：把"造 admin"从在线请求里**完全移除**，注册接口一律产出普通用户；
admin 必须通过本脚本离线创建。脚本是单进程顺序执行，不存在 race，并且依赖
`users.username` 上的 UNIQUE 约束做最终防线。

### 使用方法

前置：`SECRET_KEY`、`DATABASE_URL` 必须已经通过环境变量或 `backend/.env`
配置好。

```bash
cd backend

# 推荐：交互式输入密码（不会出现在 shell history）
python -m scripts.create_admin --username alice

# 一次性传参（密码会进 shell history 和 ps aux，不推荐）
python -m scripts.create_admin \
  --username alice \
  --password 'S3cret!' \
  --email alice@example.com

# 把已存在的普通用户提升为 admin
python -m scripts.create_admin --username alice --promote
```

### 退出码

| code | 含义 |
|------|------|
| 0    | 成功 |
| 1    | 参数 / 输入错误（用户名长度、密码长度、用户已存在但未带 --promote 等）|
| 2    | 数据库错误（例如 UNIQUE 冲突）|

### 安全注意

- 创建完 admin 后，**立即在生产环境登录一次验证**，确认密码正确。
- 不要把生成 admin 用的密码留在任何 shell history、CI log、运维笔记里。
- 生产环境强烈建议禁用普通用户的 `register` 接口，或在反向代理层用 IP
  白名单限制 `POST /api/v1/auth/register` —— 当前实现没有限制注册来源。

## add_missing_indexes.py — 补外键索引 + ownership 列

### 背景

P1 #11 给所有外键列加了 `index=True`；M2 给 `inspection_tasks` 加了
`owner_id`（NOT NULL，FK -> users.id）。这两组变更**仅对新建的库**
通过 `Base.metadata.create_all` 自动生效；对已经在线的 dev / staging /
prod 库，必须手动跑本脚本补齐。

本项目目前**没有 Alembic**（这次 P1 不引入），所以用这个手写的幂等
迁移脚本承担一次性补丁的责任。

### 它做了什么

1. 给 6 个外键列 + 新增的 `owner_id` 列 `CREATE INDEX IF NOT EXISTS`
2. 给 `inspection_tasks` 加 `owner_id` 列（如果不存在）。SQLite 用
   `PRAGMA table_info` 检测，PostgreSQL 用 `information_schema.columns`
3. 把 `owner_id IS NULL` 的旧任务回填给数据库里**第一个 admin**
   （按 `created_at` 排序取第一个）
4. **仅 PostgreSQL**：在确认没有残余 NULL 后，`ALTER COLUMN ... SET
   NOT NULL`。SQLite 不支持 `ALTER COLUMN`，跳过；模型层 NOT NULL
   能阻止新写入留 NULL，旧库的约束只能等下次表重建

### 使用方法

```bash
cd backend
SECRET_KEY=... DATABASE_URL=... python -m scripts.add_missing_indexes
```

**前置条件**：库里至少有 1 个 admin（否则 owner_id 回填没落脚点，
脚本退出码 1）。如果还没 admin，先：

```bash
python -m scripts.create_admin --username alice
```

### 退出码

| code | 含义 |
|------|------|
| 0    | 成功 |
| 1    | 库里没 admin，owner_id 回填失败 |
| 2    | 数据库错误 |

### 生产环境注意

- 脚本默认用普通 `CREATE INDEX`，会**短暂锁表**。如果生产库数据量
  大、不能停服，请改用：

    ```sql
    CREATE INDEX CONCURRENTLY ix_xxx ON yyy (zzz);
    ```

  并且必须在事务外执行。脚本图方便没用 `CONCURRENTLY`（包装事务边界
  比较麻烦），运维侧请自行评估。
- 脚本是**幂等**的，可以重复跑，不会因列 / 索引已存在而失败。
