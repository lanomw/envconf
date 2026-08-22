# Arch Linux 初始化配置脚本

一键式 Arch Linux（含 WSL Arch）环境初始化脚本：替换清华源、安装基础开发软件、配置美化 Zsh、配置 NeoVim (LazyVim)，并可选创建普通用户。

## 特性

- 菜单化交互（menuconfig 风格，单列表+分组标题）：`↑↓` 移动 / `空格` 勾选、进入子菜单或执行（`回车` 同 `空格`）/ `q` 退出，列表过长自动滚动
- **按包选择**：多包组（基础软件包、终端编辑器、Node.js、Git 工具、Podman/K8s 等）行尾带 `▶` 与 `(已选/总数)` 计数，`空格` 进入子菜单逐包勾选，`a` 全选/全不选；**整组勾选状态由子选择决定，全不选即整组取消**。除锁定项与基础软件包（默认全选）外，其余软件默认未选中，未勾选的组进入子菜单时同样默认全不选
- 子菜单内每个包附一行关键说明（众所周知的不写）
- **详情栏**：菜单底部实时显示当前高亮项**到底会装哪些包 / 改哪些文件**，不必靠"基础软件包"这样的名字猜内容。按显示列宽折行，中英混排不会错位
- 菜单即确认：勾选完成后 `空格` 触发 `[执行]` 即可，**无独立确认表**
- **分组菜单**：`系统基础 / 系统服务 / Shell 与美化 / 开发工具 / CLI 增强 / 容器 / WSL`，一目了然
- 子项随父项展开：勾选 **Docker** 后自动出现 **Docker 镜像源** 子选项（多选镜像源，候选表内自选）
- **预检测锁定**：已安装的软件 / 已启用的服务 / 已配置的用户级项自动勾选并锁定，**空格无效不可取消**，避免重复配置
- **环境自适配**：WSL 下自动禁用不适用的项（CPU 微码、NetworkManager、chrony 时间同步、ufw 防火墙——均由 Windows 宿主管理），显示 `[-]` 与原因，不可勾选
- **时区自动判定且默认勾选**：选了国内镜像源或 IP 地理探测为中国大陆时，自动设 `Asia/Shanghai`，不再要求手动确认（其它地区才交互输入）；Locale 同为默认勾选，二者幂等无害、已配置自动锁定
- **Shell 与美化解耦**：Zsh 本体（默认 Shell）、Zsh 插件（自动建议/语法高亮）、终端提示符（单选：Powerlevel10k / starship / 不配置）三项独立；p10k 与 starship 互斥生成配置，选 p10k 自动勾选 Zsh，取消 Zsh 自动级联
- **软件清单可扩展**：除基础项外，内置 Python/Lua/PHP/Ruby/Java/Node.js/Rust/Go/C++/Git 工具/CLI 工具/容器 等 20+ 可选软件项；所有包名均取自官方仓库，`yay`/`paru` 仅 archlinuxcn 提供的包会在选中时**自动启用 archlinuxcn 仓库**
- **systemd 服务项**（sshd / cronie）：勾选后原生 Arch 自动 `systemctl enable --now`；WSL 下勾选了 WSL systemd 时自动 `systemctl enable`，重启后随 systemd 自启
- **reflector**（镜像自动优选）与手动镜像源二选一，并入镜像源单选子菜单
- 支持原生 Arch 与 WSL Arch
- 不创建新用户时，可指定已有用户；默认目标为 **root**（配置写入 `/root`）
- 创建新用户时，Zsh / NeoVim 等用户级配置统一落到新用户家目录
- **sudo 保障**：无论新建用户还是已有用户，脚本都会确保其在 `wheel` 组且 sudoers 放行（全新系统上会先装 sudo 再写配置，旧版此处存在 sudo 不可用的 bug）
- **属主兜底清扫**：执行结束前统一把目标用户家目录中脚本触碰过的路径属主修正为该用户，杜绝残留 root 属主文件导致用户改不了自己的配置（如 `.zshrc`/`.p10k.zsh`）
- 关键步骤失败（如用户创建、源同步）会中止并给出提示；非关键步骤失败则记录到末尾失败汇总
- 结束时汇总：**失败项** 与 **重启后自动生效** 两类提示，并附一句统一的重启建议；不再输出"需立即处理"类提示（此类事项重启后均自动解决）
- 中途失败后可安全重跑：已存在用户会跳过创建，镜像为多源回退，Zsh/NeoVim 已配置则跳过覆盖，daemon.json 合并写入不丢自定义键
- 多用户复用同一环境时：已配置的**镜像源 / locale 自动跳过**，不会重复改写

