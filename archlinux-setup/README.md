# Arch Linux 初始化配置脚本

一键式 Arch Linux（含 WSL Arch）环境初始化脚本：替换清华源、安装基础开发软件、配置美化 Zsh、配置 NeoVim (LazyVim)，并可选创建普通用户。

## 特性

- 菜单化交互（menuconfig 风格，单列表+分组标题）：`↑↓` 移动 / `空格` 勾选或进入子菜单 / `回车` 进入子项或执行 / `q` 退出，列表过长自动滚动
- 菜单即确认：勾选完成后回车 `[执行]` 即可，**无独立确认表**
- **分组菜单**：`系统基础 / 系统服务 / 终端美化 / 开发工具 / CLI 增强 / 容器 / WSL`，一目了然
- 子项随父项展开：勾选 **Docker** 后自动出现 **Docker 镜像源** 子选项
- **预检测锁定**：已安装的软件 / 已启用的服务 / 已配置的用户级项自动勾选并锁定，**空格无效不可取消**，避免重复配置
- **软件清单可扩展**：除基础项外，内置 开发语言/Java/Node/脚本语言/C++/git/lazygit/CLI 工具/容器 等 20+ 可选软件项
- **systemd 服务项**（NetworkManager / sshd / chrony / cronie）：勾选后原生 Arch 自动 `systemctl enable --now`；WSL 下跳过并记入"重启后自动生效"
- **reflector**（镜像自动优选）与手动镜像源二选一，并入镜像源单选子菜单
- 支持原生 Arch 与 WSL Arch
- 不创建新用户时，可指定已有用户；默认目标为 **root**（配置写入 `/root`）
- 创建新用户时，Zsh / NeoVim 等用户级配置统一落到新用户家目录
- root 与目标用户均可切换为 zsh；目标为非 root 时，同时为 root 生成 `.zshrc` 并复制插件
- WSL 下创建新用户时，**默认不**将新用户设为 WSL 默认登录用户（多用户场景更安全）
- 关键步骤失败（如用户创建、源同步）会中止并给出提示；非关键步骤失败则记录到末尾失败汇总
- 结束时汇总三类提示：**需立即处理 / 重启后自动生效（无需操作）/ 失败项**，无需翻阅执行记录
- 中途失败后可安全重跑：已存在用户会跳过创建，镜像为多源回退，Zsh/NeoVim 已配置则跳过覆盖
- 多用户复用同一环境时：已配置的**镜像源 / locale 自动跳过**，不会重复改写

## 使用方法

> 脚本需以 **root** 用户执行。

```bash
# 下载后赋予执行权限
chmod +x arch-setup.py

# 以 root 执行（推荐）
sudo ./arch-setup.py
# 或
su -c './arch-setup.py'
```

在 WSL Arch 中：

```bash
sudo ./arch-setup.py
```

## 执行流程

1. **前置校验**：root 检测、`/etc/arch-release` 检测、WSL 检测
2. **菜单选择**（menuconfig 风格，分组菜单，选择即时生效，菜单即确认）：
   - **目标用户**：`空格` 或 `回车` 进入子菜单，选择 *创建新用户* 或 *配置已有用户*
   - **镜像源**：`空格` 或 `回车` 进入单选子菜单（官方 / 清华 / 中科大 / 阿里 / 腾讯 / 华为 / **自动优选(reflector)**）
   - 其余各项按分组 `空格` 勾选（见下方分组清单）；勾选 **Docker** 后自动展开 **Docker 镜像源** 子选项
   - 底部提示栏：动态操作提示（如"空格/回车: 进入选择"）与固定图例同行显示
3. **执行阶段**：回车 `[执行]` 触发，按菜单顺序依次执行所选各项

## 软件清单（分组）

| 分组 | 可选项目 |
|------|----------|
| **系统基础** | 镜像源、Locale、时区、基础软件包、CPU 微码 |
| **系统服务** | 网络工具(NetworkManager)、SSH 服务端(sshd)、NTP 时间同步(chrony)、定时任务(cronie)、防火墙(ufw) |
| **终端美化** | Zsh 美化、字体(Nerd/中文)、终端提示符(starship) |
| **开发工具** | NeoVim(LazyVim)、python、rustup、go、Java(jdk-openjdk)、Node系(bun/deno)、lua、php、ruby、C/C++工具链(clang/valgrind)、git增强(git-delta)、lazygit、AUR助手(yay)、AUR助手(paru) |
| **CLI 增强** | 终端工具(tmux/btop/eza/bat/zoxide/fd/ripgrep)、终端编辑器(helix/micro)、文件管理(yazi)、系统信息+磁盘(fastfetch/duf/ncdu)、JSON工具(jq/yq)、网络诊断(nmap/ncat/mosh/httpie/iperf3)、速查手册(tldr/cheat)、目录导航(broot/direnv)、git扩展(git-lfs/git-open)、文件索引(plocate)、网络补充(mtr/whois) |
| **容器** | Docker、Docker镜像源(子项)、Podman/K8s(podman/kubectl/k9s/helm) |
| **WSL** | WSL systemd |

