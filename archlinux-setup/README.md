# Arch Linux 初始化配置脚本

一键式 Arch Linux（含 WSL Arch）环境初始化脚本：替换清华源、安装基础开发软件、配置美化 Zsh、配置 NeoVim (LazyVim)，并可选创建普通用户。

## 特性

- 交互式 `y/n` 询问，**直接回车视为允许 (y)**
- 所有选择完成后给出确认表，确认才执行；确认表同样回车即执行
- 确认表支持 `y`(执行) / `n`(退出) / `r`(重新配置)
- 支持原生 Arch 与 WSL Arch
- 不创建新用户时，可指定已有用户；直接回车则目标为 **root**（配置写入 `/root`）
- 创建新用户时，Zsh / NeoVim 等用户级配置统一落到新用户家目录
- root 与目标用户均可切换为 zsh
- WSL 环境自动跳过 `systemctl enable docker` 但显式提示失败原因
- 失败时通过 ERR trap 输出失败行号与命令，便于排查
- 中途失败后可安全重跑：已存在用户会跳过创建，镜像为多源回退，Zsh/NeoVim 已配置则跳过覆盖

## 使用方法

> 脚本需以 **root** 用户执行。

```bash
# 下载后赋予执行权限
chmod +x init.sh

# 以 root 执行（推荐）
sudo ./init.sh
# 或
su -c './init.sh'
```

在 WSL Arch 中：

```bash
sudo ./init.sh
```

## 执行流程

1. **前置校验**：root 检测、`/etc/arch-release` 检测、WSL 检测
2. **询问阶段**（推荐项回车即 y）：
   1. 用户创建（仅 root 时提示）
   2. 镜像源（默认官方源，不修改现有 mirrorlist）
   3. 基础软件包（含 curl/wget/openssh/man 等）
   4. Locale（en_US.UTF-8 + zh_CN.UTF-8）
   5. Zsh 安装与美化
   6. Nerd Font / 中文字体
   7. NeoVim (LazyVim)
   8. AUR 助手 yay（目标为 root 时自动跳过）
   9. WSL systemd（仅 WSL）
3. **确认表**：列出全部选择与目标用户，`y` 执行 / `n` 退出 / `r` 重新配置（回车=y）
4. **执行阶段**：按序 `exec_create_user → exec_mirror → exec_base_software → exec_zsh → exec_nvim`

## 目标用户说明

| 选择 | 用户级配置写到哪里 |
|------|-------------------|
| 创建普通用户（例如 `rpok`） | `getent` 得到的家目录，通常是 `/home/rpok` |
| 不创建，指定已有普通用户 | 该用户 **passwd 中的家目录**（不假设一定是 `/home/名字`） |
| 不创建，回车默认 `root` | `/root` |

系统级改动（镜像源、pacman、软件包安装）始终以 root 执行，与目标用户无关。

写入前会校验：
- 目标必须是 **root** 或 **uid ≥ 1000** 的普通用户（拒绝 `nobody` / `bin` 等系统账户）
- 家目录必须存在且 **属主就是目标用户**，否则中止，避免写到别人家里
- 属组使用 `id -gn`（已有用户主组不一定等于用户名）

确认表在用户尚未创建时也会显示计划中的目标用户，**不会**因为“用户还不存在”而中止。

## 各模块说明

### 用户创建

- 用户名校验：`^[a-z_][a-z0-9_-]{0,31}$`
- `useradd -m -G wheel -s /bin/bash <name>`
- 交互式 `passwd` 设置密码
- 优先写入 `/etc/sudoers.d/99-wheel` 启用 wheel 组 sudo
- WSL 下写入 `/etc/wsl.conf` 的 `[user] default=<name>`，并提示在 PowerShell 执行 `wsl --terminate <发行版名>` 生效

### 镜像源

询问格式与 `y/n [y]` 相同：`(1-6) [官方源]`，直接回车为官方源。