## 使用方法

单文件自举：脚本开头内嵌了一段 shell 引导层（stage 0），**全新系统上什么都不用先装**，直接跑即可。

```bash
sh arch-setup.py
```

非 root 会自动用 `sudo` 重新执行。也可以加执行权限后直接运行：

```bash
chmod +x arch-setup.py
sudo ./arch-setup.py
```

### 裸机上怎么先拿到这个脚本

Arch 的 `base` 元包**不含** curl / wget / git / python。pacman 内部用的是 libcurl，所以可以用它先把 curl 装出来：

```bash
pacman -Sy --noconfirm curl
curl -fsSLO <本仓库 raw 地址>/arch-setup.py
sh arch-setup.py
```

> **不支持 `curl ... | sh`**：引导层需要按路径重新执行自身，管道方式下 `$0` 不是文件，必定失败。脚本会检测到并明确报错。

在 WSL Arch 中用法相同：

```bash
sudo sh arch-setup.py
```

### stage 0 引导层做了什么

按依赖顺序处理"全新系统上什么都没配置"的情况，全部在 Python 主体启动之前完成：

| 步骤 | 处理的问题 |
|------|-----------|
| CRLF 自愈 | 在 Windows 上编辑过的脚本换行是 CRLF，会让 sh 报出无法理解的语法错误；检测到就去 CR 后重新执行自身 |
| Arch 检测 | 在任何写文件动作**之前**确认是 Arch，避免在别的发行版上乱写 `/etc/pacman.d/` |
| root | 非 root 自动 `sudo` 重执行 |
| TERM | chroot / 串口终端下 `TERM` 为空会让 curses 菜单直接抛异常 |
| **快速路径** | 已有 python3 时立刻进主体：**不联网、不改任何文件** |
| 系统时钟 | 时钟偏差会表现为 TLS「证书未生效」和 GPG「签名来自未来」，尝试 `hwclock -s` 校正 |
| 镜像源 | `mirrorlist` 无可用 `Server =` 时写入一份多源默认值 |
| pacman keyring | 全新 rootfs 的 keyring 为空，**必须在装任何包之前** `pacman-key --init/--populate` |
| 同步 + 升级 | `pacman -Sy` 失败时给出联网排查指引；再更新 `archlinux-keyring` 并整体 `-Su`，避免 `-Sy` 后直接 `-S` 的部分升级 |
| 安装 python | 失败时给出签名问题的手动修复命令 |

> 走快速路径时 stage 0 不做 keyring 初始化，这部分由 Python 侧的镜像源步骤兜底（该步骤无条件执行）。

## 执行流程

1. **stage 0 引导层**（sh）：CRLF 自愈、Arch 检测、root、TERM、时钟、镜像源、keyring、安装 python（详见上方"使用方法"）
2. **前置校验**（Python）：root 检测、`/etc/arch-release` 检测、WSL 检测
3. **菜单选择**（menuconfig 风格，分组菜单，选择即时生效，菜单即确认；`空格` 为主操作键，`回车` 等效）：
   - **目标用户**：`空格` 进入子菜单，选择 *创建新用户* 或 *配置已有用户*
   - **镜像源**：`空格` 进入单选子菜单（官方 / 清华 / 中科大 / 阿里 / 腾讯 / 华为 / **自动优选(reflector)**）
   - **多包组**（行尾带 `▶`）：`空格` 进入"按包选择"子菜单（`空格` 勾/消、`a` 全选/全不选、`esc` 返回），全不选即整组取消；未勾选的组进入时默认全不选（基础软件包默认全选）
   - **单包项**：`空格` 勾选/取消
   - **终端提示符**：`空格` 进入单选子菜单（Powerlevel10k / starship / 不配置），选 p10k 自动勾选 Zsh
   - **Zsh 插件 / LazyVim / Docker 镜像源**：依附父项的缩进子项，父项勾选后才出现，取消父项自动级联
   - 底部详情栏（绿色两行）：当前高亮项会装哪些包、启用哪个服务、改哪个配置文件。例如高亮"基础软件包"时显示 `安装: sudo git base-devel make cmake vim tree curl wget openssh man-db man-pages which less unzip  ·  空格: 按包选择`
   - 底部提示栏：动态操作提示（如"空格: 按包选择（全不选=取消整组）"）与固定图例同行显示
4. **执行阶段**：`空格` 触发 `[执行]`，按菜单顺序依次执行所选各项

## 软件清单（分组）