> 部分软件（如 `bun`/`deno`/`paru` 等）可能位于 AUR 而非官方仓库：安装失败会记入末尾失败汇总，不中断流程。

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

菜单中用户尚未创建时也能继续勾选其它项并回车执行（会先创建用户再配置），**不会**因为“用户还不存在”而中止。

## 各模块说明

### 用户创建

- 用户名校验：`^[a-z_][a-z0-9_-]{0,31}$`
- `useradd -m -G wheel -s /bin/bash <name>`
- 交互式 `passwd` 设置密码
- 优先写入 `/etc/sudoers.d/99-wheel` 启用 wheel 组 sudo
- WSL 下若选择设为默认登录用户，写入 `/etc/wsl.conf` 的 `[user] default=<name>`，重启 WSL 后自动生效（无需手动操作）

### 镜像源

在菜单中通过 `回车` 进入单选子菜单选择。

| 选择 | 行为 |
|------|------|
| 官方源（默认） | **不修改** `/etc/pacman.d/mirrorlist` 和 `pacman.conf` |
| 清华 / 中科大 / 阿里 / 腾讯 / 华为 | 备份原 `mirrorlist`，所选源排第一，其余源回退 |
| **自动优选 (reflector)** | 运行 `reflector --latest 10 --protocol https --sort rate` 按速度实测生成 `mirrorlist`。**严格仅原生 Arch 执行**（WSL 跳过并记入"重启后自动生效"） |

- `[archlinuxcn]` 仓库：**国内源始终配置**（所选源优先）；**官方源 / reflector 仅在需安装 yay 或 paru 时配置**（使用官方 cn 源 `repo.archlinuxcn.org`）——安装 yay/paru 需要此仓库
- 同步失败会重试一次；仍失败则中止并提示可安全重跑
- 幂等：mirrorlist 已含所选镜像源时**跳过重写**（多用户复用同一环境时不重复改写）

### 系统服务

勾选后安装对应软件并启用 systemd 服务：

| 菜单项 | 软件包 | 服务单元 |
|--------|--------|----------|
| 网络工具 | `networkmanager` | `NetworkManager` |
| SSH 服务端 | `openssh` | `sshd` |
| NTP 时间同步 | `chrony` | `chronyd` |
| 定时任务 | `cronie` | `cronie` |
| 防火墙 | `ufw` | `ufw` |

- **原生 Arch**：装包后自动 `systemctl enable --now <服务>`（防火墙额外执行 `ufw allow OpenSSH` + `ufw --force enable`）
- **WSL**：跳过 `systemctl enable`，记入"重启后自动生效"汇总（WSL 下 systemd 不可用时）
- 服务项默认关闭，勾选才启用；服务已启用则**预检测锁定**

### 开发工具 / CLI 增强

这些分组为**纯软件包**项，勾选即 `pacman -S --needed` 安装（已装则跳过），失败记入末尾失败汇总，不中断流程。包清单见上方"软件清单"分组表。

### 时区 / CPU 微码 / 终端提示符

- **时区**（系统基础组）：交互输入时区（默认 `Asia/Shanghai`），符号链接 `/etc/localtime`；原生 Arch 与 WSL 均生效。`/etc/localtime` 已是符号链接则预检测锁定。
- **CPU 微码**（系统基础组）：按 `/proc/cpuinfo` 自动识别 Intel→`intel-ucode` / AMD→`amd-ucode` 并安装；WSL 下跳过记入"重启后自动生效"。
- **终端提示符 starship**（终端美化组）：`starship` 安装后，Zsh 美化生成的 `~/.zshrc` 会自动 `eval "$(starship init zsh)"`（同 `zoxide`）。

### 中途失败后再执行

可以再跑，一般不会把环境配坏：

| 步骤 | 再执行时 |
|------|----------|
| 用户已创建 | 跳过 `useradd`，或菜单中改为配置该已有用户 |
| 镜像 | 官方源仍不改文件；国内源若已含所选源则跳过重写，否则重写多源列表 |
| Locale | 已启用 `en_US`/`zh_CN` 则跳过重新生成 |
| 基础软件 | `pacman --needed`，已装则跳过 |
| Zsh | 已克隆的插件目录跳过；含本脚本标识的 `.zshrc` 跳过覆盖（先备份原配置） |
| NeoVim | 若已有 `init.lua` + `lua/` 则跳过克隆，不反复备份覆盖 |