| 选择 | 行为 |
|------|------|
| 官方源（默认） | **不修改** `/etc/pacman.d/mirrorlist` 和 `pacman.conf` |
| 清华 / 中科大 / 阿里 / 腾讯 / 华为 | 备份原 `mirrorlist`，所选源排第一，其余源回退 |

- `[archlinuxcn]` 仅在选择国内源时写入，同样所选源优先
- 同步失败会重试一次；仍失败则中止并提示可安全重跑

### 中途失败后再执行

可以再跑，一般不会把环境配坏：

| 步骤 | 再执行时 |
|------|----------|
| 用户已创建 | 跳过 `useradd`，或询问后改为配置该已有用户 |
| 镜像 | 官方源仍不改文件；国内源则按所选源重写多源列表 |
| 基础软件 | `pacman --needed`，已装则跳过 |
| Zsh | 已克隆的插件目录跳过；`.zshrc` 会按模板覆盖 |
| NeoVim | 若已有 `init.lua` + `lua/` 则跳过克隆，不反复备份覆盖 |

### 基础软件包

- 包列表：`git base-devel make cmake vim neovim tree docker curl wget openssh man-db man-pages which less unzip`，选 Zsh 时附加 `zsh zsh-completions`

非 root 运行会自动 `sudo` 重跑。WSL 默认登录用户**只在全部步骤成功后**才写入，避免中途失败卡在新用户。回到 root：`wsl -u root` 或先 `exit`。
- 目标用户（非 root）自动加入 `docker` 组
- **原生 Arch**：`systemctl enable docker`，失败时输出 `[ERR]` 提示
- **WSL**：跳过 `systemctl enable`，输出失败原因提示，引导使用 Docker Desktop WSL 集成或手动启动 `dockerd`

### Zsh 美化

- 安装 `zsh zsh-completions`（若未装）
- 将 `/bin/zsh` 写入 `/etc/shells`（若缺）
- 克隆三个插件到目标用户 `~/.zsh/`：
  - `zsh-users/zsh-autosuggestions`
  - `zsh-users/zsh-syntax-highlighting`
  - `romkatv/powerlevel10k`
- 写入 `~/.zshrc`：p10k 主题 + 两个插件 + 历史记录 + 补全 + 常用别名 + WSL `winhome` 别名
- 原目录已克隆则跳过（幂等）
- `chsh -s /bin/zsh` 对目标用户执行；若当前为 root 且目标用户非 root，则 root 一并切换

> 首次进入 zsh 后，powerlevel10k 会引导完成个性化配置（字体/样式）。

### NeoVim (LazyVim)

- **前置依赖**（单独作为 nvim 步骤前置安装）：`ripgrep fd unzip lazygit fzf nodejs npm gcc make`
- 备份现有 `~/.config/nvim`、`~/.local/share/nvim`、`~/.local/state/nvim`、`~/.cache/nvim` 为 `*.bak.<时间戳>`
- 克隆 [LazyVim/starter](https://github.com/LazyVim/starter) 到目标用户 `~/.config/nvim`，移除 `.git`
- 仅修正 nvim 目录 owner，不改写整个 `~/.config`

> 首次 `nvim` 启动会自动下载插件，请保持网络畅通。

## 注意事项

- 脚本会修改系统级文件（`/etc/pacman.conf`、`/etc/sudoers.d`、`/etc/shells`、`/etc/wsl.conf` 等），建议在全新系统执行；重要数据请先备份
- 已存在的配置目录会被备份而非删除，可手动恢复
- 重复执行不会破坏已克隆的插件目录，但 `~/.zshrc` 与 LazyVim starter 会被覆盖（先备份旧 nvim 目录）
- WSL 下 docker 服务需自行处理（见基础软件包章节）

## 目录结构

```
arch-init/
  init.sh      # 主脚本
  README.md    # 本文档
```

## 许可

仅供个人使用。