| 分组 | 可选项目 |
|------|----------|
| **系统基础** | 镜像源、Locale（默认勾选）、时区（默认勾选，中国环境自动）、基础软件包（17 包，默认全选、可按包取消）、AUR 助手(yay/paru，可按包选)、CPU 微码 |
| **系统服务** | 网络工具(NetworkManager，WSL 禁用)、SSH 服务端(sshd)、NTP 时间同步(chrony，WSL 禁用)、定时任务(cronie)、防火墙(ufw，WSL 禁用) |
| **Shell 与美化** | Zsh(设为默认 Shell；勾选后 Zsh 插件自动全选)、Zsh 插件(自动建议/语法高亮)、终端提示符(单选: Powerlevel10k / starship / 不配置；选中后字体作为依赖自动安装) |
| **开发工具** | Python、Lua、PHP、Ruby、Java(jdk-openjdk)、Node.js(nodejs/npm/pnpm，可按包选)、Rust(rustup)、Go、C/C++ 工具链(gcc/clang/valgrind，可按包选)、Git 工具(git-delta/lazygit/git-lfs，可按包选) |
| **CLI 增强** | 终端编辑器(neovim/helix/micro，可按包选) + LazyVim 配置子项(勾选 neovim 后自动勾选)、终端工具(tmux/btop/eza/bat/zoxide/fd/ripgrep/fzf/tldr，可按包选)、文件管理(yazi/broot/plocate/direnv，可按包选)、系统信息+磁盘(fastfetch/duf/ncdu)、JSON/YAML 工具(jq/go-yq)、网络诊断(nmap/mosh/httpie/iperf3/mtr/whois，可按包选) |
| **容器** | Docker、Docker 镜像源(子项，多选)、Podman/K8s(podman/kubectl/k9s/helm，可按包选) |
| **WSL** | WSL systemd（默认勾选，docker/sshd/cronie 的前提） |

> 标注"可按包选"的多包组可 `空格` 进入子菜单逐包勾选。所有包名均取自**官方仓库**（core/extra）；`yay`/`paru` 仅 archlinuxcn 仓库提供，选中时脚本自动启用 archlinuxcn（官方 cn 源 `repo.archlinuxcn.org`）。个别包安装失败时脚本会逐包重试定位坏包名，记入失败汇总，不中断流程、不拖垮整组。

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
- **sudo 保障**（新建与已有用户均执行，在基础软件包装好之后）：确保 sudo 已安装 → `usermod -aG wheel` → 写入 `/etc/sudoers.d/99-wheel` 启用 wheel 组 sudo → 校验用户确在 wheel 组。全新系统上 `/etc/sudoers` 尚不存在，脚本会先装 sudo 再写配置（旧版在装 sudo 之前写配置导致静默落空、新用户无法 sudo）
- **家目录属主保障**：新建用户的家目录在执行结束前**整树递归校验属主为该用户**——即使某步骤在"写入与 chown 之间"被打断也不会残留 root 属主文件；`~/.zshrc` 等配置文件先建空文件取得用户属主、再写入内容。已有用户则仅修正脚本触碰过的路径，不扩大范围
- WSL 下若选择设为默认登录用户，写入 `/etc/wsl.conf` 的 `[user] default=<name>`，重启 WSL 后自动生效（无需手动操作）

### 镜像源

在菜单中通过 `空格` 进入单选子菜单选择。

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
- **WSL**：`NetworkManager`、`chrony`、`ufw` 自动禁用（网络/时间/防火墙均由 Windows 宿主管理，菜单显示 `[-]` 及原因）；sshd/cronie 勾选了 WSL systemd 时自动 `systemctl enable`，重启后随 systemd 自启，未启用 systemd 则提示
- 服务项默认关闭，勾选才启用；服务已启用则**预检测锁定**

### 开发工具 / CLI 增强

这些分组为**纯软件包**项，勾选即 `pacman -S --needed` 安装（已装则跳过），失败记入末尾失败汇总，不中断流程。包清单见上方"软件清单"分组表。

### 时区 / CPU 微码

- **时区**（系统基础组，默认勾选）：**中国大陆环境自动设 `Asia/Shanghai`，不要求确认**——判定依据：所选镜像源为国内源（最强信号），或 best-effort IP 地理探测（`curl -m 3 ipinfo.io/country`，失败静默；会把 IP 暴露给第三方，介意可删）。非中国环境才交互输入。符号链接 `/etc/localtime`；原生 Arch 与 WSL 均生效，已是符号链接则预检测锁定。
- **CPU 微码**（系统基础组）：按 `/proc/cpuinfo` 自动识别 Intel→`intel-ucode` / AMD→`amd-ucode` 并安装；WSL 下跳过记入"重启后自动生效"。