### 基础软件包

- 包列表：`git base-devel make cmake vim neovim tree curl wget openssh man-db man-pages which less unzip`，选 Zsh 时附加 `zsh zsh-completions`（Docker 为独立勾选项，见 Docker 章节）

非 root 运行会自动 `sudo` 重跑。WSL 默认登录用户**只在全部步骤成功后**才写入，避免中途失败卡在新用户。回到 root：`wsl -u root` 或先 `exit`。

### Docker

- 独立勾选项；勾选后安装 `docker docker-compose docker-buildx`（已装则跳过）
- 目标用户（非 root）自动加入 docker 组（成功后提示）；**需重新登录或 `newgrp docker` 后才免 sudo 使用 docker**
- **原生 Arch**：`systemctl enable docker`，失败时记录到末尾失败汇总
- **WSL**：跳过 `systemctl enable`，记录失败原因提示，引导使用 Docker Desktop WSL 集成或手动启动 `dockerd`

### Docker 镜像源

- 仅在勾选 **Docker** 后作为子项展开
- 勾选后写入 `/etc/docker/daemon.json`（原文件备份为 `daemon.json.bak.<时间戳>`）
- `registry-mirrors` 多源回退（已登记你提供的 `https://docker.1ms.run`）：
  - `https://docker.1ms.run`
  - `https://docker.mirrors.ustc.edu.cn`
  - `https://hub-mirror.c.163.com`
  - `https://mirror.baidubce.com`
- 原生 Arch 下 `systemctl restart docker` 使其生效；WSL/无 systemd 下由 dockerd 启动时自动读取

### Zsh 美化

- 安装 `zsh zsh-completions`（若未装）
- 将 `/bin/zsh` 写入 `/etc/shells`（若缺）
- 克隆三个插件到目标用户 `~/.zsh/`：
  - `zsh-users/zsh-autosuggestions`
  - `zsh-users/zsh-syntax-highlighting`
  - `romkatv/powerlevel10k`
- 写入 `~/.zshrc`：p10k 主题 + 两个插件 + 历史记录 + 补全 + 常用别名 + WSL `winhome` 别名
- 原目录已克隆则跳过（幂等）
- `chsh -s /bin/zsh` 对目标用户执行；若当前为 root 且目标用户非 root，则 root 一并切换，并为 root 生成 `.zshrc` 与插件目录

> 首次进入 zsh 后，powerlevel10k 会引导完成个性化配置（字体/样式）。

### NeoVim (LazyVim)

- **前置依赖**（单独作为 nvim 步骤前置安装）：`ripgrep fd unzip lazygit fzf nodejs npm gcc make`
- 备份现有 `~/.config/nvim`、`~/.local/share/nvim`、`~/.local/state/nvim`、`~/.cache/nvim` 为 `*.bak.<时间戳>`
- 克隆 [LazyVim/starter](https://github.com/LazyVim/starter) 到目标用户 `~/.config/nvim`，移除 `.git`
- 仅修正 nvim 目录 owner，不改写整个 `~/.config`

> 首次 `nvim` 启动会自动下载插件，请保持网络畅通。

## 结束时汇总

脚本执行完后统一打印三类提示，避免在长日志中翻找：

| 分类 | 含义 |
|------|------|
| **需立即处理** | 需要你现在执行的操作（如 `newgrp docker`、重登加载 zsh、首次启动 nvim） |
| **重启后自动生效** | 无需你操作，重启/重连后自动生效（如 WSL systemd、WSL 默认用户、daemon.json） |
| **失败项汇总** | 安装或配置失败但脚本继续的项，附手动修复命令，便于复查 |

## 注意事项

- 脚本会修改系统级文件（`/etc/pacman.conf`、`/etc/sudoers.d`、`/etc/shells`、`/etc/wsl.conf` 等），建议在全新系统执行；重要数据请先备份
- 已存在的配置目录会被备份而非删除，可手动恢复
- 重复执行不会破坏已克隆的插件目录；含本脚本标识的 `~/.zshrc` 会跳过覆盖，LazyVim starter 若已有 `init.lua` + `lua/` 也跳过（先备份旧 nvim 目录）
- WSL 下 docker 服务需自行处理（见 Docker 章节）

## 目录结构

```
arch-init/
  arch-setup.py  # 主脚本 (Python 3 + curses)
  init.bat       # 旧版 bash 脚本，仅作参考，不再执行
  README.md      # 本文档
```

## 许可

仅供个人使用。
