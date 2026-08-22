#!/bin/sh
# -*- coding: utf-8 -*-
''':' #
# ===========================================================================
# wsl安装arch系统到指定路径
#   下载系统: https://fastly.mirror.pkgbuild.com/wsl/latest
#   注销系统: wsl --unregister archlinux
#   安装到指定位置: wsl --install --from-file C:/Users/atk/Downloads/archlinux-2026.08.01.174141.wsl --location E:/WSL/ArchLinux
#   进入系统: wsl -d archlinux -u root
#
# 注意: 上方示例路径必须用正斜杠——本文件开头是 Python 三引号字符串，
# Windows 风格反斜杠路径会形成非法 unicode 转义，导致 python 阶段直接解析失败。
#
# 进入系统后执行当前脚本进行环境配置
#
# stage 0: shell 引导层（单文件自举）
#   全新 Arch 上可能没有 python3 / 镜像源 / pacman keyring，这里按依赖顺序
#   把它们准备好，再把控制权交给下面的 Python 主体。
#
#   开头三行对 CRLF 换行免疫（行尾的 # 会吃掉 \r）：一旦在 stage 0 区域内检测
#   到 CR，就把自身去 CR 后重新执行。否则在 Windows 上编辑过的脚本会报出一堆
#   无法理解的 sh 语法错误（fi\r、heredoc 终止符失配）。
#   只扫前 200 行：Python 主体是 CRLF 无所谓（Python 走 universal newlines），
#   没必要为此多做一次重执行。若 stage 0 长过 200 行，记得同步调大。
# ===========================================================================
[ -r "$0" ] || { echo "错误: 不支持管道执行(curl ... | sh)，请先下载再运行: sh arch-setup.py" >&2; exit 1; } #
CR=$(printf '\r') #
[ -z "$(head -n 200 "$0" 2>/dev/null | tr -dc "$CR" | head -c 1)" ] || { _s=${TMPDIR:-/tmp}/arch-setup.$$.py; tr -d "$CR" < "$0" > "$_s" && exec sh "$_s" "$@"; } #

# --- 1. 必须是 Arch：放在任何写文件动作之前 --------------------------------
if [ ! -e /etc/arch-release ] && ! command -v pacman >/dev/null 2>&1; then
    echo "错误: 未检测到 Arch Linux（既无 /etc/arch-release 也无 pacman）" >&2
    exit 1
fi

# --- 2. 必须是 root --------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        exec sudo sh "$0" "$@"
    fi
    echo "错误: 请以 root 运行本脚本" >&2
    exit 1
fi

# --- 3. curses 需要 TERM，chroot / 串口终端下可能为空 ----------------------
[ -n "$TERM" ] || TERM=linux
export TERM

# --- 4. 快速路径：python3 已就绪时直接进主体，不联网、不改任何文件 --------
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$0" "$@"
fi

echo "未检测到 python3，开始引导（时钟 / 镜像源 / keyring / 安装 python）…"

# --- 5. 时钟：偏差会表现为 TLS 证书未生效、GPG 签名来自未来 ----------------
_year=$(date -u +%Y 2>/dev/null)
case $_year in ''|*[!0-9]*) _year=0 ;; esac
if [ "$_year" -lt 2024 ]; then
    echo "系统时钟异常（当前年份 $_year），尝试从硬件时钟校正…"
    hwclock -s >/dev/null 2>&1
    _year=$(date -u +%Y 2>/dev/null)
    case $_year in ''|*[!0-9]*) _year=0 ;; esac
    if [ "$_year" -lt 2024 ]; then
        echo "警告: 时钟仍不正确，包签名校验可能失败" >&2
        echo "      请手动执行: date -s 'YYYY-MM-DD HH:MM:SS'" >&2
    fi
fi

# --- 6. 镜像源列表为空时写入一份多源默认值（全新系统可能未配置）-----------
if ! grep -qE '^[[:space:]]*Server[[:space:]]*=' /etc/pacman.d/mirrorlist 2>/dev/null; then
    echo "镜像源列表为空，写入默认镜像…"
    mkdir -p /etc/pacman.d
    cat > /etc/pacman.d/mirrorlist <<'MIRRORLIST'
Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch
Server = https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch
Server = https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch
Server = https://mirror.rackspace.com/archlinux/$repo/os/$arch
Server = https://mirrors.kernel.org/archlinux/$repo/os/$arch
MIRRORLIST
fi

# --- 7. keyring：全新 rootfs 的 keyring 为空，装任何包之前必须先初始化 -----
if [ ! -s /etc/pacman.d/gnupg/pubring.gpg ]; then
    echo "初始化 pacman keyring…"
    pacman-key --init >/dev/null 2>&1
    pacman-key --populate archlinux >/dev/null 2>&1
fi

# --- 8. 同步软件源；失败时给出可直接照做的排查指引 -------------------------
echo "同步软件源…"
if ! pacman -Sy --noconfirm; then
    echo "错误: 软件源同步失败" >&2
    echo "  常见原因: 无网络 / DNS 不可用 / 镜像源不可达" >&2
    echo "  排查:  ip link   |   ping -c1 223.5.5.5   |   cat /etc/resolv.conf" >&2
    echo "  联网:  dhcpcd <网卡>   |   无线: iwctl   |   systemctl start NetworkManager" >&2
    exit 1
fi

# keyring 包过期会让后续所有签名校验失败，先单独更新它
pacman -S --noconfirm --needed archlinux-keyring >/dev/null 2>&1

# 整体升级：避免 -Sy 之后直接 -S 的部分升级（新 python 可能链接更新的 glibc，
# 装完直接跑不起来，而那时脚本已经没有可用的 python 自救了）
pacman -Su --noconfirm || echo "警告: 系统升级未完全成功，仍继续尝试安装 python" >&2

# --- 9. 安装 python 并交棒给 Python 主体 -----------------------------------
echo "安装 python…"
if ! pacman -S --noconfirm python; then
    echo "错误: 安装 python 失败" >&2
    echo "  若报签名相关错误，手动执行:" >&2
    echo "    pacman-key --init && pacman-key --populate archlinux" >&2
    echo "    pacman -Sy --noconfirm archlinux-keyring" >&2
    echo "  然后重跑: sh $0" >&2
    exit 1
fi

exec python3 "$0" "$@"
':'''
"""
Arch Linux 初始化配置脚本 (Python 3 + curses)
支持: 原生 Arch / WSL Arch
要求: 以 root 执行 (非 root 会自动用 sudo 重执行)

菜单 (menuconfig 风格):
  ↑/↓   移动
  空格  勾选/取消 单包项；进入子菜单（目标用户 / 镜像源 / 多包组"按包
        选择" / Docker 镜像源多选）；触发 [执行] / [退出]
        多包组的整组勾选状态由子选择决定: 全不选即整组取消;
        未勾选的组进入子菜单时默认全不选
  回车  同空格
  a     多选子菜单内全选 / 全不选
  q     退出

全新系统单文件自举: 直接 `sh arch-setup.py`
  脚本开头内嵌 shell 引导层 (stage 0)，按依赖顺序确保 Arch 检测 / root / TERM /
  系统时钟 / 镜像源 / pacman keyring / 软件源同步 / python 就绪后再进入本主体。
  已装 python3 时走快速路径: 直接进菜单，不联网、不改任何文件。

裸机上怎么拿到本脚本 (Arch base 元包不含 curl/wget/git/python):
  pacman -Sy --noconfirm curl && curl -fsSLO <raw-url> && sh arch-setup.py
  注意: 不支持 `curl ... | sh`——引导层需要按路径重新执行自身。
"""

import os
import re
import sys
import json
import time
import pwd
import grp
import getpass
import shutil
import subprocess
import curses
import unicodedata

# ---------------------------------------------------------------------------
#  工具函数
# ---------------------------------------------------------------------------

def is_wsl():
    try:
        with open("/proc/version") as f:
            return re.search(r"microsoft|wsl", f.read(), re.I) is not None
    except OSError:
        return False


def run(cmd, **kw):
    """运行命令并返回 CompletedProcess。"""
    return subprocess.run(cmd, **kw)


def run_ok(cmd, **kw):
    return subprocess.run(cmd, **kw).returncode == 0


def shell(cmd, **kw):
    """运行 shell 命令字符串。"""
    return subprocess.run(cmd, shell=True, **kw)