### 中途失败后再执行

可以再跑，一般不会把环境配坏：

| 步骤 | 再执行时 |
|------|----------|
| 用户已创建 | 跳过 `useradd`，或菜单中改为配置该已有用户 |
| 镜像 | 官方源仍不改文件；国内源若已含所选源则跳过重写，否则重写多源列表 |
| Locale | 已启用 `en_US`/`zh_CN` 则跳过重新生成 |
| 基础软件 | `pacman --needed`，已装则跳过 |
| Zsh | 已克隆的插件目录跳过；含本脚本标识（新版"arch-setup"或旧版"美化版"）的 `.zshrc` 跳过覆盖 |
| NeoVim | 若已有 `init.lua` + `lua/` 则跳过克隆，不反复备份覆盖 |
| Docker 镜像源 | 合并写入：读回现有 `registry-mirrors`，仅在选择变化时改写，其余键保留 |

> 追加安装软件（如后来想加 php、yay）直接重跑并勾选新项即可：已配置项自动锁定跳过、`pacman --needed` 不重装。本脚本定位为**初始配置工具**，不是增量配置管理器。

### 基础软件包

- 包列表（17 个，**默认全选**，可 `空格` 进入逐包取消）：`sudo git base-devel make cmake vim tree curl wget openssh man-db man-pages which less unzip zip rsync`
- `neovim` 不在基础包里——由 CLI 增强的"终端编辑器"组/LazyVim 依赖自装，避免两处管理

非 root 运行会自动 `sudo` 重跑。WSL 默认登录用户**只在全部步骤成功后**才写入，避免中途失败卡在新用户。回到 root：`wsl -u root` 或先 `exit`。

### Docker

- 独立勾选项；勾选后安装 `docker docker-compose docker-buildx`（已装则跳过）
- 目标用户（非 root）自动加入 docker 组，重启/重新登录后即可免 sudo 使用 docker
- **原生 Arch**：`systemctl enable docker`，失败时记录到末尾失败汇总
- **WSL**：勾选了 WSL systemd 时自动 `systemctl enable docker`（重启后随 systemd 自启）；未启用 systemd 则提示手动启动 `dockerd` 或改用 Docker Desktop WSL 集成

### Docker 镜像源

- 仅在勾选 **Docker** 后作为子项展开；`空格` 进入多选子菜单，**全不选=停用**，默认未选中
- 候选表（多选，按选择顺序写入，表首三个为推荐组合；163/百度源已停服故不列入；镜像源可用性随时间变化，可自行修改脚本中的 `DOCKER_MIRRORS` 表）：

  | 标签 | 地址 | 备注 |
  |------|------|------|
  | 毫秒镜像 | `https://docker.1ms.run` | 速度快，推荐 |
  | DaoCloud | `https://docker.m.daocloud.io` | 老牌稳定 |
  | 1Panel | `https://docker.1panel.live` | |
  | 轩辕镜像 | `https://docker.xuanyuan.me` | 免费，速度快 |
  | 中科大 | `https://docker.mirrors.ustc.edu.cn` | 限校内 |

- **合并写入** `/etc/docker/daemon.json`：只替换 `registry-mirrors` 键，**其余配置键原样保留**（原文件先备份为 `daemon.json.bak.<时间戳>`）；文件不存在或无法解析时备份后写入全新内容
- 重跑时自动读回已配置的镜像源（含候选表之外手工添加的地址），不会用默认选择覆盖你的现有配置
- 原生 Arch 下 `systemctl restart docker` 使其生效；WSL/无 systemd 下重启后 dockerd 启动时自动读取

### Shell 与美化（Zsh / 插件 / 提示符）

Zsh 本体与美化彻底解耦，按需组合：

