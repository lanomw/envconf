#!/bin/sh
# -*- coding: utf-8 -*-
''':' #
# ===========================================================================
# wsl安装arch系统到指定路径
#   下载系统: https://fastly.mirror.pkgbuild.com/wsl/latest
#   安装到指定位置:: wsl --install --from-file C:\Users\atk\Downloads\archlinux-2026.08.01.174141.wsl --location E:\WSL\ArchLinux
#   注销系统: wsl --unregister archlinux
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
  空格  勾选 / 取消 (已存在的项会被锁定, 空格无效)
  空格  进入子菜单 (目标用户 / 镜像源) 或 执行 / 退出
  q    退出

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
import time
import pwd
import grp
import stat
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


def cn_url(m):
    return CN_URL[m]


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


def enable_wheel_sudo(now, failures):
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

BASE_PKGS = ["sudo", "git", "base-devel", "make", "cmake", "vim", "neovim",
             "tree", "curl", "wget", "openssh", "man-db", "man-pages",
             "which", "less", "unzip"]

FONT_PKGS = ["ttf-meslo-nerd", "noto-fonts-cjk", "noto-fonts-emoji"]

NVIM_DEPS = ["ripgrep", "fd", "unzip", "lazygit", "fzf", "nodejs", "npm",
             "gcc", "make"]

# 可勾选软件清单: key -> (标签, 包元组, 服务单元或 None)
#   纯包项  -> run_pkgs；带服务单元 -> run_service（非 WSL 时 systemctl enable --now）
PACKAGE_ITEMS = {
    # ---- 系统服务 ----
    "network":  ("网络工具 (NetworkManager)",       ("networkmanager",),      "NetworkManager"),
    "sshd":     ("SSH 服务端",                      ("openssh",),             "sshd"),
    "chrony":   ("NTP 时间同步",                    ("chrony",),              "chronyd"),
    "cronie":   ("定时任务",                        ("cronie",),              "cronie"),
    "ufw":      ("防火墙 (ufw)",                    ("ufw",),                 "ufw"),
    # ---- 开发工具 ----
    "python":   ("开发语言 (python)",               ("python",),              None),
    "rustup":   ("Rust (rustup)",                    ("rustup",),              None),
    "go":       ("Go",                              ("go",),                  None),
    "java":     ("Java (jdk-openjdk)",              ("jdk-openjdk",),         None),
    "node":     ("Node 系 (bun/deno)",              ("bun", "deno"),          None),
    "lua":      ("脚本语言 (lua)",                  ("lua",),                 None),
    "php":      ("脚本语言 (php)",                  ("php",),                 None),
    "ruby":     ("脚本语言 (ruby)",                 ("ruby",),                None),
    "cpp":      ("C/C++ 工具链 (clang/valgrind)",   ("clang", "valgrind"),    None),
    "git":      ("git 增强 (git-delta)",            ("git-delta",),           None),
    "lazygit":  ("lazygit",                         ("lazygit",),             None),
    "paru":     ("AUR 助手 (paru)",                 ("paru",),                None),
    # ---- CLI 增强 ----
    "cli":      ("终端工具 (tmux/btop/eza/bat/zoxide/fd/ripgrep)",
                 ("tmux", "btop", "eza", "bat", "zoxide", "fd", "ripgrep"), None),
    "editor":   ("终端编辑器 (helix/micro)",        ("helix", "micro"),       None),
    "file":     ("文件管理 (yazi)",                 ("yazi",),                None),
    "sysinfo":  ("系统信息+磁盘 (fastfetch/duf/ncdu)",
                 ("fastfetch", "duf", "ncdu"), None),
    "json":     ("JSON 工具 (jq/yq)",               ("jq", "yq"),             None),
    "netdiag":  ("网络诊断 (nmap/ncat/mosh/httpie/iperf3)",
                 ("nmap", "ncat", "mosh", "httpie", "iperf3"), None),
    "starship": ("终端提示符 (starship)",           ("starship",),            None),
    "man":      ("速查手册 (tldr/cheat)",           ("tldr", "cheat"),        None),
    "nav":      ("目录导航 (broot/direnv)",         ("broot", "direnv"),      None),
    "gitx":     ("git 扩展 (git-lfs/git-open)",     ("git-lfs", "git-open"),  None),
    "plocate":  ("文件索引 (plocate)",              ("plocate",),             None),
    "netadd":   ("网络补充 (mtr/whois)",            ("mtr", "whois"),         None),
    # ---- 容器 ----
    "container":("Podman/K8s (podman/kubectl/k9s/helm)",
                 ("podman", "kubectl", "k9s", "helm"), None),
}

# 非装包项的说明: key -> 这一项到底改了什么（菜单详情栏用）
ACTION_DETAIL = {
    "user":          "选择配置目标: 创建新用户 / 指定已有用户 / root",
    "mirror":        "改写 /etc/pacman.d/mirrorlist（所选源排第一，其余回退）",
    "locale":        "启用 en_US.UTF-8 + zh_CN.UTF-8，写入 /etc/locale.conf",
    "timezone":      "交互输入时区（默认 Asia/Shanghai），符号链接 /etc/localtime",
    "docker_mirror": "写入 /etc/docker/daemon.json 的 registry-mirrors 多源回退",
    "wsl_systemd":   "在 /etc/wsl.conf 写入 [boot] systemd=true",
    "wsl_default":   "在 /etc/wsl.conf 写入 [user] default=<新用户>",
}


def item_detail(key, st):
    """菜单详情栏：这一项到底会装哪些包 / 改哪些文件。"""
    if key in ACTION_DETAIL:
        return ACTION_DETAIL[key]
    if key in PACKAGE_ITEMS:
        _, pkgs, unit = PACKAGE_ITEMS[key]
        s = "安装: " + " ".join(pkgs)
        if unit:
            s += "  ·  启用服务: " + unit
        return s
    if key == "base":
        pkgs = list(BASE_PKGS)
        if st["zsh"]:
            pkgs += ["zsh", "zsh-completions"]
        return "安装: " + " ".join(pkgs)
    if key == "fonts":
        return "安装: " + " ".join(FONT_PKGS)
    if key == "microcode":
        return "安装: intel-ucode 或 amd-ucode（按 /proc/cpuinfo 自动识别，WSL 跳过）"
    if key == "zsh":
        return ("安装: zsh zsh-completions  ·  克隆插件: "
                + " ".join(n for _, n in ZSH_PLUGINS)
                + "  ·  写入 ~/.zshrc 并 chsh")
    if key == "nvim":
        return ("安装: " + " ".join(NVIM_DEPS)
                + "  ·  克隆 LazyVim/starter 到 ~/.config/nvim（旧配置先备份）")
    if key == "docker":
        return "安装: docker docker-compose docker-buildx  ·  启用服务: docker  ·  目标用户加入 docker 组"
    if key == "aur":
        return "安装: yay（来自 archlinuxcn 仓库）"
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


ZSH_PLUGINS = [
    ("https://github.com/zsh-users/zsh-autosuggestions", "zsh-autosuggestions"),
    ("https://github.com/zsh-users/zsh-syntax-highlighting", "zsh-syntax-highlighting"),
    ("https://github.com/romkatv/powerlevel10k.git", "powerlevel10k"),
]

ZSH_CONFIG = """# ============================
#  Zsh 配置 — 美化版
# ============================
export PATH=$HOME/.local/bin:$PATH

source $HOME/.zsh/powerlevel10k/powerlevel10k.zsh-theme

source $HOME/.zsh/zsh-autosuggestions/zsh-autosuggestions.zsh
source $HOME/.zsh/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

setopt AUTO_CD
setopt CORRECT
setopt NO_BEEP

HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt SHARE_HISTORY
setopt HIST_IGNORE_DUPS
setopt HIST_REDUCE_BLANKS

alias ll='ls -alF --color=auto'
alias la='ls -A --color=auto'
alias l='ls -CF --color=auto'
alias grep='grep --color=auto'
alias ..='cd ..'
alias ...='cd ../..'

autoload -Uz compinit && compinit
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'

if grep -qi "microsoft\\|wsl" /proc/version 2>/dev/null; then
    alias winhome='cd /mnt/c/Users/$([ ! -z "$USER" ] && echo $USER || echo $USERNAME)'
fi

if command -v starship >/dev/null 2>&1; then
    eval "$(starship init zsh)"
fi

if command -v zoxide >/dev/null 2>&1; then
    eval "$(zoxide init zsh)"
fi

[[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh
[[ -f ~/.zsh_env ]] && source ~/.zsh_env
"""

DOCKER_DAEMON = """{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
"""

# ---------------------------------------------------------------------------
#  预检测 (包 + 用户级配置)
# ---------------------------------------------------------------------------

def detect(st, now):
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
    lock("locale", locale_present())
    lock("zsh", user_zsh_present(home))
    lock("fonts", all(pkg_installed(p) for p in FONT_PKGS))
    lock("nvim", user_nvim_present(home))
    lock("aur", pkg_installed("yay") or shutil.which("yay") is not None)
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
        return "美化版" in open(rc).read()
    except OSError:
        return False


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


# ---------------------------------------------------------------------------
#  执行层
# ---------------------------------------------------------------------------

def run_create_user(st, now, reboot, failures):
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
    enable_wheel_sudo(now, failures)
    if is_wsl() and st["wsl_default"]:
        st["_pending_wsl_default"] = u
        info("WSL 默认登录用户将在全部步骤成功后写入，避免中途失败卡在新用户")


def run_mirror(st, now, reboot, failures):
    mirror = st["mirror"]
    if mirror == "official":
        info("已选择官方源，保持现有 mirrorlist 与 pacman.conf 不变")
    elif mirror == "reflector":
        run_reflector(st, now, reboot, failures)
    else:
        info("配置镜像源：%s（所选源优先，其余回退）…" % MIRROR_LABEL[mirror])
        ml = "/etc/pacman.d/mirrorlist"
        if os.path.exists(ml):
            shutil.copy2(ml, "%s.bak.%d" % (ml, int(time.time())))
        content = write_mirrorlist(mirror, arch_url)
        with open(ml, "w") as f:
            f.write(content)

    cn_enabled = False
    if mirror in ("tuna", "ustc", "aliyun", "tencent", "huawei") or st["aur"] or st["paru"]:
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


def run_base(st, now, reboot, failures):
    pkgs = list(BASE_PKGS)
    if st["zsh"]:
        pkgs += ["zsh", "zsh-completions"]
    if not pacman_S(*pkgs):
        failures.append("基础软件包安装失败，请手动执行: pacman -S %s" % " ".join(pkgs))
        warn("基础软件包安装失败，脚本继续（后续依赖可能缺失）")
        return
    ok("基础软件包安装完成")


def service_enabled(unit):
    """systemctl is-enabled 返回 0 表示已启用。WSL 恒 False。"""
    if is_wsl():
        return False
    return run_ok(["systemctl", "is-enabled", unit])


def run_pkgs(st, key, now, reboot, failures):
    """纯包项：安装该 key 的包元组，失败记录。"""
    label, pkgs, _ = PACKAGE_ITEMS[key]
    info("安装 %s …" % label)
    if not pacman_S(*pkgs):
        failures.append("%s 安装失败（部分软件可能不在当前仓库，请手动: pacman -S %s）"
                        % (label, " ".join(pkgs)))
        warn("%s 安装失败，脚本继续" % label)
        return
    ok("%s 已安装" % label)


def run_service(st, key, now, reboot, failures):
    """服务项：装包（如无）→ 非 WSL 时 systemctl enable --now；WSL 跳过并记重启。"""
    label, pkgs, unit = PACKAGE_ITEMS[key]
    info("配置 %s (%s) …" % (label, unit))
    if pkgs and not pacman_S(*pkgs):
        failures.append("%s 包安装失败，请手动: pacman -S %s" % (label, " ".join(pkgs)))
        warn("%s 包安装失败，脚本继续" % label)
        return
    if is_wsl():
        reboot.append("%s 已安装；WSL 下不执行 systemctl，重启 WSL 后由 systemd 管理" % label)
        ok("%s 已安装（WSL：重启后由 systemd 管理）" % label)
        return
    if not run_ok(["systemctl", "enable", "--now", unit]):
        failures.append("%s 服务启动失败，请手动执行: systemctl enable --now %s" % (label, unit))
        warn("%s 服务启动失败" % unit)
        return
    ok("%s 服务已启用并启动 (%s)" % (label, unit))


def run_reflector(st, now, reboot, failures):
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


def run_timezone(st, now, reboot, failures):
    """设置系统时区；原生 Arch 与 WSL 均适用。默认 Asia/Shanghai，可交互输入。"""
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


def run_ufw(st, now, reboot, failures):
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


def run_microcode(st, now, reboot, failures):
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


def run_docker(st, now, reboot, failures):
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
            now.append("%s 已加入 docker 组，需重新登录或执行 'newgrp docker' 后才能免 sudo 使用 docker" % t)
        else:
            failures.append("无法将 %s 加入 docker 组" % t)

    if is_wsl():
        failures.append("WSL 环境未执行 systemctl enable docker（systemd 不可用）")
        now.append("如需在 WSL 使用 docker：安装 Docker Desktop 并启用 WSL 集成，或在 WSL 内手动启动 dockerd")
    else:
        if not run_ok(["systemctl", "enable", "docker"]):
            err("systemctl enable docker 失败")
            failures.append("systemctl enable docker 失败，请手动执行: systemctl enable --now docker")
        else:
            ok("docker 服务已启用")
    ok("Docker 安装配置完成")


def run_docker_mirror(st, now, reboot, failures):
    if not st["docker_mirror"]:
        return
    info("配置 Docker 国内镜像源 …")
    os.makedirs("/etc/docker", exist_ok=True)
    cfg = "/etc/docker/daemon.json"
    if os.path.exists(cfg):
        shutil.copy2(cfg, "%s.bak.%d" % (cfg, int(time.time())))
        warn("已备份原 daemon.json")
    with open(cfg, "w") as f:
        f.write(DOCKER_DAEMON)
    if not is_wsl() and shutil.which("systemctl"):
        if run_ok(["systemctl", "restart", "docker"]):
            ok("docker 服务已重启加载镜像源")
        else:
            failures.append("docker 重启加载镜像源失败，请手动执行: systemctl restart docker")
    else:
        reboot.append("WSL/无 systemd：daemon.json 已写入，启动 dockerd 时自动读取生效（无需手动操作）")
    ok("Docker 镜像源已写入 /etc/docker/daemon.json")


def run_locale(st, now, reboot, failures):
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


def run_zsh(st, now, reboot, failures):
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

    for url, name in ZSH_PLUGINS:
        dest = os.path.join(zsh_dir, name)
        if os.path.isdir(os.path.join(dest, ".git")):
            continue
        if bash_as(t, "git clone --depth=1 '%s' '%s'" % (url, dest)).returncode != 0:
            warn("以 %s 克隆失败，改用当前用户克隆到 %s" % (t, dest))
            if subprocess.run(["git", "clone", "--depth=1", url, dest]).returncode != 0:
                failures.append("zsh 插件 %s 克隆失败，请手动安装" % name)
                warn("zsh 插件 %s 克隆失败" % name)

    chown_r(zsh_dir, t)

    rc = os.path.join(home, ".zshrc")
    if os.path.isfile(rc) and "美化版" in open(rc).read():
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
            f.write(ZSH_CONFIG)
    chown_r(rc, t)

    if not run_ok(["chsh", "-s", "/bin/zsh", t]):
        warn("%s 切换默认 shell 为 zsh 失败" % t)
        failures.append("%s 切换 zsh 失败，请手动执行: chsh -s /bin/zsh %s" % (t, t))

    now.append("Zsh 已配置：注销重新登录或执行 'exec zsh' 加载；首次进入会触发 p10k 个性化向导")
    ok("Zsh 美化配置完成")


def ensure_zsh_in_shells():
    zsh_path = shutil.which("zsh") or "/bin/zsh"
    shells = "/etc/shells"
    if os.path.exists(shells):
        content = open(shells).read()
        if zsh_path not in content.splitlines():
            with open(shells, "a") as f:
                f.write(zsh_path + "\n")


def run_fonts(st, now, reboot, failures):
    info("安装字体 (Meslo Nerd Font + 中文/Emoji) …")
    if not pacman_S(*FONT_PKGS):
        warn("部分字体安装失败，p10k 图标或中文可能显示异常")
        failures.append("字体安装失败 (%s)，请手动执行: pacman -S %s" %
                        (" ".join(FONT_PKGS), " ".join(FONT_PKGS)))
        return
    if is_wsl():
        now.append("WSL:请在 Windows Terminal → 配置文件 → 外观 → 字体 选择 MesloLGS NF")
    ok("字体安装完成")


def run_nvim(st, now, reboot, failures):
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

    now.append("NeoVim: 首次 'nvim' 会自动下载 LazyVim 插件，请保持网络畅通")
    ok("NeoVim LazyVim 配置完成")


def run_aur(st, now, reboot, failures):
    if pkg_installed("yay") or shutil.which("yay"):
        info("yay 已安装，跳过")
        return
    info("安装 yay（来自 archlinuxcn 仓库）…")
    if not pacman_S("yay"):
        failures.append("yay 安装失败：请确认 archlinuxcn 仓库已配置后手动执行: pacman -S yay")
        return
    ok("yay 安装完成")


def run_wsl_systemd(st, now, reboot, failures):
    if not is_wsl():
        return
    info("写入 /etc/wsl.conf [boot] systemd=true")
    wsl_conf_set("boot", "systemd", "true")
    reboot.append("WSL systemd 已写入 /etc/wsl.conf，wsl --shutdown 后重开自动生效")
    ok("WSL systemd 已写入")


def apply_wsl_default(st, now, reboot, failures):
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


def build_rows(st):
    """构建主菜单行列表: [(text, kind, key, locked, indent)]；header 为分组标题不可选中"""
    rows = []
    mark_on = "[*]"
    mark_off = "[ ]"

    def header(text):
        rows.append((text, "header", "", False, 0))

    def toggle_row(label, key, indent=0):
        if st["disabled"].get(key):
            rows.append(("  " * indent + "[-] %s (%s)" % (label, st["disabled"][key]),
                         "toggle", key, True, indent))
        elif st["locked"].get(key):
            rows.append(("  " * indent + "[*] %s (已配置)" % label, "toggle", key, True, indent))
        else:
            m = mark_on if st[key] else mark_off
            rows.append(("  " * indent + "%s %s" % (m, label), "toggle", key, False, indent))

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
    toggle_row("CPU 微码", "microcode")

    # ---- 系统服务 ----
    header("系统服务")
    for key in ("network", "sshd", "chrony", "cronie", "ufw"):
        toggle_row(PACKAGE_ITEMS[key][0], key)

    # ---- 终端美化 ----
    header("终端美化")
    toggle_row("Zsh 美化", "zsh")
    toggle_row("字体 (Nerd/中文)", "fonts")
    toggle_row("终端提示符 (starship)", "starship")

    # ---- 开发工具 ----
    header("开发工具")
    toggle_row("NeoVim (LazyVim)", "nvim")
    for key in ("python", "rustup", "go", "java", "node", "lua", "php", "ruby",
                "cpp", "git", "lazygit", "paru"):
        toggle_row(PACKAGE_ITEMS[key][0], key)
    toggle_row("AUR 助手 (yay)", "aur")

    # ---- CLI 增强 ----
    header("CLI 增强")
    for key in ("cli", "editor", "file", "sysinfo", "json", "netdiag",
                "man", "nav", "gitx", "plocate", "netadd"):
        toggle_row(PACKAGE_ITEMS[key][0], key)

    # ---- 容器 ----
    header("容器")
    toggle_row("Docker", "docker")
    if st["docker"]:
        toggle_row("Docker 镜像源", "docker_mirror", 1)
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
        elif kind == "toggle":
            if st["disabled"].get(key):
                hint = "当前环境不支持，无法选择"
            elif locked:
                hint = "已配置，空格无效"
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
    line = "↑↓移动 · 空格勾选/进入/执行 · q退出"
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
    detect(st, [])


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
        elif k == "space":
            text, kind, key, locked, indent = rows[cur]
            if kind == "toggle" and not locked:
                st[key] = not st[key]
                if key == "docker" and not st["docker"]:
                    st["docker_mirror"] = False
                rows = build_rows(st)
                n = len(rows)
            elif kind == "submenu_user":
                user_menu(win, st)
                rows = build_rows(st)
                n = len(rows)
            elif kind == "submenu_mirror":
                mirror_menu(win, st)
                rows = build_rows(st)
                n = len(rows)
            elif kind == "action":
                if key == "run":
                    if st["create_user"] and not st["new_username"]:
                        win.addstr(0, 0, "请先设置新用户用户名", curses.color_pair(2))
                        win.refresh()
                        win.getch()
                        user_menu(win, st)
                        rows = build_rows(st)
                        n = len(rows)
                    else:
                        return st
                else:
                    return None


def resolve_target(st):
    if st["create_user"]:
        return st["new_username"]
    return st["config_user"] or "root"


# ---------------------------------------------------------------------------
#  主流程
# ---------------------------------------------------------------------------

def execute(st):
    now, reboot, failures = [], [], []
    target = resolve_target(st)
    st["target_user"] = target
    info("开始执行 (目标用户: %s, 家目录: %s)" % (target, user_home(target)))

    try:
        if st["create_user"]:
            run_create_user(st, now, reboot, failures)
        run_mirror(st, now, reboot, failures)
        if st["timezone"]:
            run_timezone(st, now, reboot, failures)
        if st["locale"]:
            run_locale(st, now, reboot, failures)
        if st["base"]:
            run_base(st, now, reboot, failures)
        if st["microcode"]:
            run_microcode(st, now, reboot, failures)
        # 系统服务
        for key in ("network", "sshd", "chrony", "cronie"):
            if st[key]:
                run_service(st, key, now, reboot, failures)
        if st["ufw"]:
            run_ufw(st, now, reboot, failures)
        # 终端美化
        if st["zsh"]:
            run_zsh(st, now, reboot, failures)
        if st["fonts"]:
            run_fonts(st, now, reboot, failures)
        if st["starship"]:
            run_pkgs(st, "starship", now, reboot, failures)
        # 开发工具
        if st["nvim"]:
            run_nvim(st, now, reboot, failures)
        for key in ("python", "rustup", "go", "java", "node", "lua", "php", "ruby",
                    "cpp", "git", "lazygit", "paru"):
            if st[key]:
                run_pkgs(st, key, now, reboot, failures)
        if st["aur"]:
            run_aur(st, now, reboot, failures)
        # CLI 增强
        for key in ("cli", "editor", "file", "sysinfo", "json", "netdiag",
                    "man", "nav", "gitx", "plocate", "netadd"):
            if st[key]:
                run_pkgs(st, key, now, reboot, failures)
        # 容器
        if st["docker"]:
            run_docker(st, now, reboot, failures)
        if st["docker_mirror"]:
            run_docker_mirror(st, now, reboot, failures)
        if st["container"]:
            run_pkgs(st, "container", now, reboot, failures)
        # WSL
        if st["wsl_systemd"]:
            run_wsl_systemd(st, now, reboot, failures)
        apply_wsl_default(st, now, reboot, failures)
    except KeyboardInterrupt:
        print()
        err("被用户中断")
        return

    print("\n\033[1;36m========================================\033[0m")
    print("\033[1;36m初始化配置全部完成！\033[0m")
    print("\033[1;36m========================================\033[0m")
    print("目标用户: %s" % target)
    print("家目录  : %s" % user_home(target))
    if st["create_user"]:
        print("请使用: su - %s   切换到新用户" % target)
    elif target == "root":
        print("本次未创建普通用户，用户级配置已写入 root (/root)")

    if failures:
        print("\n\033[1;31m执行失败项汇总（脚本已继续，请复查后手动补装/修复）\033[0m")
        for i, f in enumerate(failures, 1):
            print("\033[0;31m%d. %s\033[0m" % (i, f))
    if now:
        print("\n\033[1;33m需立即处理（请现在执行）\033[0m")
        for i, f in enumerate(now, 1):
            print("\033[1;33m%d. %s\033[0m" % (i, f))
    if reboot:
        print("\n\033[0;36m重启/重连后自动生效（无需操作，仅供知晓）\033[0m")
        for i, f in enumerate(reboot, 1):
            print("\033[0;36m%d. %s\033[0m" % (i, f))
    print()
    if st["zsh"]:
        print("建议重启终端或执行 'exec zsh' 以加载新配置")


def default_state():
    return {
        "create_user": False,
        "new_username": "",
        "config_user": "root",
        "mirror": "official",
        "base": False,
        "docker": False,
        "docker_mirror": False,
        "locale": False,
        "timezone": False,
        "microcode": False,
        "zsh": False,
        "fonts": False,
        "nvim": False,
        "aur": False,
        "paru": False,
        "wsl_systemd": False,
        "wsl_default": False,
        "network": False,
        "sshd": False,
        "chrony": False,
        "cronie": False,
        "ufw": False,
        "python": False,
        "rustup": False,
        "go": False,
        "java": False,
        "node": False,
        "lua": False,
        "php": False,
        "ruby": False,
        "cpp": False,
        "git": False,
        "lazygit": False,
        "cli": False,
        "editor": False,
        "file": False,
        "sysinfo": False,
        "json": False,
        "netdiag": False,
        "starship": False,
        "man": False,
        "nav": False,
        "gitx": False,
        "plocate": False,
        "netadd": False,
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
        detect(st, [])

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