def pkg_installed(pkg):
    return subprocess.run(["pacman", "-Q", pkg], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def pacman_S(*pkgs):
    """pacman -S --needed --noconfirm pkgs...，返回是否成功。"""
    return run_ok(["pacman", "-S", "--needed", "--noconfirm", *pkgs])


def pacman_sync():
    """pacman -Syy，失败重试一次。"""
    if run_ok(["pacman", "-Syy", "--noconfirm"]):
        return True
    return run_ok(["pacman", "-Syy", "--noconfirm"])


def user_exists(user):
    try:
        pwd.getpwnam(user)
        return True
    except KeyError:
        return False


def user_home(user):
    try:
        return pwd.getpwnam(user).pw_dir
    except KeyError:
        return "/home/%s" % user


def user_group(user):
    try:
        return pwd.getpwnam(user).pw_gid
    except KeyError:
        return grp.getgrnam("users").gr_gid


def group_name(user):
    try:
        return grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name
    except (KeyError, IndexError):
        return "users"


def is_configurable(user):
    """root 或 uid>=1000 的普通用户。"""
    if user == "root":
        return True
    try:
        return pwd.getpwnam(user).pw_uid >= 1000
    except KeyError:
        return False


def configurable_users():
    """列出可配置用户: root + uid>=1000。"""
    users = []
    for pw in pwd.getpwall():
        if pw.pw_name == "root" or pw.pw_uid >= 1000:
            users.append(pw.pw_name)
    return sorted(users, key=lambda n: (n != "root", n))


def valid_username(name):
    return re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", name) is not None


def bash_as(user, script):
    """以 user 身份执行 bash 脚本。若 user 是当前用户则直接执行。"""
    if user == getpass.getuser():
        return subprocess.run(["bash", "-c", script])
    return subprocess.run(["runuser", "-u", user, "--", "bash", "-c", script])


def chown_r(path, user, group=None):
    if not os.path.exists(path):
        return
    if group is None:
        group = group_name(user)
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrnam(group).gr_gid
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            p = os.path.join(root, name)
            try:
                os.chown(p, uid, gid)
            except OSError:
                pass
        try:
            os.chown(root, uid, gid)
        except OSError:
            pass


def ensure_root(argv):
    if os.geteuid() == 0:
        return
    print("当前不是 root，尝试用 sudo 重新执行 …")
    if shutil.which("sudo"):
        os.execvp("sudo", ["sudo", sys.argv[0], *argv[1:]])
    sys.exit("请以 root 或 sudo 运行本脚本")


def ensure_archlinuxcn_repo(mirror):
    write_archlinuxcn_mirrorlist(mirror)
    conf = open("/etc/pacman.conf").read()
    if re.search(r"^\[archlinuxcn\]", conf, re.M):
        if not re.search(r"^Include\s*=\s*/etc/pacman.d/archlinuxcn-mirrorlist", conf, re.M):
            conf = re.sub(r"(?m)^\[archlinuxcn\]",
                          "[archlinuxcn]\nInclude = /etc/pacman.d/archlinuxcn-mirrorlist",
                          conf)
            open("/etc/pacman.conf", "w").write(conf)
        return
    with open("/etc/pacman.conf", "a") as f:
        f.write("\n[archlinuxcn]\nInclude = /etc/pacman.d/archlinuxcn-mirrorlist\n")


def write_mirrorlist(primary, url_of):
    order = ["official", "tuna", "ustc", "aliyun", "tencent", "huawei"]
    order.remove(primary)
    lines = ["# 首选: %s" % MIRROR_LABEL[primary]]
    lines.append("Server = %s" % url_of(primary))
    for m in order:
        lines.append("Server = %s" % url_of(m))
    return "\n".join(lines) + "\n"


def arch_url(m):
    return ARCH_URL[m]


def write_archlinuxcn_mirrorlist(primary):
    content = write_mirrorlist(primary, cn_url)
    with open("/etc/pacman.d/archlinuxcn-mirrorlist", "w") as f:
        f.write(content)


def wsl_conf_set(section, key, value):
    """安全改写 /etc/wsl.conf 的 section/key，不覆盖其它段。"""
    path = "/etc/wsl.conf"
    if not os.path.exists(path):
        open(path, "w").close()
    content = open(path).read()
    if not re.search(r"^\[%s\]" % re.escape(section), content, re.M):
        with open(path, "a") as f:
            f.write("\n[%s]\n%s=%s\n" % (section, key, value))
        return
    lines = content.split("\n")
    out = []
    insec = False
    for line in lines:
        if re.match(r"^\[%s\]\s*$" % re.escape(section), line):
            out.append(line)
            insec = True
            out.append("%s=%s" % (key, value))
            continue
        if re.match(r"^\[", line):
            insec = False
        if insec and re.match(r"^%s=" % re.escape(key), line):
            continue
        out.append(line)
    with open(path, "w") as f:
        f.write("\n".join(out))


def enable_wheel_sudo(failures):
    sudoers = "/etc/sudoers"
    if os.path.exists(sudoers):
        content = open(sudoers).read()
        if not re.search(r"^[#@]\s*includedir\s+/etc/sudoers\.d", content, re.M):
            with open(sudoers, "a") as f:
                f.write("\n@includedir /etc/sudoers.d\n")
    dropin = "/etc/sudoers.d/99-wheel"
    if os.path.isdir("/etc/sudoers.d"):
        if not os.path.exists(dropin):
            with open(dropin, "w") as f:
                f.write("%wheel ALL=(ALL:ALL) ALL\n")
            os.chmod(dropin, 0o440)
            ok("已写入 %s，启用 wheel 组 sudo" % dropin)
    elif os.path.exists(sudoers):
        content = open(sudoers).read()
        if re.search(r"^#?\s*%wheel ALL=\(ALL:ALL\) ALL", content, re.M):
            content = re.sub(r"(?m)^#?\s*%wheel ALL=\(ALL:ALL\) ALL",
                             "%wheel ALL=(ALL:ALL) ALL", content)
            open(sudoers, "w").write(content)
            ok("已启用 wheel 组的 sudo 权限")
        elif "%wheel ALL=(ALL:ALL) ALL" not in content:
            with open(sudoers, "a") as f:
                f.write("%wheel ALL=(ALL:ALL) ALL\n")
            ok("已追加 wheel 组的 sudo 权限")
    if shutil.which("visudo"):
        if not run_ok(["visudo", "-cf", sudoers]):
            warn("visudo 校验 /etc/sudoers 失败，请手动检查")


def ensure_user_sudo(st, failures):
    """确保目标用户可 sudo：加入 wheel 组 + sudoers 放行。

    必须在 sudo 包装好之后再写 sudoers：全新系统 /etc/sudoers 与
    /etc/sudoers.d 都不存在（sudo 未安装），enable_wheel_sudo 会
    整体静默落空，之后装上的 sudo 默认注释 %wheel，用户无法 sudo。
    对"已有用户"目标同样执行（旧版只在创建新用户分支里做）。
    """
    t = st["target_user"]
    if t == "root":
        return
    if not run_ok(["usermod", "-aG", "wheel", t]):
        failures.append("无法将 %s 加入 wheel 组，请手动执行: usermod -aG wheel %s" % (t, t))
    if not (os.path.exists("/etc/sudoers") or shutil.which("sudo")):
        info("检测到 sudo 未安装，先安装 …")
        if not pacman_S("sudo"):
            failures.append("sudo 安装失败，%s 暂无法使用 sudo，请手动执行: pacman -S sudo" % t)
            return
    os.makedirs("/etc/sudoers.d", exist_ok=True)
    enable_wheel_sudo(failures)
    groups = {g.gr_name for g in grp.getgrall() if t in g.gr_mem}
    groups.add(group_name(t))
    if "wheel" in groups:
        ok("%s 已在 wheel 组，重新登录后即可使用 sudo" % t)
    else:
        failures.append("%s 不在 wheel 组，sudo 不可用，请检查 usermod 是否成功" % t)


# ---------------------------------------------------------------------------
#  常量 / 镜像表
# ---------------------------------------------------------------------------

MIRROR_LABEL = {
    "official": "官方源",
    "tuna":     "清华源",
    "ustc":     "中科大源",
    "aliyun":   "阿里源",
    "tencent":  "腾讯源",
    "huawei":   "华为源",
    "reflector":"自动优选 (reflector)",
}

ARCH_URL = {
    "official": "https://geo.mirror.pkgbuild.com/$repo/os/$arch",
    "tuna":     "https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch",
    "ustc":     "https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch",
    "aliyun":   "https://mirrors.aliyun.com/archlinux/$repo/os/$arch",
    "tencent":  "https://mirrors.cloud.tencent.com/archlinux/$repo/os/$arch",
    "huawei":   "https://mirrors.huaweicloud.com/archlinux/$repo/os/$arch",
}

CN_URL = {
    "official": "https://repo.archlinuxcn.org/$arch",
    "tuna":     "https://mirrors.tuna.tsinghua.edu.cn/archlinuxcn/$arch",
    "ustc":     "https://mirrors.ustc.edu.cn/archlinuxcn/$arch",
    "aliyun":   "https://mirrors.aliyun.com/archlinuxcn/$arch",
    "tencent":  "https://mirrors.cloud.tencent.com/archlinuxcn/$arch",
    "huawei":   "https://mirrors.huaweicloud.com/archlinuxcn/$arch",
    "reflector":"https://repo.archlinuxcn.org/$arch",
}

def cn_url(m):
    return CN_URL.get(m, CN_URL["official"])

BASE_PKGS = ["sudo", "git", "base-devel", "make", "cmake", "vim",
             "tree", "curl", "wget", "openssh", "man-db", "man-pages",
             "which", "less", "unzip", "zip", "rsync"]

FONT_PKGS = ["ttf-meslo-nerd", "noto-fonts-cjk", "noto-fonts-emoji"]   # 提示符依赖,自动安装

NVIM_DEPS = ["neovim", "ripgrep", "fd", "unzip", "lazygit", "fzf", "nodejs", "npm",
             "gcc", "make"]

# 可勾选软件清单: key -> (标签, 包元组, 服务单元或 None)
#   纯包项  -> run_pkgs；带服务单元 -> run_service（非 WSL 时 systemctl enable --now）
#   多包组的标签只写类别名：包清单与说明在"按包选择"子菜单里展示（空格进入）
# 包名均取自官方仓库 (core/extra)；archlinuxcn 独有的包登记在 CN_PKGS，
# 选中这类包时 run_mirror 会自动启用 archlinuxcn 仓库。
PACKAGE_ITEMS = {
    # ---- 系统服务 ----
    "network":  ("网络工具 (NetworkManager)",  ("networkmanager",),     "NetworkManager"),
    "sshd":     ("SSH 服务端",                 ("openssh",),            "sshd"),
    "chrony":   ("NTP 时间同步",               ("chrony",),             "chronyd"),
    "cronie":   ("定时任务",                   ("cronie",),             "cronie"),
    "ufw":      ("防火墙 (ufw)",               ("ufw",),                "ufw"),
    # ---- 系统基础 / 包管理 ----
    "aur":      ("AUR 助手",                   ("yay", "paru"),         None),
    # ---- 开发工具（语言在前，工具在后）----
    "python":   ("Python",                     ("python",),             None),
    "lua":      ("Lua",                        ("lua",),                None),
    "php":      ("PHP",                        ("php",),                None),
    "ruby":     ("Ruby",                       ("ruby",),               None),
    "java":     ("Java (jdk-openjdk)",         ("jdk-openjdk",),        None),
    "node":     ("Node.js",                    ("nodejs", "npm", "pnpm"), None),
    "rustup":   ("Rust (rustup)",              ("rustup",),             None),
    "go":       ("Go",                         ("go",),                 None),
    "cpp":      ("C/C++ 工具链",               ("gcc", "clang", "valgrind"), None),
    "gittools": ("Git 工具",                   ("git-delta", "lazygit", "git-lfs"), None),
    # ---- CLI 增强 ----
    "cli":      ("终端工具",   ("tmux", "btop", "eza", "bat", "zoxide", "fd",
                                "ripgrep", "fzf", "tldr"), None),
    "editor":   ("终端编辑器", ("neovim", "helix", "micro"), None),
    "file":     ("文件管理",   ("yazi", "broot", "plocate", "direnv"), None),
    "sysinfo":  ("系统信息+磁盘",              ("fastfetch", "duf", "ncdu"), None),
    "json":     ("JSON/YAML 工具",            ("jq", "go-yq"),         None),
    "netdiag":  ("网络诊断",   ("nmap", "mosh", "httpie", "iperf3", "mtr", "whois"), None),
    # ---- 容器 ----
    "container":("Podman/K8s", ("podman", "kubectl", "k9s", "helm"),   None),
}

# 仅 archlinuxcn 仓库提供（官方仓库没有）的包:选中时自动启用 archlinuxcn
CN_PKGS = {"yay", "paru"}

# 包的一行说明（按包选择子菜单展示用）。众所周知的不写（lua/python/nodejs 等）。
PKG_DESC = {
    # 基础软件包
    "base-devel":  "AUR/源码构建工具组",
    "man-db":      "man 命令",
    "man-pages":   "系统手册页",
    # 开发
    "gcc":         "GNU C/C++ 编译器",
    "clang":       "C/C++ 编译器 (LLVM)",
    "valgrind":    "内存泄漏/性能检测",
    "npm":         "Node 包管理器 (Arch 的 nodejs 不自带)",
    "pnpm":        "快速省磁盘的包管理器",
    "yay":         "AUR 助手 [archlinuxcn 源]",
    "paru":        "AUR 助手 [archlinuxcn 源]",
    "git-delta":   "diff 语法高亮 (side-by-side)",
    "lazygit":     "git 终端 UI",
    # CLI 增强
    "neovim":      "vim 系现代编辑器",
    "helix":       "模态编辑器 (vim 系，自带 LSP)",
    "micro":       "易上手的编辑器",
    "yazi":        "终端文件管理器 TUI",
    "broot":       "交互式目录树导航",
    "plocate":     "全盘文件秒搜 (索引)",
    "direnv":      "按目录自动加载环境变量",
    "tmux":        "终端复用器",
    "btop":        "资源监视器 (top 替代)",
    "eza":         "ls 替代，图标+git 状态",
    "bat":         "cat 替代，语法高亮",
    "zoxide":      "智能 cd，记住常用目录",
    "fd":          "find 替代，语法更简",
    "ripgrep":     "grep 替代，极快 (LazyVim 依赖)",
    "fzf":         "模糊搜索 (Ctrl-R/Ctrl-T)",
    "tldr":        "命令示例速查",
    "fastfetch":   "系统信息概览 (neofetch 替代)",
    "duf":         "磁盘空间一览 (df 替代)",
    "ncdu":        "交互式磁盘占用分析",
    "go-yq":       "YAML/XML/TOML 处理器 (jq 语法)",
    "nmap":        "端口/主机扫描 (内含 ncat)",
    "mosh":        "弱网稳定的 SSH",
    "httpie":      "人性化的 curl",
    "iperf3":      "网络带宽测速",
    "mtr":         "traceroute+ping 合体",
    "whois":       "域名 WHOIS 查询",
    # 容器
    "podman":      "无守护进程容器引擎 (docker 替代)",
    "kubectl":     "Kubernetes 命令行",
    "k9s":         "Kubernetes TUI",
    "helm":        "Kubernetes 包管理器",
    # Zsh 插件（伪包名，走 git clone 而非 pacman）
    "zsh-autosuggestions":    "命令自动建议",
    "zsh-syntax-highlighting": "命令语法高亮",
}


def menu_pkgs(key):
    """任一勾选项对应的选择单元元组。

    统一覆盖 PACKAGE_ITEMS 与 base/fonts/zsh_plugins 等特殊项，
    使"按包选择"子菜单、(n/m) 计数、执行层取子集共用一套逻辑。
    """
    if key in PACKAGE_ITEMS:
        return PACKAGE_ITEMS[key][1]
    if key == "base":
        return tuple(BASE_PKGS)
    if key == "zsh_plugins":
        return tuple(name for _url, name in ZSH_PLUGINS)
    return ()


def menu_label(key):
    if key in PACKAGE_ITEMS:
        return PACKAGE_ITEMS[key][0]
    return {"base": "基础软件包", "zsh_plugins": "Zsh 插件"}[key]


def is_multi_pkg(key):
    """该菜单项是否为多包组（空格进入"按包选择"）。"""
    return len(menu_pkgs(key)) > 1


def selected_pkgs(st, key):
    """该组当前勾选的成员列表；未自定义时默认全选。"""
    pkgs = menu_pkgs(key)
    selmap = st.get("pkgsel", {}).get(key, {})
    return [p for p in pkgs if selmap.get(p, True)]


def chosen_pkgs(st):
    """所有已勾选组里当前选中的包集合（判断是否需要 archlinuxcn 用）。"""
    out = set()
    for key, (_, pkgs, _unit) in PACKAGE_ITEMS.items():
        if st.get(key):
            out.update(selected_pkgs(st, key))
    return out

# 非装包项的说明: key -> 这一项到底改了什么（菜单详情栏用）
ACTION_DETAIL = {
    "user":          "选择配置目标: 创建新用户 / 指定已有用户 / root",
    "mirror":        "改写 /etc/pacman.d/mirrorlist（所选源排第一，其余回退）",
    "locale":        "启用 en_US.UTF-8 + zh_CN.UTF-8，写入 /etc/locale.conf",
    "timezone":      "中国大陆环境自动设为 Asia/Shanghai（国内源/IP 判定），其它地区交互输入",
    "prompt":        "单选提示符主题: Powerlevel10k(zsh 专属,自动勾选 Zsh) / starship(跨 Shell,bash 也可用) / 不配置",
    "docker_mirror": "合并写入 /etc/docker/daemon.json 的 registry-mirrors（其余键保留）",
    "wsl_systemd":   "在 /etc/wsl.conf 写入 [boot] systemd=true",
    "wsl_default":   "在 /etc/wsl.conf 写入 [user] default=<新用户>",
}


def item_detail(key, st):
    """菜单详情栏：这一项到底会装哪些包 / 改哪些文件。"""
    if key in ACTION_DETAIL:
        return ACTION_DETAIL[key]
    if key in PACKAGE_ITEMS or key == "base":
        sel = selected_pkgs(st, key)
        s = "安装: " + (" ".join(sel) if sel else "（未选任何包，空格进入选择）")
        if key in PACKAGE_ITEMS and PACKAGE_ITEMS[key][2]:
            s += "  ·  启用服务: " + PACKAGE_ITEMS[key][2]
        if len(menu_pkgs(key)) > 1:
            s += "  ·  空格: 按包选择"
        return s
    if key == "microcode":
        return "安装: intel-ucode 或 amd-ucode（按 /proc/cpuinfo 自动识别，WSL 跳过）"
    if key == "zsh":
        s = "安装: zsh zsh-completions  ·  写入基础 ~/.zshrc 并 chsh"
        if st.get("prompt") == "p10k":
            s += "  ·  附带 p10k 主题克隆"
        elif st.get("prompt") == "starship":
            s += "  ·  附带 starship 集成"
        return s
    if key == "zsh_plugins":
        sel = selected_pkgs(st, "zsh_plugins")
        return ("克隆所选插件到 ~/.zsh/ 并在 .zshrc 加载: "
                + (" ".join(sel) if sel else "（未选任何插件，空格进入选择）"))
    if key == "nvim":
        return ("安装 LazyVim 依赖: " + " ".join(NVIM_DEPS)
                + "  ·  克隆 LazyVim/starter 到 ~/.config/nvim（旧配置先备份）")
    if key == "docker":
        return "安装: docker docker-compose docker-buildx  ·  启用服务: docker  ·  目标用户加入 docker 组"
    return ""


def disp_width(s):
    """终端显示宽度：CJK 全角字符按 2 列计。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def trunc_disp(s, limit):
    """按显示列宽截断。"""
    out, w = [], 0
    for c in s:
        cw = 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
        if w + cw > limit:
            break
        out.append(c)
        w += cw
    return "".join(out)


def wrap_disp(s, limit, max_lines):
    """按显示列宽折行，不拆开空格分隔的词；超出 max_lines 则末行加省略号。"""
    if limit < 4 or max_lines < 1:
        return []
    lines, cur = [], ""
    for token in re.findall(r"\S+\s*", s):
        if cur and disp_width(cur + token) > limit:
            lines.append(cur.rstrip())
            cur = ""
        cur += token
        while disp_width(cur) > limit:          # 单个词就超长，硬切
            head = trunc_disp(cur, limit)
            lines.append(head)
            cur = cur[len(head):]
    if cur.strip():
        lines.append(cur.rstrip())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = trunc_disp(lines[-1], limit - 1) + "…"
    return lines


def pad_disp(s, width):
    """按显示列宽右侧补空格到 width 列（CJK 宽字符安全）。"""
    return s + " " * max(0, width - disp_width(s))


# Zsh 增强插件（git clone 到 ~/.zsh/，非 pacman 包;按包选择子菜单用包名做键）
ZSH_PLUGINS = [
    ("https://github.com/zsh-users/zsh-autosuggestions", "zsh-autosuggestions"),
    ("https://github.com/zsh-users/zsh-syntax-highlighting", "zsh-syntax-highlighting"),
]

# 提示符主题: p10k 是 zsh 专属主题（git clone）;starship 跨 Shell（pacman 安装）
P10K_REPO = ("https://github.com/romkatv/powerlevel10k.git", "powerlevel10k")

PROMPT_LABEL = {"p10k": "Powerlevel10k", "starship": "starship", "": "未配置"}


def build_zsh_config(st):
    """按当前选择动态生成 .zshrc:插件与提示符互斥、按需加载。

    p10k 与 starship 只会写入其一——旧模板两者叠加加载,后初始化的
    starship 会覆盖 p10k 主题,属于实际冲突。
    """
    lines = []
    a = lines.append
    a("# ============================")
    a("#  Zsh 配置 — arch-setup 版")
    a("# ============================")
    a("export PATH=$HOME/.local/bin:$PATH")
    a("")
    a("setopt AUTO_CD")
    a("setopt CORRECT")
    a("setopt NO_BEEP")
    a("")
    a("HISTFILE=~/.zsh_history")
    a("HISTSIZE=10000")
    a("SAVEHIST=10000")
    a("setopt SHARE_HISTORY")
    a("setopt HIST_IGNORE_DUPS")
    a("setopt HIST_REDUCE_BLANKS")
    a("")
    a("alias ll='ls -alF --color=auto'")
    a("alias la='ls -A --color=auto'")
    a("alias l='ls -CF --color=auto'")
    a("alias grep='grep --color=auto'")
    a("alias ..='cd ..'")
    a("alias ...='cd ../..'")
    a("")
    a("autoload -Uz compinit && compinit")
    a("zstyle ':completion:*' menu select")
    a("zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'")
    a("")
    a('if grep -qi "microsoft\\|wsl" /proc/version 2>/dev/null; then')
    a("    alias winhome='cd /mnt/c/Users/$([ ! -z \"$USER\" ] && echo $USER || echo $USERNAME)'")
    a("fi")
    a("")
    if st.get("zsh_plugins"):
        for name in selected_pkgs(st, "zsh_plugins"):
            a('source $HOME/.zsh/%s/%s.zsh' % (name, name))
        a("")
    if st.get("prompt") == "p10k":
        a('source $HOME/.zsh/powerlevel10k/powerlevel10k.zsh-theme')
        a('[[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh')
        a("")
    elif st.get("prompt") == "starship":
        a('if command -v starship >/dev/null 2>&1; then')
        a('    eval "$(starship init zsh)"')
        a('fi')
        a("")
    a('if command -v zoxide >/dev/null 2>&1; then')
    a('    eval "$(zoxide init zsh)"')
    a('fi')
    a("")
    a('[[ -f ~/.zsh_env ]] && source ~/.zsh_env')
    return "\n".join(lines) + "\n"

# Docker registry-mirrors 候选表: (key, 标签, URL, 备注)
#   菜单中多选，按选择顺序写入 daemon.json 的 registry-mirrors。
#   默认全部未选中；表首三个为推荐组合，仅在"已有 daemon.json 但无镜像源"
#   时作为种子。163/百度等源 2024 年起已停服，不再列入；镜像源可用性随
#   时间变化，可自行增删。
DOCKER_MIRRORS = [
    ("1ms",      "毫秒镜像", "https://docker.1ms.run",             "速度快，推荐"),
    ("daocloud", "DaoCloud", "https://docker.m.daocloud.io",       "老牌稳定"),
    ("1panel",   "1Panel",   "https://docker.1panel.live",         ""),
    ("xuanyuan", "轩辕镜像", "https://docker.xuanyuan.me",         "免费，速度快"),
    ("ustc",     "中科大",   "https://docker.mirrors.ustc.edu.cn", "限校内"),
]
DOCKER_MIRROR_DEFAULT = ["1ms", "daocloud", "1panel"]

# ---------------------------------------------------------------------------
#  预检测 (包 + 用户级配置)
# ---------------------------------------------------------------------------

def detect(st):
    """根据目标用户刷新 locked 表；已存在的项强制勾选并锁定。"""
    st["target_user"] = resolve_target(st)
    st["locked"] = {}
    t = st["target_user"]
    home = user_home(t)

    def lock(key, present):
        if present:
            st["locked"][key] = True
            st[key] = True

    lock("base", all(pkg_installed(p) for p in BASE_PKGS))
    lock("docker", pkg_installed("docker") or shutil.which("docker") is not None)
    lock("docker_mirror", os.path.exists("/etc/docker/daemon.json"))
    if st["locked"].get("docker_mirror"):
        # 已配置过:读回现有镜像源，重跑合并写入时不丢用户已有选择；
        # 已有 daemon.json 但无 registry-mirrors 时用推荐组合作种子
        keys, extra = read_configured_mirrors()
        if keys or extra:
            st["docker_mirrors"] = keys
            st["dmirror_extra"] = extra
        else:
            st["docker_mirrors"] = list(DOCKER_MIRROR_DEFAULT)
    lock("locale", locale_present())
    lock("zsh", user_zsh_present(home))
    lock("zsh_plugins",
         all(os.path.isdir(os.path.join(home, ".zsh", name, ".git"))
             for _u, name in ZSH_PLUGINS))
    # 提示符已配置过则锁定并回显（重跑改写受 .zshrc 标识跳过保护约束）
    if os.path.isdir(os.path.join(home, ".zsh", "powerlevel10k")):
        st["prompt"] = "p10k"
        st["locked"]["prompt"] = True
    elif pkg_installed("starship") or shutil.which("starship") is not None:
        st["prompt"] = "starship"
        st["locked"]["prompt"] = True
    lock("nvim", user_nvim_present(home))
    lock("timezone", os.path.islink("/etc/localtime"))
    lock("microcode", pkg_installed("intel-ucode") or pkg_installed("amd-ucode"))
    for key, (label, pkgs, unit) in PACKAGE_ITEMS.items():
        if unit:
            lock(key, service_enabled(unit))
        else:
            lock(key, all(pkg_installed(p) for p in pkgs))
    if is_wsl():
        lock("wsl_systemd", wsl_systemd_present())

    # ---- 当前环境明确不支持的项：禁用并强制取消勾选，避免无效选择 ----
    st["disabled"] = {}

    def disable(key, reason):
        # 已安装/已配置的按"已配置"显示即可，不必再提不支持
        if st["locked"].get(key):
            return
        st["disabled"][key] = reason
        st[key] = False

    if is_wsl():
        disable("microcode", "WSL 不适用，微码由 Windows 宿主管理")
        disable("network", "WSL 无效，网络由 Windows 宿主管理")
        disable("chrony", "WSL 无效，时间由 Windows 宿主自动同步")
        disable("ufw", "WSL 无效，防火墙由 Windows 宿主管理")
    elif microcode_pkg() is None:
        disable("microcode", "无法从 /proc/cpuinfo 识别 CPU 厂商")

    # reflector best-effort：mirrorlist 已是 reflector 生成则默认选中
    if reflector_present():
        st["mirror"] = "reflector"
    # WSL 下 reflector 不执行，若已选中则退回官方源
    if is_wsl() and st["mirror"] == "reflector":
        st["mirror"] = "official"


def locale_present():
    try:
        gen = open("/etc/locale.gen").read()
    except OSError:
        return False
    have_locales = bool(re.search(r"^en_US\.UTF-8", gen, re.M)) and \
                   bool(re.search(r"^zh_CN\.UTF-8", gen, re.M))
    try:
        conf = open("/etc/locale.conf").read()
    except OSError:
        conf = ""
    return have_locales and bool(re.search(r"^LANG=en_US\.UTF-8", conf, re.M))


def user_zsh_present(home):
    rc = os.path.join(home, ".zshrc")
    if not os.path.isfile(rc):
        return False
    try:
        content = open(rc).read()
    except OSError:
        return False
    # "美化版" 是旧版标识，保留兼容避免重跑时误覆盖旧配置
    return "美化版" in content or "arch-setup" in content


def user_nvim_present(home):
    init = os.path.join(home, ".config", "nvim", "init.lua")
    lua = os.path.join(home, ".config", "nvim", "lua")
    return os.path.isfile(init) and os.path.isdir(lua)


def wsl_systemd_present():
    try:
        content = open("/etc/wsl.conf").read()
    except OSError:
        return False
    m = re.search(r"^\[boot\]\s*$", content, re.M)
    return m is not None and re.search(r"^systemd\s*=\s*true", content[m.end():], re.M) is not None


def reflector_present():
    """mirrorlist 是否已是 reflector 生成（含其生成注释头）。"""
    try:
        content = open("/etc/pacman.d/mirrorlist").read()
    except OSError:
        return False
    return "## Arch Linux repository mirrorlist" in content and "# Generated by reflector" in content


def read_configured_mirrors():
    """读取现有 daemon.json 的 registry-mirrors，映射回候选表 key。

    返回 (keys, extra)：候选表内的 URL 归为 key，候选表外的原样保留在
    extra——重跑合并写入时一并写回，不丢用户手工加的镜像源。
    """
    try:
        with open("/etc/docker/daemon.json") as f:
            data = json.load(f)
        urls = data.get("registry-mirrors", []) if isinstance(data, dict) else []
    except (OSError, ValueError):
        return [], []
    known = {u: k for k, _l, u, _n in DOCKER_MIRRORS}
    keys = [known[u] for u in urls if u in known]
    extra = [u for u in urls if u not in known]
    return keys, extra


# ---------------------------------------------------------------------------
#  执行层
# ---------------------------------------------------------------------------

def run_create_user(st, reboot, failures):
    if not st["create_user"]:
        return
    u = st["new_username"]
    if user_exists(u):
        ok("用户 %s 已存在，跳过 useradd（可安全重跑）" % u)
        run(["usermod", "-aG", "wheel", u])
    else:
        info("创建用户: %s" % u)
        if not run_ok(["useradd", "-m", "-G", "wheel", "-s", "/bin/bash", u]):
            raise SystemExit("useradd %s 失败，脚本中止" % u)
        while True:
            pw1 = getpass.getpass("请为新用户 %s 设置密码: " % u)
            pw2 = getpass.getpass("再次输入密码: ")
            if pw1 and pw1 == pw2:
                break
            err("两次输入不一致或为空，请重试")
        if run(["chpasswd"], input="%s:%s\n" % (u, pw1), text=True).returncode:
            failures.append("为用户 %s 设置密码失败" % u)
    # wheel 组 sudo 放行移到 ensure_user_sudo：需等 base 装好 sudo 后执行
    if is_wsl() and st["wsl_default"]:
        st["_pending_wsl_default"] = u
        info("WSL 默认登录用户将在全部步骤成功后写入，避免中途失败卡在新用户")


def run_mirror(st, reboot, failures):
    mirror = st["mirror"]
    if mirror == "official":
        info("已选择官方源，保持现有 mirrorlist 与 pacman.conf 不变")
    elif mirror == "reflector":
        run_reflector(st, reboot, failures)
    else:
        info("配置镜像源：%s（所选源优先，其余回退）…" % MIRROR_LABEL[mirror])
        ml = "/etc/pacman.d/mirrorlist"
        if os.path.exists(ml):
            shutil.copy2(ml, "%s.bak.%d" % (ml, int(time.time())))
        content = write_mirrorlist(mirror, arch_url)
        with open(ml, "w") as f:
            f.write(content)

    cn_enabled = False
    # 选中了仅 archlinuxcn 提供的包（bun/paru 等）时，即使官方源也自动启用 archlinuxcn
    if (mirror in ("tuna", "ustc", "aliyun", "tencent", "huawei")
            or st["aur"] or chosen_pkgs(st) & CN_PKGS):
        ensure_archlinuxcn_repo(mirror)
        cn_enabled = True

    if not run_ok(["pacman-key", "--init"]):
        warn("pacman-key --init 失败，继续尝试")
        failures.append("pacman-key --init 失败，可能影响包签名校验")
    if not run_ok(["pacman-key", "--populate", "archlinux"]):
        warn("pacman-key --populate archlinux 失败，继续尝试")
        failures.append("pacman-key --populate archlinux 失败，可能影响包签名校验")

    if not pacman_sync():
        raise SystemExit("软件源同步失败。请检查网络后重跑本脚本（可安全重跑，不会重复创建用户）")

    if cn_enabled:
        if not pacman_S("archlinuxcn-keyring"):
            warn("archlinuxcn-keyring 安装失败，后续 archlinuxcn 软件可能无法签名校验")
            failures.append("archlinuxcn-keyring 安装失败，请手动执行: pacman -S archlinuxcn-keyring")
        else:
            run(["pacman-key", "--populate", "archlinuxcn"])
    ok("镜像源配置完成")


def run_base(st, reboot, failures):
    pkgs = selected_pkgs(st, "base")
    if not pkgs:
        info("基础软件包: 未选择任何包，跳过")
        return
    if not pacman_S(*pkgs):
        failures.append("基础软件包安装失败，请手动执行: pacman -S %s" % " ".join(pkgs))
        warn("基础软件包安装失败，脚本继续（后续依赖可能缺失）")
        return
    ok("基础软件包安装完成 (%d 个)" % len(pkgs))


def service_enabled(unit):
    """systemctl is-enabled 返回 0 表示已启用。WSL 恒 False。"""
    if is_wsl():
        return False
    return run_ok(["systemctl", "is-enabled", unit])


def run_pkgs(st, key, reboot, failures):
    """纯包项：安装该组当前选中的包；整组失败时逐包重试定位坏包名。"""
    label, _pkgs, _ = PACKAGE_ITEMS[key]
    pkgs = selected_pkgs(st, key)
    if not pkgs:
        info("%s: 未选择任何包，跳过" % label)
        return
    info("安装 %s: %s …" % (label, " ".join(pkgs)))
    if pacman_S(*pkgs):
        ok("%s 已安装" % label)
        return
    # pacman 遇到一个不存在的目标会整批失败：逐包重试，别让一个坏名字拖垮整组
    bad = [p for p in pkgs if not pacman_S(p)]
    if bad:
        failures.append("%s 部分安装失败: %s（可能不在当前已配置的仓库，请手动确认包名）"
                        % (label, " ".join(bad)))
        warn("%s 安装失败: %s" % (label, " ".join(bad)))
    else:
        ok("%s 已安装（整组失败但逐包重试成功）" % label)


def run_service(st, key, reboot, failures):
    """服务项：装包（如无）→ 非 WSL 时 systemctl enable --now；WSL 跳过并记重启。"""
    label, pkgs, unit = PACKAGE_ITEMS[key]
    info("配置 %s (%s) …" % (label, unit))
    if pkgs and not pacman_S(*pkgs):
        failures.append("%s 包安装失败，请手动: pacman -S %s" % (label, " ".join(pkgs)))
        warn("%s 包安装失败，脚本继续" % label)
        return
    if is_wsl():
        if st.get("wsl_systemd"):
            run_ok(["systemctl", "enable", unit])   # 只建开机软链，不需要 systemd 已运行
            reboot.append("%s 已安装并 enable，重启 WSL 后由 systemd 自动启动" % label)
        else:
            reboot.append("%s 已安装；未启用 systemd，重启后不会自启（可勾选 WSL systemd 项）" % label)
        ok("%s 已安装（WSL）" % label)
        return
    if not run_ok(["systemctl", "enable", "--now", unit]):
        failures.append("%s 服务启动失败，请手动执行: systemctl enable --now %s" % (label, unit))
        warn("%s 服务启动失败" % unit)
        return
    ok("%s 服务已启用并启动 (%s)" % (label, unit))


def run_reflector(st, reboot, failures):
    """reflector 自动优选镜像源；严格仅非 WSL 执行（WSL 易出错）。"""
    ml = "/etc/pacman.d/mirrorlist"
    if is_wsl():
        reboot.append("已选择 reflector；WSL 下不执行，请在 Linux 原生环境运行或手动选择镜像源")
        ok("已选择 reflector（WSL 跳过，记入重启说明）")
        return
    info("用 reflector 自动优选镜像源 …")
    if not run_ok(["reflector", "--latest", "10", "--protocol", "https",
                   "--sort", "rate", "--save", ml]):
        failures.append("reflector 自动优选失败，请手动执行: reflector --latest 10 --protocol https --sort rate --save /etc/pacman.d/mirrorlist")
        warn("reflector 自动优选失败")
        return
    ok("reflector 已生成最优镜像列表")


CN_MIRROR_KEYS = ("tuna", "ustc", "aliyun", "tencent", "huawei")


def looks_like_cn(st):
    """中国大陆环境判定:国内镜像源是最强信号,再退一步做 IP 地理探测。

    geo 探测 best-effort（3 秒超时、失败静默），会把 IP 暴露给
    ipinfo.io——介意可删掉这段，只会退回交互输入。
    """
    if st.get("mirror") in CN_MIRROR_KEYS:
        return True
    try:
        r = subprocess.run(["curl", "-fsS", "-m", "3", "https://ipinfo.io/country"],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0 and r.stdout.strip() == "CN"
    except Exception:
        return False


def run_timezone(st, reboot, failures):
    """设置系统时区;中国大陆环境自动设 Asia/Shanghai,不再要求手动确认。"""
    if looks_like_cn(st):
        tz = "Asia/Shanghai"
        info("检测到中国大陆环境，时区自动设为 %s" % tz)
    else:
        tz = "Asia/Shanghai"
        try:
            ans = input("设置系统时区（默认 Asia/Shanghai，回车使用默认）: ").strip()
            if ans:
                tz = ans
        except (EOFError, KeyboardInterrupt):
            pass
    zonefile = "/usr/share/zoneinfo/%s" % tz
    if not os.path.exists(zonefile):
        failures.append("时区 %s 不存在，未设置" % tz)
        warn("时区 %s 不存在" % tz)
        return
    info("设置时区: %s" % tz)
    if os.path.exists("/etc/localtime"):
        os.remove("/etc/localtime")
    if not run_ok(["ln", "-s", zonefile, "/etc/localtime"]):
        failures.append("设置时区 %s 失败" % tz)
        warn("设置时区失败")
        return
    ok("时区已设为 %s" % tz)


def run_ufw(st, reboot, failures):
    """防火墙：原生 Arch 装 ufw、放行 SSH、启用并注册服务；WSL 跳过记重启。"""
    label, pkgs, unit = PACKAGE_ITEMS["ufw"]
    info("配置 %s …" % label)
    if pkgs and not pacman_S(*pkgs):
        failures.append("%s 安装失败，请手动: pacman -S %s" % (label, " ".join(pkgs)))
        warn("%s 安装失败，脚本继续" % label)
        return
    if is_wsl():
        reboot.append("%s 已安装；WSL 下不启用防火墙，请在 Linux 原生环境启用" % label)
        ok("%s 已安装（WSL：请在原生环境启用）" % label)
        return
    if not run_ok(["ufw", "allow", "OpenSSH"]):
        warn("ufw allow OpenSSH 失败（可能 OpenSSH 服务未启用）")
    if not run_ok(["ufw", "--force", "enable"]):
        failures.append("ufw 启用失败，请手动执行: ufw --force enable && systemctl enable ufw")
        warn("ufw 启用失败")
        return
    run_ok(["systemctl", "enable", "ufw"])
    ok("ufw 已启用并放行 OpenSSH")


def microcode_pkg():
    """按 /proc/cpuinfo 得出应装的微码包；无法识别厂商返回 None。"""
    try:
        with open("/proc/cpuinfo") as f:
            data = f.read()
    except OSError:
        return None
    if re.search(r"\bGenuineIntel\b", data):
        return "intel-ucode"
    if re.search(r"\bAuthenticAMD\b", data):
        return "amd-ucode"
    return None


def run_microcode(st, reboot, failures):
    """CPU 微码：依据 /proc/cpuinfo 安装 intel-ucode 或 amd-ucode。

    WSL 与厂商无法识别两种情况已在菜单侧禁用，这里仅作兜底。
    """
    if is_wsl():
        reboot.append("CPU 微码由 Windows 宿主管理，跳过")
        ok("CPU 微码（WSL：由宿主管理，跳过）")
        return
    pkg = microcode_pkg()
    if not pkg:
        failures.append("无法识别 CPU 厂商，未安装微码")
        warn("无法识别 CPU 厂商")
        return
    info("安装 CPU 微码: %s" % pkg)
    if not pacman_S(pkg):
        failures.append("%s 安装失败，请手动执行: pacman -S %s" % (pkg, pkg))
        warn("%s 安装失败" % pkg)
        return
    ok("%s 已安装" % pkg)


def run_docker(st, reboot, failures):
    t = st["target_user"]
    if not (pkg_installed("docker") or shutil.which("docker")):
        info("安装 Docker …")
        if not pacman_S("docker", "docker-compose", "docker-buildx"):
            failures.append("docker 安装失败，请手动执行: pacman -S docker docker-compose docker-buildx")
            warn("docker 安装失败，脚本继续（Docker 镜像源等后续步骤仍会执行）")
            return
    else:
        info("docker 已安装，跳过")

    if t != "root":
        if run_ok(["usermod", "-aG", "docker", t]):
            reboot.append("%s 已加入 docker 组，重启/重新登录后可免 sudo 使用 docker" % t)
        else:
            failures.append("无法将 %s 加入 docker 组" % t)

    if is_wsl():
        if st["wsl_systemd"]:
            # systemctl enable 只创建开机软链，不需要 systemd 已运行；重启 WSL 后自启
            if run_ok(["systemctl", "enable", "docker"]):
                reboot.append("docker 服务已 enable，重启 WSL 后随 systemd 自动启动")
            else:
                failures.append("systemctl enable docker 失败，请重启后手动执行: sudo systemctl enable --now docker")
        else:
            reboot.append("WSL 未启用 systemd：重启后需手动启动 dockerd，或改用 Docker Desktop（WSL 集成）")
    else:
        if not run_ok(["systemctl", "enable", "docker"]):
            err("systemctl enable docker 失败")
            failures.append("systemctl enable docker 失败，请手动执行: systemctl enable --now docker")
        else:
            ok("docker 服务已启用")
    ok("Docker 安装配置完成")


def run_docker_mirror(st, reboot, failures):
    if not st["docker_mirror"]:
        return
    urls = [u for k, _l, u, _n in DOCKER_MIRRORS if k in st["docker_mirrors"]]
    urls += st.get("dmirror_extra") or []   # 用户手工配置过的候选表外镜像源，原样写回
    if not urls:
        warn("未选择任何 Docker 镜像源，跳过该项")
        return
    info("配置 Docker 镜像源: %s …" % " ".join(urls))
    os.makedirs("/etc/docker", exist_ok=True)
    cfg = "/etc/docker/daemon.json"
    merged = False
    if os.path.exists(cfg):
        # 合并写入：只替换 registry-mirrors，保留用户已有的其它配置键
        try:
            with open(cfg) as f:
                data = json.load(f)
            if isinstance(data, dict):
                shutil.copy2(cfg, "%s.bak.%d" % (cfg, int(time.time())))
                data["registry-mirrors"] = urls
                with open(cfg, "w") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                merged = True
                ok("已合并写入 registry-mirrors（原文件已备份，其余配置保留）")
        except (ValueError, OSError):
            pass
    if not merged:
        if os.path.exists(cfg):
            shutil.copy2(cfg, "%s.bak.%d" % (cfg, int(time.time())))
            warn("原 daemon.json 不存在或无法解析，备份后写入")
        with open(cfg, "w") as f:
            json.dump({"registry-mirrors": urls}, f, indent=2)
            f.write("\n")
    if not is_wsl() and shutil.which("systemctl"):
        if run_ok(["systemctl", "restart", "docker"]):
            ok("docker 服务已重启加载镜像源")
        else:
            failures.append("docker 重启加载镜像源失败，请手动执行: systemctl restart docker")
    else:
        reboot.append("daemon.json 已写入，重启后 dockerd 启动时自动读取生效")
    ok("Docker 镜像源已写入 /etc/docker/daemon.json")


def run_locale(st, reboot, failures):
    info("配置 Locale (en_US.UTF-8 + zh_CN.UTF-8) …")
    gen = "/etc/locale.gen"
    content = open(gen).read() if os.path.exists(gen) else ""
    changed = False
    for loc in ["en_US.UTF-8", "zh_CN.UTF-8"]:
        if re.search(r"^#%s\s" % re.escape(loc), content, re.M):
            content = re.sub(r"(?m)^#%s\s.*" % re.escape(loc), "%s UTF-8" % loc, content)
            changed = True
        elif not re.search(r"^%s\s" % re.escape(loc), content, re.M):
            content += "%s UTF-8\n" % loc
            changed = True
    if not changed:
        info("locale 已配置，跳过（多用户复用）")
        return
    with open(gen, "w") as f:
        f.write(content)
    if not run_ok(["locale-gen"]):
        failures.append("locale-gen 失败，Locale 可能未生效")
        warn("locale-gen 执行失败，locale 配置可能未生效")
        return
    with open("/etc/locale.conf", "w") as f:
        f.write("LANG=en_US.UTF-8\n")
    ok("Locale 已写入 /etc/locale.conf (LANG=en_US.UTF-8)，已生成中英 UTF-8")


def run_zsh(st, reboot, failures):
    t = st["target_user"]
    home = user_home(t)
    info("配置 Zsh (目标: %s , 家目录: %s) …" % (t, home))

    if not (pkg_installed("zsh") or shutil.which("zsh")):
        if not pacman_S("zsh", "zsh-completions"):
            failures.append("zsh 安装失败，Zsh 配置将跳过")
            warn("zsh 安装失败，跳过 Zsh 配置")
            return
    ensure_zsh_in_shells()

    zsh_dir = os.path.join(home, ".zsh")
    os.makedirs(zsh_dir, exist_ok=True)
    chown_r(zsh_dir, t)

    # 待克隆清单:所选增强插件 + p10k 主题（若提示符选了 p10k）
    clones = []
    if st.get("zsh_plugins"):
        clones += [(url, name) for url, name in ZSH_PLUGINS
                   if name in selected_pkgs(st, "zsh_plugins")]
    if st.get("prompt") == "p10k":
        clones.append(P10K_REPO)
    for url, name in clones:
        dest = os.path.join(zsh_dir, name)
        if os.path.isdir(os.path.join(dest, ".git")):
            continue
        if bash_as(t, "git clone --depth=1 '%s' '%s'" % (url, dest)).returncode != 0:
            warn("以 %s 克隆失败，改用当前用户克隆到 %s" % (t, dest))
            if subprocess.run(["git", "clone", "--depth=1", url, dest]).returncode != 0:
                failures.append("zsh 插件 %s 克隆失败，请手动安装" % name)
                warn("zsh 插件 %s 克隆失败" % name)

    chown_r(zsh_dir, t)

    # 提示符为 starship 时安装包（p10k 是克隆仓库，上面已处理）
    if st.get("prompt") == "starship" and not pkg_installed("starship"):
        if not pacman_S("starship"):
            failures.append("starship 安装失败，请手动执行: pacman -S starship")

    rc = os.path.join(home, ".zshrc")
    ours = False
    if os.path.isfile(rc):
        try:
            content = open(rc).read()
            # "美化版" 为旧版标识，同样视为本脚本产物，避免重跑误覆盖
            ours = "美化版" in content or "arch-setup" in content
        except OSError:
            ours = False
    if ours:
        info("已检测到本脚本写入的 .zshrc，跳过覆盖（可安全重跑）")
        # 修正可能残留的 root 属主：上次若在 write 与 chown 之间被中断，
        # .zshrc 会以 root 属主留下，且因含标识而永远跳过覆盖。
    else:
        if os.path.exists(rc):
            bak = "%s.bak.%d" % (rc, int(time.time()))
            shutil.copy2(rc, bak)
            warn("已备份原 .zshrc")
            chown_r(bak, t)
        with open(rc, "w") as f:
            f.write(build_zsh_config(st))
    chown_r(rc, t)

    if not run_ok(["chsh", "-s", "/bin/zsh", t]):
        warn("%s 切换默认 shell 为 zsh 失败" % t)
        failures.append("%s 切换 zsh 失败，请手动执行: chsh -s /bin/zsh %s" % (t, t))

    if st.get("prompt") == "p10k":
        reboot.append("首次登录 zsh 会触发 p10k 个性化向导，按提示选择即可")
    ok("Zsh 配置完成")


def ensure_zsh_in_shells():
    zsh_path = shutil.which("zsh") or "/bin/zsh"
    shells = "/etc/shells"
    if os.path.exists(shells):
        content = open(shells).read()
        if zsh_path not in content.splitlines():
            with open(shells, "a") as f:
                f.write(zsh_path + "\n")


def run_fonts(st, reboot, failures):
    """提示符的字体依赖:Nerd 图标 + 中文 + emoji,自动安装(非菜单项)。"""
    info("安装字体 (Nerd/中文/Emoji，提示符依赖) …")
    if not pacman_S(*FONT_PKGS):
        warn("字体安装失败，提示符图标或中文可能显示异常")
        failures.append("字体安装失败，请手动执行: pacman -S %s" % " ".join(FONT_PKGS))
        return
    if is_wsl():
        reboot.append("WSL: 请在 Windows Terminal → 配置文件 → 外观 → 字体 选择 MesloLGS NF")
    ok("字体安装完成")


def run_nvim(st, reboot, failures):
    t = st["target_user"]
    home = user_home(t)
    info("配置 NeoVim LazyVim (目标: %s , 家目录: %s) …" % (t, home))

    info("安装 LazyVim 前置依赖 …")
    if not pacman_S(*NVIM_DEPS):
        warn("部分 LazyVim 依赖安装失败，首次启动可能报缺工具")
        failures.append("LazyVim 依赖安装失败 (%s)，请手动安装" % " ".join(NVIM_DEPS))

    nvim_dir = os.path.join(home, ".config", "nvim")
    dirs = [os.path.join(home, ".config"), os.path.join(home, ".local"),
            os.path.join(home, ".local", "share"), os.path.join(home, ".local", "state"),
            os.path.join(home, ".cache")]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        chown_r(d, t)

    if os.path.isfile(os.path.join(nvim_dir, "init.lua")) and \
       os.path.isdir(os.path.join(nvim_dir, "lua")):
        info("已检测到 NeoVim 配置，跳过克隆（可安全重跑）")
        chown_r(nvim_dir, t)
        ok("NeoVim LazyVim 配置已存在，未覆盖")
        return

    ts = int(time.time())
    for d in [nvim_dir, os.path.join(home, ".local", "share", "nvim"),
              os.path.join(home, ".local", "state", "nvim"),
              os.path.join(home, ".cache", "nvim")]:
        if os.path.isdir(d):
            bak = "%s.bak.%d" % (d, ts)
            shutil.move(d, bak)
            # shutil.move 跨文件系统会递归 copy2，属主全部变成 root，
            # 必须显式修正，否则用户家目录残留 root 属主的备份目录。
            chown_r(bak, t)
            warn("已备份不完整目录: %s -> %s" % (d, bak))

    if bash_as(t, "git clone --depth=1 https://github.com/LazyVim/starter '%s'" % nvim_dir).returncode != 0:
        warn("以 %s 克隆失败，改用当前用户克隆到 %s" % (t, nvim_dir))
        if subprocess.run(["git", "clone", "--depth=1",
                           "https://github.com/LazyVim/starter", nvim_dir]).returncode != 0:
            failures.append("NeoVim LazyVim 克隆失败，请手动执行: git clone https://github.com/LazyVim/starter %s" % nvim_dir)
            return
    subprocess.run(["rm", "-rf", os.path.join(nvim_dir, ".git")])
    chown_r(nvim_dir, t)

    reboot.append("NeoVim: 首次启动会自动下载 LazyVim 插件，需保持网络畅通")
    ok("NeoVim LazyVim 配置完成")


def run_wsl_systemd(st, reboot, failures):
    if not is_wsl():
        return
    info("写入 /etc/wsl.conf [boot] systemd=true")
    wsl_conf_set("boot", "systemd", "true")
    reboot.append("WSL systemd 已写入 /etc/wsl.conf，wsl --shutdown 后重开自动生效")
    ok("WSL systemd 已写入")


def apply_wsl_default(st, reboot, failures):
    if not is_wsl() or not st.get("_pending_wsl_default"):
        return
    wsl_conf_set("user", "default", st["_pending_wsl_default"])
    reboot.append("WSL 默认登录用户已设为 %s，wsl --shutdown 后重开自动生效" % st["_pending_wsl_default"])


# ---------------------------------------------------------------------------
#  输出 (文本模式, 执行阶段用)
# ---------------------------------------------------------------------------

def info(*a):
    print("\033[0;34m[INFO]\033[0m  ", *a)


def ok(*a):
    print("\033[0;32m[OK]\033[0m   ", *a)


def warn(*a):
    print("\033[1;33m[WARN]\033[0m ", *a)


def err(*a):
    print("\033[0;31m[ERR]\033[0m  ", *a)


# ---------------------------------------------------------------------------
#  curses 菜单
# ---------------------------------------------------------------------------

RADIO_SEL = 0

def read_key(win):
    c = win.getch()
    if c == ord("q") or c == ord("Q"):
        return "q"
    if c == 27:
        return "esc"
    if c in (10, 13, curses.KEY_ENTER):
        return "enter"
    if c == ord(" "):
        return "space"
    if c in (ord("a"), ord("A")):
        return "a"
    if c == curses.KEY_UP:
        return "up"
    if c == curses.KEY_DOWN:
        return "down"
    if c == curses.KEY_LEFT:
        return "left"
    if c == curses.KEY_RIGHT:
        return "right"
    return "other"


def radio_select(win, title, options, current):
    """单选子菜单；空格返回选中索引，esc/q 返回 None。"""
    n = len(options)
    cur = max(0, min(n - 1, current)) if n else 0
    while True:
        win.clear()
        try:
            win.addstr(0, 0, "==== %s （方向键 + 空格确认，esc/q 返回） ====" % title,
                       curses.color_pair(3))
        except curses.error:
            pass
        for i, opt in enumerate(options):
            y = 2 + i
            if i == cur:
                try:
                    win.addstr(y, 0, "  > %s" % opt, curses.A_REVERSE | curses.color_pair(3))
                except curses.error:
                    pass
            else:
                try:
                    win.addstr(y, 0, "    %s" % opt)
                except curses.error:
                    pass
        win.refresh()
        k = read_key(win)
        if k == "up":
            cur = max(0, cur - 1)
        elif k == "down":
            cur = min(n - 1, cur + 1)
        elif k == "space":
            return cur
        elif k in ("esc", "q"):
            return None


def check_select(win, title, entries):
    """多选子菜单：entries 为 [显示文本, 是否选中] 的可变列表，原地修改。

    空格 勾选/取消；a 全选/全不选；esc/q 返回（保留已作的修改）。
    """
    n = len(entries)
    cur = 0
    while True:
        win.clear()
        try:
            win.addstr(0, 0, "==== %s（空格 勾选/取消 · a 全选/全不选 · esc 返回） ====" % title,
                       curses.color_pair(3))
        except curses.error:
            pass
        for i, (text, sel) in enumerate(entries):
            mark = "[*]" if sel else "[ ]"
            line = "  > %s %s" % (mark, text) if i == cur else "    %s %s" % (mark, text)
            try:
                if i == cur:
                    win.addstr(2 + i, 0, line, curses.A_REVERSE | curses.color_pair(3))
                else:
                    win.addstr(2 + i, 0, line)
            except curses.error:
                pass
        win.refresh()
        k = read_key(win)
        if k == "up":
            cur = max(0, cur - 1)
        elif k == "down":
            cur = min(n - 1, cur + 1)
        elif k in ("space", "enter"):
            entries[cur][1] = not entries[cur][1]
        elif k == "a":
            all_on = all(e[1] for e in entries)
            for e in entries:
                e[1] = not all_on
        elif k in ("esc", "q"):
            return


def build_rows(st):
    """构建主菜单行列表: [(text, kind, key, locked, indent)]；header 为分组标题不可选中"""
    rows = []
    mark_on = "[*]"
    mark_off = "[ ]"

    def header(text):
        rows.append((text, "header", "", False, 0))

    def toggle_row(label, key, indent=0):
        multi = is_multi_pkg(key)
        if multi:
            total = len(menu_pkgs(key))
            sel = len(selected_pkgs(st, key)) if st.get(key) else 0
            label = "%s (%d/%d)" % (label, sel, total)
        if st["disabled"].get(key):
            rows.append(("  " * indent + "[-] %s (%s)" % (label, st["disabled"][key]),
                         "toggle", key, True, indent))
        elif st["locked"].get(key):
            rows.append(("  " * indent + "[*] %s (已配置)" % label, "toggle", key, True, indent))
        else:
            m = mark_on if st[key] else mark_off
            suffix = " ▶" if multi else ""
            rows.append(("  " * indent + "%s %s%s" % (m, label, suffix),
                         "toggle", key, False, indent))

    def dmirror_row():
        # Docker 镜像源:空格进入多选,子选择决定开关(全不选=停用)
        locked = bool(st["locked"].get("docker_mirror"))
        if locked:
            rows.append(("  Docker 镜像源: 已配置 ▶", "submenu_dmirror", "docker_mirror", True, 1))
        elif st["docker_mirror"]:
            n = len(st.get("docker_mirrors") or [])
            rows.append(("  [*] Docker 镜像源: 已选 %d 个 ▶" % n,
                         "submenu_dmirror", "docker_mirror", False, 1))
        else:
            rows.append(("  [ ] Docker 镜像源 ▶", "submenu_dmirror", "docker_mirror", False, 1))

    # ---- 用户 ----
    if is_wsl() or os.geteuid() == 0:
        if st["create_user"]:
            label = "目标用户: 创建新用户 %s" % (st["new_username"] or "<未命名>")
        else:
            label = "目标用户: 配置已有用户 %s" % (st["config_user"] or "root")
        rows.append((label + " ▶", "submenu_user", "user", False, 0))
        if st["create_user"] and is_wsl():
            if st["wsl_default"]:
                rows.append(("  [*] 设为 WSL 默认登录", "toggle", "wsl_default", False, 1))
            else:
                rows.append(("  [ ] 设为 WSL 默认登录", "toggle", "wsl_default", False, 1))

    # ---- 系统基础 ----
    header("系统基础")
    rows.append(("镜像源: %s ▶" % MIRROR_LABEL[st["mirror"]], "submenu_mirror", "mirror", False, 0))
    toggle_row("Locale", "locale")
    toggle_row("时区", "timezone")
    toggle_row("基础软件包", "base")
    toggle_row("AUR 助手", "aur")
    toggle_row("CPU 微码", "microcode")

    # ---- 系统服务 ----
    header("系统服务")
    for key in ("network", "sshd", "chrony", "cronie", "ufw"):
        toggle_row(PACKAGE_ITEMS[key][0], key)

    # ---- Shell 与美化 ----
    header("Shell 与美化")
    toggle_row("Zsh (设为默认 Shell)", "zsh")
    if st["zsh"]:
        toggle_row("Zsh 插件", "zsh_plugins", 1)
    if st["locked"].get("prompt"):
        rows.append(("终端提示符: %s (已配置)" % PROMPT_LABEL.get(st.get("prompt"), "未配置"),
                     "submenu_prompt", "prompt", True, 0))
    else:
        rows.append(("终端提示符: %s ▶" % PROMPT_LABEL.get(st.get("prompt"), "未配置"),
                     "submenu_prompt", "prompt", False, 0))
    # 字体不再单列菜单项:选了任一提示符后作为依赖自动安装(见 run_fonts)

    # ---- 开发工具 ----（语言在前，工具在后）
    header("开发工具")
    for key in ("python", "lua", "php", "ruby", "java", "node",
                "rustup", "go", "cpp", "gittools"):
        toggle_row(PACKAGE_ITEMS[key][0], key)

    # ---- CLI 增强 ----
    header("CLI 增强")
    toggle_row("终端编辑器", "editor")
    # LazyVim 配置只在终端编辑器组勾选且选中了 neovim 时才有意义
    if st.get("editor") and "neovim" in selected_pkgs(st, "editor"):
        toggle_row("LazyVim (NeoVim 配置)", "nvim", 1)
    for key in ("cli", "file", "sysinfo", "json", "netdiag"):
        toggle_row(PACKAGE_ITEMS[key][0], key)

    # ---- 容器 ----
    header("容器")
    toggle_row("Docker", "docker")
    if st["docker"]:
        dmirror_row()
    toggle_row(PACKAGE_ITEMS["container"][0], "container")

    # ---- WSL ----
    if is_wsl():
        header("WSL")
        toggle_row("WSL systemd", "wsl_systemd")

    rows.append(("", "sep", "", False, 0))
    rows.append(("  [ 执行 ]", "action", "run", False, 0))
    rows.append(("  [ 退出 ]", "action", "quit", False, 0))
    return rows


def render_main(win, rows, cur, st):
    win.clear()
    try:
        height, width = win.getmaxyx()
    except curses.error:
        height, width = 24, 80
    try:
        win.addstr(0, 0, "========================================", curses.color_pair(3))
        win.addstr(1, 0, "Arch Linux 初始化配置", curses.A_BOLD | curses.color_pair(3))
        win.addstr(2, 0, "========================================", curses.color_pair(3))
    except curses.error:
        pass
    # 内容区: y=4 .. height-5（底部留给详情栏两行 + 提示一行）
    content_top = 4
    DETAIL_LINES = 2 if height >= 12 else 0   # 窗口太矮就不画详情栏，避免压住内容
    vis = max(1, height - 6 - DETAIL_LINES)
    top = max(0, min(cur - vis // 2, len(rows) - vis))
    y = content_top
    for i in range(top, min(top + vis, len(rows))):
        text, kind, key, locked, indent = rows[i]
        if kind == "sep":
            y += 1
            continue
        if kind == "header":
            try:
                win.addstr(y, 0, "—— %s" % text, curses.A_BOLD | curses.color_pair(3))
            except curses.error:
                pass
        elif i == cur:
            try:
                win.addstr(y, 0, "> %s" % text, curses.A_REVERSE | curses.color_pair(3))
            except curses.error:
                pass
        else:
            attr = curses.A_DIM if locked else curses.A_NORMAL
            try:
                win.addstr(y, 0, "  %s" % text, attr)
            except curses.error:
                pass
        y += 1
    # 底部详情栏：当前高亮项到底装哪些包 / 改哪些文件
    hint = ""
    if rows:
        text, kind, key, locked, indent = rows[cur]
        if kind in ("submenu_user", "submenu_mirror"):
            hint = "空格: 进入选择"
        elif kind == "submenu_prompt":
            hint = "已配置（如需更换请手动调整）" if locked else "空格: 选择提示符"
        elif kind == "submenu_dmirror":
            if locked:
                hint = "已配置（重跑时将合并写入）"
            else:
                hint = "空格: 选择镜像源（全不选=停用）"
        elif kind == "toggle":
            if st["disabled"].get(key):
                hint = "当前环境不支持，无法选择"
            elif locked:
                hint = "已配置，空格无效"
            elif is_multi_pkg(key):
                hint = "空格: 按包选择（全不选=取消整组）"
            else:
                hint = "空格: 勾选/取消"
        elif kind == "action":
            hint = "空格: 执行/退出"
        detail = item_detail(key, st)
        if st["disabled"].get(key):
            detail = "不支持: %s（跳过，不会执行）" % st["disabled"][key]
        for j, seg in enumerate(wrap_disp(detail, max(4, width - 1), DETAIL_LINES)):
            try:
                win.addstr(height - 1 - DETAIL_LINES + j, 0, seg, curses.color_pair(4))
            except curses.error:
                pass
    line = "↑↓移动 · 空格勾选/进入/选包 · q退出"
    if hint:
        line += "   |   " + hint
    try:
        win.addstr(height - 1, 0, trunc_disp(line, max(0, width - 1)), curses.color_pair(2))
    except curses.error:
        pass
    win.refresh()


def user_menu(win, st):
    options = ["创建新用户"] + configurable_users()
    cur = 0 if st["create_user"] else 1
    sel = radio_select(win, "目标用户", options, cur)
    if sel is None:
        return
    if sel == 0:
        # 创建新用户
        st["create_user"] = True
        st["config_user"] = "root"
        win.clear()
        win.refresh()
        win.addstr(0, 0, "请输入新用户名: ")
        curses.echo()
        curses.nocbreak()
        win.nodelay(False)
        curses.curs_set(1)
        name = win.getstr(0, 16, 32).decode(errors="replace").strip()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        if not valid_username(name):
            st["create_user"] = False
            win.addstr(2, 0, "用户名非法(小写字母/下划线开头，仅含 a-z 0-9 _ -，最长32)")
            win.getch()
            return
        if user_exists(name):
            if is_configurable(name):
                st["create_user"] = False
                st["config_user"] = name
                return
            else:
                st["create_user"] = False
                return
        st["new_username"] = name
    else:
        st["create_user"] = False
        st["config_user"] = options[sel]
    detect(st)


def mirror_menu(win, st):
    keys = ["official", "tuna", "ustc", "aliyun", "tencent", "huawei", "reflector"]
    title = "选择镜像源"
    if is_wsl():
        # reflector 在 WSL 下不执行（run_reflector 直接跳过），不列为候选
        keys.remove("reflector")
        title = "选择镜像源（WSL 不支持 reflector，已隐藏）"
    if st["mirror"] in keys:
        cur = keys.index(st["mirror"])
    else:
        cur = 0
    sel = radio_select(win, title, [MIRROR_LABEL[k] for k in keys], cur)
    if sel is not None:
        st["mirror"] = keys[sel]


def pkg_menu(win, st, key):
    """按包选择子菜单：空格进入，子选择决定整组勾选状态（全不选=未勾选）。

    未勾选的组进入时默认全不选，由用户按需勾选——与全局"默认未选中"一致。
    覆盖 PACKAGE_ITEMS 与 base/fonts/zsh_plugins 等特殊组。
    """
    pkgs = menu_pkgs(key)
    label = menu_label(key)
    default_on = st.get(key) is True
    selmap = st.setdefault("pkgsel", {}).setdefault(key, {p: default_on for p in pkgs})
    w = max(disp_width(p) for p in pkgs)
    entries = []
    for p in pkgs:
        desc = PKG_DESC.get(p, "")
        entries.append([(pad_disp(p, w) + "  " + desc).rstrip(), selmap.get(p, default_on)])
    check_select(win, "%s · 按包选择" % label, entries)
    for p, e in zip(pkgs, entries):
        selmap[p] = e[1]
    st[key] = any(selmap.values())


def prompt_menu(win, st):
    """终端提示符单选子菜单;p10k 是 zsh 专属主题,选中时自动勾选 Zsh。"""
    opts = [
        ("p10k",     "Powerlevel10k  zsh 专属主题，功能最全（自动勾选 Zsh，建议同时勾字体）"),
        ("starship", "starship       跨 Shell 提示符，轻量易配，bash 也可用"),
        ("",         "不配置"),
    ]
    cur = {"p10k": 0, "starship": 1, "": 2}[st.get("prompt", "") or ""]
    sel = radio_select(win, "终端提示符", [o[1] for o in opts], cur)
    if sel is None:
        return
    st["prompt"] = opts[sel][0]
    # p10k 必须依附 zsh;starship 独立可用
    if st["prompt"] == "p10k":
        st["zsh"] = True
        cascade(st, "zsh")      # 与手动勾选 Zsh 一致:插件默认全选


def docker_mirror_menu(win, st):
    """Docker 镜像源多选子菜单：空格进入，子选择决定该项开关（全不选=停用）。"""
    sel = set(st.get("docker_mirrors") or [])
    wl = max(disp_width(label) for _k, label, _u, _n in DOCKER_MIRRORS)
    wu = max(disp_width(url) for _k, _l, url, _n in DOCKER_MIRRORS)
    entries = []
    for k, label, url, note in DOCKER_MIRRORS:
        text = pad_disp(label, wl) + "  " + pad_disp(url, wu) + "  " + note
        entries.append([text.rstrip(), k in sel])
    check_select(win, "Docker 镜像源 · 多选", entries)
    st["docker_mirrors"] = [m[0] for m, e in zip(DOCKER_MIRRORS, entries) if e[1]]
    st["docker_mirror"] = bool(st["docker_mirrors"])


def cascade(st, key):
    """某项状态变化后的级联:取消父项时收掉依附它的子项,开启时给出合理默认。"""
    if key == "zsh":
        if st["zsh"]:
            # 勾选 Zsh 默认带上全部插件(曾显式全不选过则重置为全选)
            if not st["zsh_plugins"]:
                st["zsh_plugins"] = True
                selmap = st.get("pkgsel", {}).get("zsh_plugins")
                if selmap is not None and not any(selmap.values()):
                    st["pkgsel"]["zsh_plugins"] = {p: True for p in menu_pkgs("zsh_plugins")}
        else:
            st["zsh_plugins"] = False
            if st.get("prompt") == "p10k":     # p10k 无法脱离 zsh;starship 独立保留
                st["prompt"] = ""
    if key == "docker" and not st["docker"]:
        st["docker_mirror"] = False
    if key == "editor" and (not st.get("editor")
                            or "neovim" not in selected_pkgs(st, "editor")):
        st["nvim"] = False                 # LazyVim 配置依附 neovim


def main_menu(win, st):
    curses.start_color()
    try:
        curses.use_default_colors()
    except curses.error:
        pass
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)   # 详情栏
    curses.noecho()
    curses.cbreak()
    win.keypad(True)
    curses.curs_set(0)
    rows = build_rows(st)
    cur = 0
    n = len(rows)

    def refresh():
        return build_rows(st)

    def try_run():
        """点击 [执行]：新用户未命名时先弹输入，返回 False 需要刷新菜单。"""
        if st["create_user"] and not st["new_username"]:
            win.addstr(0, 0, "请先设置新用户用户名", curses.color_pair(2))
            win.refresh()
            win.getch()
            user_menu(win, st)
            return False
        return True

    while True:
        render_main(win, rows, cur, st)
        k = read_key(win)
        if k == "q" or k == "esc":
            return None
        elif k == "up":
            cur = (cur - 1) % n
            while rows[cur][1] in ("sep", "header"):
                cur = (cur - 1) % n
        elif k == "down":
            cur = (cur + 1) % n
            while rows[cur][1] in ("sep", "header"):
                cur = (cur + 1) % n
        elif k in ("space", "enter"):
            text, kind, key, locked, indent = rows[cur]
            if kind == "toggle" and not locked:
                if is_multi_pkg(key):
                    # 多包组：空格进入按包选择，整组勾选状态由子选择决定
                    # (未勾选组的 selected_pkgs 默认全选,须先看组开关再判断"曾选中")
                    had_neovim = (key == "editor" and st.get("editor")
                                  and "neovim" in selected_pkgs(st, "editor"))
                    pkg_menu(win, st, key)
                    # 新选中 neovim 时默认带上 LazyVim 配置(可再手动取消)
                    if key == "editor" and not had_neovim \
                            and "neovim" in selected_pkgs(st, "editor"):
                        st["nvim"] = True
                else:
                    st[key] = not st[key]
                cascade(st, key)
                rows = refresh(); n = len(rows)
            elif kind == "submenu_dmirror" and not locked:
                docker_mirror_menu(win, st)
                rows = refresh(); n = len(rows)
            elif kind == "submenu_prompt" and not locked:
                prompt_menu(win, st)
                rows = refresh(); n = len(rows)
            elif kind == "submenu_user":
                user_menu(win, st)
                rows = refresh(); n = len(rows)
            elif kind == "submenu_mirror":
                mirror_menu(win, st)
                rows = refresh(); n = len(rows)
            elif kind == "action":
                if key == "run":
                    if try_run():
                        return st
                    rows = refresh(); n = len(rows)
                else:
                    return None


def resolve_target(st):
    if st["create_user"]:
        return st["new_username"]
    return st["config_user"] or "root"


# ---------------------------------------------------------------------------
#  主流程
# ---------------------------------------------------------------------------

def sweep_owner(st):
    """最终兜底：把目标用户家目录中脚本触碰过的路径属主修正为该用户。

    各步骤内部已有 chown 修正，但任一步骤在"写入"与"修正"之间被打断，
    就会残留 root 属主文件，用户此后改不了自己的配置（.zshrc/.p10k.zsh
    等）。无论成败，execute 退出前都执行一次兜底清扫。
    """
    t = st.get("target_user", "root")
    if t == "root" or not user_exists(t):
        return
    home = user_home(t)
    uid = pwd.getpwnam(t).pw_uid
    try:
        if os.stat(home).st_uid != uid:
            # 家目录本身属主不对（如手动建用户后 root 复制过文件），整树修正
            chown_r(home, t)
    except OSError:
        pass
    # 脚本写入/创建的具体路径（chown_r 对不存在的路径是 no-op）
    for rel in (".zsh", ".zshrc", ".zsh_history", ".p10k.zsh",
                ".config", ".local", ".cache"):
        chown_r(os.path.join(home, rel), t)
    ok("已确认 %s 家目录属主为 %s" % (home, t))


# ---------------------------------------------------------------------------
#  主流程
# ---------------------------------------------------------------------------

def execute(st):
    reboot, failures = [], []
    target = resolve_target(st)
    st["target_user"] = target
    info("开始执行 (目标用户: %s, 家目录: %s)" % (target, user_home(target)))

    try:
        try:
            if st["create_user"]:
                run_create_user(st, reboot, failures)
            run_mirror(st, reboot, failures)
            if st["timezone"]:
                run_timezone(st, reboot, failures)
            if st["locale"]:
                run_locale(st, reboot, failures)
            if st["base"]:
                run_base(st, reboot, failures)
            # sudo/wheel 必须等 base 装好 sudo 之后（全新系统 /etc/sudoers 不存在）
            ensure_user_sudo(st, failures)
            if st["aur"]:
                run_pkgs(st, "aur", reboot, failures)
            if st["microcode"]:
                run_microcode(st, reboot, failures)
            # 系统服务
            for key in ("network", "sshd", "chrony", "cronie"):
                if st[key]:
                    run_service(st, key, reboot, failures)
            if st["ufw"]:
                run_ufw(st, reboot, failures)
            # Shell 与美化
            if st["zsh"]:
                run_zsh(st, reboot, failures)
            if st.get("prompt") == "starship" and not st["zsh"]:
                info("安装 starship（未选 Zsh：仅安装包，bash 用户自行在 ~/.bashrc 添加 eval）…")
                if not pacman_S("starship"):
                    failures.append("starship 安装失败，请手动执行: pacman -S starship")
            if st.get("prompt"):
                run_fonts(st, reboot, failures)   # 字体作为提示符依赖自动安装
            # 开发工具
            for key in ("python", "lua", "php", "ruby", "java", "node",
                        "rustup", "go", "cpp", "gittools"):
                if st[key]:
                    run_pkgs(st, key, reboot, failures)
            # CLI 增强
            for key in ("editor", "cli", "file", "sysinfo", "json", "netdiag"):
                if st[key]:
                    run_pkgs(st, key, reboot, failures)
            if st["nvim"]:
                run_nvim(st, reboot, failures)
            # 容器
            if st["docker"]:
                run_docker(st, reboot, failures)
            if st["docker_mirror"]:
                run_docker_mirror(st, reboot, failures)
            if st["container"]:
                run_pkgs(st, "container", reboot, failures)
            # WSL
            if st["wsl_systemd"]:
                run_wsl_systemd(st, reboot, failures)
            apply_wsl_default(st, reboot, failures)
        except KeyboardInterrupt:
            print()
            err("被用户中断")
            return
    finally:
        sweep_owner(st)

    print("\n\033[1;36m========================================\033[0m")
    print("\033[1;36m初始化配置全部完成！\033[0m")
    print("\033[1;36m========================================\033[0m")
    print("目标用户: %s" % target)
    print("家目录  : %s" % user_home(target))
    if target == "root" and not st["create_user"]:
        print("本次未创建普通用户，用户级配置已写入 root (/root)")

    if failures:
        print("\n\033[1;31m执行失败项汇总（脚本已继续，请复查后手动补装/修复）\033[0m")
        for i, f in enumerate(failures, 1):
            print("\033[0;31m%d. %s\033[0m" % (i, f))
    if reboot:
        print("\n\033[0;36m重启后自动生效（无需操作，仅供知晓）\033[0m")
        for i, f in enumerate(reboot, 1):
            print("\033[0;36m%d. %s\033[0m" % (i, f))
    print()
    if is_wsl():
        print("\033[1;36m建议在 Windows 执行 wsl --shutdown 后重新打开终端，使全部配置生效\033[0m")
    else:
        print("\033[1;36m建议重启系统（或注销重新登录），使全部配置生效\033[0m")


def default_state():
    return {
        "create_user": False,
        "new_username": "",
        "config_user": "root",
        "mirror": "official",
        "base": True,                # 基础软件包默认全选
        "aur": False,
        "docker": False,
        "docker_mirror": False,
        "docker_mirrors": [],
        "dmirror_extra": [],
        "pkgsel": {},
        "locale": True,             # 幂等无害、中文环境必需,默认勾选
        "timezone": True,           # 中国环境零交互自动设 Asia/Shanghai
        "microcode": False,
        "zsh": False,
        "zsh_plugins": False,
        "prompt": "",
        "nvim": False,
        "wsl_systemd": True,        # docker/sshd/cronie 等服务的前提,默认勾选
        "wsl_default": False,
        "network": False,
        "sshd": False,
        "chrony": False,
        "cronie": False,
        "ufw": False,
        "python": False,
        "lua": False,
        "php": False,
        "ruby": False,
        "java": False,
        "node": False,
        "rustup": False,
        "go": False,
        "cpp": False,
        "gittools": False,
        "cli": False,
        "editor": False,
        "file": False,
        "sysinfo": False,
        "json": False,
        "netdiag": False,
        "container": False,
        "locked": {},
        "disabled": {},
        "target_user": "root",
        "_pending_wsl_default": "",
    }


def main():
    ensure_root(sys.argv)
    try:
        st = default_state()
        if not is_wsl():
            st["wsl_systemd"] = False

        if not os.path.exists("/etc/arch-release"):
            warn("未检测到 /etc/arch-release，当前可能不是 Arch Linux")
            ans = input("非 Arch 环境，是否继续执行? [y/N]: ").strip().lower()
            if ans not in ("y", "yes"):
                print("已退出")
                return

        st["target_user"] = "root"
        detect(st)

        result = curses.wrapper(lambda w: main_menu(w, st))
        if result is None:
            print("已退出")
            return
        execute(st)
    except KeyboardInterrupt:
        print()
        err("已取消")
        sys.exit(130)


if __name__ == "__main__":
    main()