- **Zsh（设为默认 Shell）**：安装 `zsh zsh-completions`（若未装）、`/bin/zsh` 写入 `/etc/shells`（若缺）、写入基础 `~/.zshrc`（历史/补全/别名/WSL `winhome`，**不含任何主题与插件**）、`chsh -s /bin/zsh` 仅对目标用户执行
- **Zsh 插件**（缩进子项，勾选 Zsh 后出现且**默认全选**）：按包勾选 `zsh-autosuggestions` / `zsh-syntax-highlighting`，克隆到目标用户 `~/.zsh/` 并在 `.zshrc` 中 source；原目录已克隆则跳过（幂等）
- **终端提示符**（单选子菜单，与 Zsh 解耦）：
  - **Powerlevel10k**：zsh 专属主题，git clone 到 `~/.zsh/powerlevel10k`；**选中时自动勾选 Zsh（插件随之默认全选）**；首次登录触发个性化向导
  - **starship**：跨 Shell 提示符，pacman 安装；勾了 Zsh 则 `.zshrc` 生成 `starship init`，未勾 Zsh 仅安装包（bash 用户自行在 `~/.bashrc` 添加 eval）
  - p10k 与 starship **互斥**生成配置——旧版模板两者叠加加载、starship 覆盖 p10k 的冲突已修复
  - **字体自动安装**：选中任一提示符后，`ttf-meslo-nerd / noto-fonts-cjk / noto-fonts-emoji` 作为依赖自动安装（p10k 图标必需 Nerd 字体；`--needed` 幂等），不再作为菜单项
- **级联**：取消 Zsh 自动取消 Zsh 插件并重置 p10k（starship 保留）；已配置的 `.zshrc`（含旧版"美化版"标识）与插件目录、提示符均预检测锁定
- `~/.zshrc` 由脚本按当前选择动态生成；zoxide 装了会自动加载（同旧版）

### 终端编辑器 / LazyVim (NeoVim)

- **终端编辑器组**（CLI 增强）：`neovim / helix / micro` 按包勾选安装（helix 自带 LSP 无需配置分发；micro 开箱即用）；**子菜单中新勾选 neovim 时，LazyVim 配置自动勾选**（可再手动取消）
- **LazyVim 配置**（缩进子项，编辑器组里勾选 neovim 后出现）：
  - **前置依赖**（随 LazyVim 安装）：`neovim ripgrep fd unzip lazygit fzf nodejs npm gcc make`
  - 备份现有 `~/.config/nvim`、`~/.local/share/nvim`、`~/.local/state/nvim`、`~/.cache/nvim` 为 `*.bak.<时间戳>`
  - 克隆 [LazyVim/starter](https://github.com/LazyVim/starter) 到目标用户 `~/.config/nvim`，移除 `.git`
  - 仅修正 nvim 目录 owner，不改写整个 `~/.config`；取消 neovim 勾选后该项自动收起

> 首次 `nvim` 启动会自动下载插件，请保持网络畅通。

## 结束时汇总

脚本执行完后统一打印：

| 分类 | 含义 |
|------|------|
| **失败项汇总** | 安装或配置失败但脚本继续的项，附手动修复命令，便于复查 |
| **重启后自动生效** | 无需操作，仅供知晓（如 docker 组、wheel 组、WSL systemd、默认登录用户、p10k 首次向导、nvim 首次启动下载插件等） |

末尾附一句统一建议：**重启系统（WSL: 在 Windows 执行 `wsl --shutdown` 后重新打开终端）使全部配置生效**。不再输出"需立即处理"类提示——此类事项（组变更、服务自启、zsh 加载）重启后均自动解决，输出只会造成困扰。

## 注意事项

- **换行固定 LF**：仓库根目录 `.gitattributes`（`* text=auto eol=lf`）保证任何平台 checkout 后脚本都是 Linux 换行，可直接 `./arch-setup.py` 执行。即便文件后来被改成 CRLF（如 Windows 编辑器另存），stage 0 自愈机制仍可通过 `sh arch-setup.py` 启动并自动去 CR 重执行
- 脚本会修改系统级文件（`/etc/pacman.conf`、`/etc/sudoers.d`、`/etc/shells`、`/etc/wsl.conf` 等），建议在全新系统执行；重要数据请先备份
- 已存在的配置目录会被备份而非删除，可手动恢复
- 重复执行不会破坏已克隆的插件目录；含本脚本标识的 `~/.zshrc` 会跳过覆盖，LazyVim starter 若已有 `init.lua` + `lua/` 也跳过（先备份旧 nvim 目录）
- 执行结束前脚本会把目标用户家目录中脚本触碰过的路径属主统一修正为该用户（兜底清扫），避免中断残留 root 属主文件
- WSL 下 docker 服务需自行处理（见 Docker 章节）
- 脚本定位为**全新系统的初始配置**：重跑可安全追加软件包，但不做配置文件的增量合并管理（除 daemon.json 外，用户级配置以"已配置即跳过"为准）

## 目录结构

```
archlinux-setup/
  arch-setup.py  # 主脚本，单文件（sh 引导层 + Python 3 curses 主体）
  README.md      # 本文档
```

## 许可

仅供个人使用。
