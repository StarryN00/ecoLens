# 安全补救后续步骤（Security Remediation Steps）

## 背景

`server.md` 在 Initial commit `327cb1d` 中以明文形式提交了生产服务器的 SSH 凭据：

- IP: `81.68.224.178`
- 用户: `ubuntu`
- 密码: `***REDACTED-ROTATED-PASSWORD***`

该 commit 已经 push 到 `origin/main`，等同于密码已经公开泄露。

本次提交（chore(security): remove leaked server credentials, gitignore .env）
**只是把文件从 HEAD 删除了**，git 历史里 `327cb1d:server.md` 仍可被任何能拉到本仓库的人 checkout 出来。

要彻底从历史中清除，必须重写 git 历史并强推。

---

## 前置条件（在执行清除历史 + 强推前必须完成）

按顺序执行，每一项都是阻塞项：

1. **立即在生产服务器上修改 ubuntu 用户的密码**
   - SSH 登录 81.68.224.178，运行 `passwd` 修改 ubuntu 密码。
   - 或更彻底：禁用密码登录，改为强制 SSH key 认证
     （`/etc/ssh/sshd_config` 设置 `PasswordAuthentication no`，重启 sshd）。
   - 检查 `~/.ssh/authorized_keys`，确认没有陌生公钥。
   - 检查 `/var/log/auth.log` 或 `journalctl _COMM=sshd`，确认没有可疑登录。

2. **轮换其它可能复用的密钥/凭据**
   - 如果 `***REDACTED-ROTATED-PASSWORD***` 或其变种用在数据库、对象存储、第三方 API、其他服务器上，
     全部一并轮换。

3. **通知所有 collaborator**
   - 告知：仓库历史即将被重写，旧的本地 clone 在强推后会与远程冲突。
   - 要求所有人：
     - 暂存或推送自己的未提交工作；
     - 在强推完成后，删除本地 clone 重新 `git clone`，
       或执行 `git fetch && git reset --hard origin/<branch>`。

4. **确认仓库的 fork / mirror**
   - 在 GitHub/Gitee 等托管平台检查是否有 fork。
   - 若有，逐个联系 owner 删除 fork 或同步重写后的历史。
   - 注意：即使我们重写历史，GitHub 仍会在一段时间内通过 commit SHA 访问到旧
     commit（`https://github.com/<org>/<repo>/commit/327cb1d`），需要联系 GitHub
     Support 请求清除缓存的 commit。

---

## 历史重写步骤（仅供参考，不要在前置条件未完成时执行）

### 方案 A: git filter-repo（推荐）

```bash
# 1. 安装 git-filter-repo（本机当前未安装）
brew install git-filter-repo
# 或 pip install git-filter-repo

# 2. 备份当前仓库（强烈建议）
cd /Users/starryn/project/ecoLens
git clone --mirror . /tmp/ecoLens-backup-$(date +%Y%m%d).git

# 3. 在主仓库（不是 worktree）中执行历史重写
cd /Users/starryn/project/ecoLens
git filter-repo \
  --path server.md \
  --path .env \
  --path backend/.env \
  --invert-paths --force

# 4. 验证 server.md 已从所有历史中消失
git log --all --oneline -- server.md   # 应该无输出
git rev-list --all | xargs -I{} git ls-tree -r {} 2>/dev/null | grep server.md
# 应该无输出

# 5. 重新添加 remote（filter-repo 会移除 remote）
git remote add origin <git@github.com:org/ecoLens.git>

# 6. 强推所有分支和 tag（破坏性操作！）
git push --force --all origin
git push --force --tags origin
```

### 方案 B: BFG Repo-Cleaner

```bash
brew install bfg
cd /tmp
git clone --mirror <repo-url> ecoLens-mirror.git
cd ecoLens-mirror.git
bfg --delete-files server.md
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force
```

---

## 风险

- **强推会改写所有 collaborator 的 main 分支历史**。未通知到位会导致他人推送 merge commit 把旧历史带回来。
- **GitHub 缓存**：即使强推成功，旧 commit SHA 在一段时间内仍可通过直链访问，必须联系 GitHub Support。
- **CI/CD/部署系统**可能 pin 在旧 commit SHA 上，重写后会失效。
- **本地 worktree**：当前仓库使用了 worktree，重写历史前应先 `git worktree list` 并清理，否则 filter-repo 可能出错。

---

## 校验清单（强推完成后）

- [ ] `git log --all --oneline -- server.md` 输出为空
- [ ] 在 GitHub 网页 `https://github.com/<org>/<repo>/commit/327cb1d` 返回 404 或被 GitHub 清除
- [ ] 生产服务器 ubuntu 密码已修改且禁用密码登录
- [ ] 所有 collaborator 已重新 clone
- [ ] CI/CD 系统正常构建最新 commit

---

## 时间线

- 发现时间：2026-05-17
- 本次 HEAD 删除：2026-05-17（本 commit）
- 服务器密码轮换：**待执行**
- 历史重写 + 强推：**待执行**（由主对话流程协调）

---

## 已 untrack 的 .env 文件

`.env` 和 `backend/.env` 在 Initial commit `327cb1d` 中被一并提交，
内含 `SECRET_KEY` 等敏感配置。Team A 已在 `911d621` 把这两个路径加入
`.gitignore`，但 **未把它们从 Git 索引移除**，因此 `git ls-files` 仍能列出。

本 commit 用 `git rm --cached` 把它们从索引移除（本地文件保留供开发者继续使用）：

```bash
git rm --cached .env backend/.env
```

效果：
- `.env`、`backend/.env` 不再被 Git 跟踪，后续 `git status` 不会显示其改动
- 本地工作树中的文件未删除
- **历史中仍然存在**：`git show 327cb1d:.env` 等仍可读出旧内容

正式清理：参见上文 `git filter-repo` 命令，已在 `--path` 列表里追加 `.env`
和 `backend/.env`，与 `server.md` 一并彻底从所有 commit 中抹除。

### 配套动作（必做）
1. **轮换 SECRET_KEY**：旧的 `SECRET_KEY` 必须视为泄露，所有签发过的 JWT
   都应作废。重新生成并写入新的 `.env`：
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. **轮换数据库密码**：`backend/.env` 中的 `DATABASE_URL` 包含的 DB 密码
   同样视为泄露，需在数据库侧修改并更新 `.env`。
3. 在 filter-repo 完成、强推之前，**不要把任何新的敏感凭据再写进
   tracked 的文件**。
