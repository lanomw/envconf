#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
#  Arch Linux 初始化配置脚本
#  支持: 原生 Arch / WSL Arch
#  要求: 以 root 用户执行
# =============================================================================

# --------------------------- 颜色定义 ---------------------------
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# --------------------------- 配置变量 ---------------------------
CREATE_USER=false
NEW_USERNAME=""
MIRROR_PROVIDER="official"
INSTALL_BASE=false
DOCKER_MIRROR=false
INSTALL_LOCALE=false
INSTALL_FONTS=false
INSTALL_ZSH=false
INSTALL_NEOVIM=false
INSTALL_AUR=false
WSL_SYSTEMD=false
TARGET_USER=""
TARGET_HOME=""
WSL_PENDING_DEFAULT_USER=""
WSL_DEFAULT_USER=false

# --------------------------- 工具函数 ---------------------------
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERR]${NC}  $*"; }
die()   { err "$*"; exit 1; }

# 需用户在脚本结束后处理的事项，分三类统一收集到末尾打印，避免淹没在执行日志里
#   ACTIONS_NOW    : 需用户立即手动操作（如 newgrp docker、重登加载 zsh）
#   ACTIONS_REBOOT : 重启/重连后自动生效，无需用户操作（仅供知晓）
#   FAILURES       : 安装或配置失败但脚本继续的项，便于复查
ACTIONS_NOW=()
ACTIONS_REBOOT=()
FAILURES=()
postwarn()      { ACTIONS_NOW+=("$*"); }      # 兼容旧调用，按"需立即处理"归类
postwarn_now()  { ACTIONS_NOW+=("$*"); }
postwarn_reboot(){ ACTIONS_REBOOT+=("$*"); }
record_failure(){ FAILURES+=("$*"); }

print_postaction_summary() {
    local i w
    if [[ ${#FAILURES[@]} -gt 0 ]]; then
        echo ""
        heading "执行失败项汇总（脚本已继续，请复查后手动补装/修复）"
        i=1
        for w in "${FAILURES[@]}"; do
            echo -e "${RED}$i. $w${NC}"
            i=$((i+1))
        done
    fi
    if [[ ${#ACTIONS_NOW[@]} -gt 0 ]]; then
        echo ""
        heading "需立即处理（请现在执行）"
        i=1
        for w in "${ACTIONS_NOW[@]}"; do
            echo -e "${YELLOW}$i. $w${NC}"
            i=$((i+1))
        done
    fi
    if [[ ${#ACTIONS_REBOOT[@]} -gt 0 ]]; then
        echo ""
        heading "重启/重连后自动生效（无需操作，仅供知晓）"
        i=1
        for w in "${ACTIONS_REBOOT[@]}"; do
            echo -e "${CYAN}$i. $w${NC}"
            i=$((i+1))
        done
    fi
}

heading() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

# 直接回车视为 y
confirm() {
    local prompt="$1"
    local answer
    while true; do
        read -rp "$(echo -e "${YELLOW}${prompt}${NC} (Y/n): ")" answer
        if [[ -z "$answer" ]]; then
            answer="y"
        fi
        case "$answer" in
            [Yy]|[Yy][Ee][Ss]) return 0 ;;
            [Nn]|[Nn][Oo])     return 1 ;;
            *) echo "请输入 y 或 n（直接回车视为 y）" ;;
        esac
    done
}

# 直接回车视为 n（用于默认不启用的选项）
confirm_no() {
    local prompt="$1"
    local answer
    while true; do
        read -rp "$(echo -e "${YELLOW}${prompt}${NC} (y/N): ")" answer
        if [[ -z "$answer" ]]; then
            answer="n"
        fi
        case "$answer" in
            [Yy]|[Yy][Ee][Ss]) return 0 ;;
            [Nn]|[Nn][Oo])     return 1 ;;
            *) echo "请输入 y 或 n（直接回车视为 n）" ;;
        esac
    done
}

err_handler() {
    local exit_code=$?
    err "命令失败 (exit=$exit_code): 行 ${BASH_LINENO[0]} -> ${BASH_COMMAND}"
    die "脚本中止，请根据上方提示排查后重试"
}
trap err_handler ERR

is_root() { [[ $EUID -eq 0 ]]; }
is_wsl()  { [[ -f /proc/version ]] && grep -qi "microsoft\|wsl" /proc/version; }

valid_username() {
    [[ "$1" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]
}

user_home_of() {
    local user="$1"
    local home=""
    home="$(getent passwd "$user" 2>/dev/null | cut -d: -f6 || true)"
    if [[ -n "$home" ]]; then
        printf '%s\n' "$home"
        return 0
    fi
    if [[ "$user" == "root" ]]; then
        printf '/root\n'
    else
        printf '/home/%s\n' "$user"
    fi
}

target_group() {
    id -gn "$TARGET_USER"
}

# 是否允许作为"环境配置目标"：root，或 uid>=1000 的普通用户
is_configurable_user() {
    local user="$1"
    local uid
    id "$user" &>/dev/null || return 1
    uid="$(id -u "$user")"
    [[ "$user" == "root" || "$uid" -ge 1000 ]]
}

# 询问/摘要阶段：只根据已选定的目标推导路径，绝不回退到 $USER / SUDO_USER
plan_target() {
    if [[ -z "$TARGET_USER" && -n "$NEW_USERNAME" ]]; then
        TARGET_USER="$NEW_USERNAME"
    fi
    if [[ -z "$TARGET_USER" ]]; then
        die "内部错误：尚未选定目标用户"
    fi
    if id "$TARGET_USER" &>/dev/null; then
        TARGET_HOME="$(user_home_of "$TARGET_USER")"
    elif [[ -z "$TARGET_HOME" ]]; then
        TARGET_HOME="/home/$TARGET_USER"
    fi
}

# 执行阶段：用户必须存在，家目录必须属于该用户，禁止写到别人家里
assert_target() {
    plan_target
    if ! id "$TARGET_USER" &>/dev/null; then
        die "目标用户 $TARGET_USER 不存在（若刚选择创建，请确认 useradd 已成功）"
    fi
    if ! is_configurable_user "$TARGET_USER"; then
        die "拒绝配置系统账户 $TARGET_USER (uid=$(id -u "$TARGET_USER"))，请选择普通用户或 root"
    fi
    TARGET_HOME="$(user_home_of "$TARGET_USER")"
    if [[ -z "$TARGET_HOME" || "$TARGET_HOME" == "/" ]]; then
        die "目标用户 $TARGET_USER 家目录非法: '$TARGET_HOME'"
    fi
    if [[ ! -d "$TARGET_HOME" ]]; then
        info "家目录不存在，正在创建: $TARGET_HOME"
        install -d -o "$TARGET_USER" -g "$(target_group)" -m 700 "$TARGET_HOME"
    fi
    local owner
    owner="$(stat -c '%U' "$TARGET_HOME")"
    if [[ "$owner" != "$TARGET_USER" ]]; then
        die "拒绝写入：家目录 $TARGET_HOME 属于 $owner，不是 $TARGET_USER"
    fi
}

# 以目标用户身份执行；不用 login shell，避免 nologin 用户失败后误落到 root 环境变量
runas_target() {
    if [[ "$(id -u "$TARGET_USER")" -eq "$(id -u)" ]]; then
        bash -c "$*"
    else
        runuser -u "$TARGET_USER" -- bash -c "$*"
    fi
}

ensure_zsh_in_shells() {
    local zsh_path
    zsh_path="$(command -v zsh 2>/dev/null || true)"
    [[ -z "$zsh_path" ]] && zsh_path="/bin/zsh"
    grep -qxF "$zsh_path" /etc/shells 2>/dev/null || echo "$zsh_path" >> /etc/shells
}

# 非 root 时用 sudo 重新执行，避免卡在普通用户会话里无法继续
ensure_root() {
    if is_root; then
        return 0
    fi
    local me
    me="$(id -un)"
    warn "当前用户是 $me，不是 root"
    echo "可先退出当前会话回到原账户:  exit"
    if is_wsl; then
        echo "WSL 也可在 PowerShell 执行:  wsl -u root"
        echo "然后再运行本脚本；或直接:  sudo ./init.sh"
    else
        echo "请使用:  sudo ./init.sh"
    fi
    if command -v sudo >/dev/null 2>&1; then
        info "正在用 sudo 重新执行 …"
        exec sudo -- "$0" "$@"
    fi
    die "无法提升为 root。请先 exit 回到原账户，或: sudo $0"
}

# 安全改写 /etc/wsl.conf 的 section/key，不覆盖其它段
wsl_conf_set() {
    local section="$1" key="$2" value="$3"
    local file="/etc/wsl.conf"
    [[ -f "$file" ]] || : > "$file"
    if ! grep -qE "^\[${section}\]" "$file"; then
        printf '\n[%s]\n%s=%s\n' "$section" "$key" "$value" >> "$file"
        return 0
    fi
    awk -v s="$section" -v k="$key" -v v="$value" '
        $0 ~ "^\\[" s "\\]" { print; insec=1; if (!set) { print k "=" v; set=1 }; next }
        /^\[/ { insec=0 }
        insec && $0 ~ "^" k "=" { next }
        { print }
    ' "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
}

# =============================================================================
#  询问阶段
# =============================================================================
ask_create_user() {
    heading "步骤 1/10 — 用户配置"
    if ! is_root; then
        warn "当前不是 root 用户，跳过用户创建；目标用户为当前用户"
        TARGET_USER="$(id -un)"
        TARGET_HOME="$(user_home_of "$TARGET_USER")"
        return 0
    fi

    if confirm "是否创建普通用户"; then
        while true; do
            read -rp "请输入用户名: " NEW_USERNAME
            if [[ -z "$NEW_USERNAME" ]]; then
                echo "用户名不能为空"
                continue
            fi
            if ! valid_username "$NEW_USERNAME"; then
                echo "用户名非法(小写字母/下划线开头，仅含 a-z 0-9 _ -，最长32)"
                continue
            fi
            if id "$NEW_USERNAME" &>/dev/null; then
                if is_configurable_user "$NEW_USERNAME" && confirm "用户 $NEW_USERNAME 已存在，是否改为配置该用户（跳过创建）"; then
                    CREATE_USER=false
                    TARGET_USER="$NEW_USERNAME"
                    TARGET_HOME="$(user_home_of "$TARGET_USER")"
                    NEW_USERNAME=""
                    info "将配置已有用户 $TARGET_USER ($TARGET_HOME)"
                    return 0
                fi
                echo "用户已存在，请重新输入其它用户名"
                continue
            fi
            break
        done
        CREATE_USER=true
        TARGET_USER="$NEW_USERNAME"
        TARGET_HOME="/home/$NEW_USERNAME"
        info "将创建用户 $TARGET_USER，后续 Zsh / NeoVim 等用户级配置会写入 $TARGET_HOME"
        if is_wsl && confirm_no "是否将 $NEW_USERNAME 设为 WSL 默认登录用户（多用户场景建议选 n）"; then
            WSL_DEFAULT_USER=true
        fi
    else
        CREATE_USER=false
        NEW_USERNAME=""
        local existing=""
        while true; do
            read -rp "配置哪个已有用户? [root]: " existing
            if [[ -z "$existing" ]]; then
                existing="root"
            fi
            if ! valid_username "$existing"; then
                echo "用户名非法(小写字母/下划线开头，仅含 a-z 0-9 _ -，最长32)"
                continue
            fi
            if ! id "$existing" &>/dev/null; then
                echo "用户 $existing 不存在，请重新输入"
                continue
            fi
            if ! is_configurable_user "$existing"; then
                echo "拒绝配置系统账户 $existing (uid=$(id -u "$existing"))，请选择普通用户或 root"
                continue
            fi
            break
        done
        TARGET_USER="$existing"
        TARGET_HOME="$(user_home_of "$TARGET_USER")"
        if [[ "$TARGET_USER" == "root" ]]; then
            warn "未创建普通用户，目标为 root：Zsh / NeoVim 等用户级配置将写入 /root"
        else
            info "不创建新用户，将把用户级配置写入 $TARGET_USER ($TARGET_HOME)"
        fi
    fi
}

mirror_label() {
    case "${1:-official}" in
        official) echo "官方源" ;;
        tuna)     echo "清华源" ;;
        ustc)     echo "中科大源" ;;
        aliyun)   echo "阿里源" ;;
        tencent)  echo "腾讯源" ;;
        huawei)   echo "华为源" ;;
        *)        echo "$1" ;;
    esac
}

ask_mirror() {
    heading "步骤 2/10 — 镜像源配置"
    echo "  1) 官方源"
    echo "  2) 清华源"
    echo "  3) 中科大源"
    echo "  4) 阿里源"
    echo "  5) 腾讯源"
    echo "  6) 华为源"
    local answer
    while true; do
        read -rp "$(echo -e "${YELLOW}请选择镜像源 (1-6) [官方源]: ${NC}")" answer
        if [[ -z "$answer" ]]; then
            answer="1"
        fi
        case "$answer" in
            1) MIRROR_PROVIDER="official"; break ;;
            2) MIRROR_PROVIDER="tuna"; break ;;
            3) MIRROR_PROVIDER="ustc"; break ;;
            4) MIRROR_PROVIDER="aliyun"; break ;;
            5) MIRROR_PROVIDER="tencent"; break ;;
            6) MIRROR_PROVIDER="huawei"; break ;;
            *) echo "请输入 1-6，直接回车为官方源" ;;
        esac
    done
    info "已选择: $(mirror_label "$MIRROR_PROVIDER")"
    if [[ "$MIRROR_PROVIDER" == "official" ]]; then
        info "使用官方源，将不会修改 /etc/pacman.d/mirrorlist 与 pacman.conf"
    fi
}

ask_base_software() {
    heading "步骤 3/10 — 基础软件包安装"
    if confirm "是否安装基础开发软件 (sudo, git, curl, wget, openssh, make, cmake, vim, neovim, tree, docker, man)?"; then
        INSTALL_BASE=true
    fi
}

ask_docker_mirror() {
    heading "步骤 4/10 — Docker 镜像源"
    if ! $INSTALL_BASE; then
        DOCKER_MIRROR=false
        return 0
    fi
    if confirm "是否配置 Docker 国内镜像源（多源回退，自动写入推荐源）"; then
        DOCKER_MIRROR=true
    fi
}

ask_locale() {
    heading "步骤 5/10 — Locale"
    if confirm "是否配置 Locale (en_US.UTF-8 + zh_CN.UTF-8)"; then
        INSTALL_LOCALE=true
    fi
}

ask_zsh() {
    heading "步骤 6/10 — Zsh 配置"
    if confirm "是否安装并美化 Zsh (root 与目标用户均切换为 zsh)?"; then
        INSTALL_ZSH=true
    fi
}

ask_fonts() {
    heading "步骤 7/10 — 字体"
    if confirm "是否安装 Nerd Font / 中文字体 (p10k 图标与中文显示)"; then
        INSTALL_FONTS=true
    fi
}

ask_nvim() {
    heading "步骤 8/10 — NeoVim (LazyVim) 配置"
    if confirm "是否配置 NeoVim (LazyVim)"; then
        INSTALL_NEOVIM=true
    fi
}

ask_aur() {
    heading "步骤 9/10 — AUR 助手 (yay)"
    if confirm "是否为 $TARGET_USER 安装 AUR 助手 yay"; then
        INSTALL_AUR=true
    fi
}

ask_wsl_systemd() {
    if ! is_wsl; then
        WSL_SYSTEMD=false
        return 0
    fi
    heading "步骤 10/10 — WSL systemd"
    if confirm "是否在 /etc/wsl.conf 启用 systemd"; then
        WSL_SYSTEMD=true
    fi
}

show_summary() {
    plan_target

    local create_user_status mirror_status base_status docker_status locale_status font_status zsh_status nvim_status aur_status wsl_status wsl_default_user_status
    $CREATE_USER    && create_user_status="是 ($NEW_USERNAME)" || create_user_status="否"
    if [[ "$MIRROR_PROVIDER" == "official" ]]; then
        mirror_status="官方源（不改配置文件）"
    else
        mirror_status="$(mirror_label "$MIRROR_PROVIDER")"
    fi
    $INSTALL_BASE   && base_status="是"    || base_status="否"
    $DOCKER_MIRROR  && docker_status="是"  || docker_status="否"
    $INSTALL_LOCALE && locale_status="是"  || locale_status="否"
    $INSTALL_FONTS  && font_status="是"    || font_status="否"
    $INSTALL_ZSH    && zsh_status="是"     || zsh_status="否"
    $INSTALL_NEOVIM && nvim_status="是"    || nvim_status="否"
    $INSTALL_AUR    && aur_status="是 (yay)" || aur_status="否"
    if is_wsl; then
        $WSL_SYSTEMD && wsl_status="是" || wsl_status="否"
    else
        wsl_status="非 WSL"
    fi
    if is_wsl && $CREATE_USER && $WSL_DEFAULT_USER; then
        wsl_default_user_status="是 ($NEW_USERNAME)"
    else
        wsl_default_user_status="否"
    fi

    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}配置确认表${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    echo -e "  创建普通用户      : ${GREEN}${create_user_status}${NC}"
    echo -e "  镜像源            : ${GREEN}${mirror_status}${NC}"
    echo -e "  安装基础软件包    : ${GREEN}${base_status}${NC}"
    echo -e "  Docker 镜像源     : ${GREEN}${docker_status}${NC}"
    echo -e "  配置 Locale       : ${GREEN}${locale_status}${NC}"
    echo -e "  安装并美化 Zsh    : ${GREEN}${zsh_status}${NC}"
    echo -e "  安装 Nerd 字体    : ${GREEN}${font_status}${NC}"
    echo -e "  配置 NeoVim       : ${GREEN}${nvim_status}${NC}"
    echo -e "  安装 yay          : ${GREEN}${aur_status}${NC}"
    echo -e "  WSL systemd       : ${GREEN}${wsl_status}${NC}"
    echo -e "  WSL 默认登录用户  : ${GREEN}${wsl_default_user_status}${NC}"
    echo -e "  目标配置用户      : ${GREEN}${TARGET_USER}${NC}"
    echo -e "  目标配置家目录    : ${GREEN}${TARGET_HOME}${NC}"
    echo ""

    if [[ "$TARGET_USER" == "root" ]]; then
        warn "当前目标用户是 root，用户级配置（Zsh / NeoVim）会写到 /root"
    fi
}

# =============================================================================
#  执行阶段
# =============================================================================
enable_wheel_sudo() {
    # 确保 /etc/sudoers 启用 sudoers.d 目录（Arch 默认有，缺则补）
    if [[ -f /etc/sudoers ]] && ! grep -qE '^[#@]\s*includedir\s+/etc/sudoers\.d' /etc/sudoers; then
        printf '\n@includedir /etc/sudoers.d\n' >> /etc/sudoers
    fi

    local dropin="/etc/sudoers.d/99-wheel"
    if [[ -d /etc/sudoers.d ]]; then
        if [[ ! -f "$dropin" ]]; then
            printf '%s\n' '%wheel ALL=(ALL:ALL) ALL' > "$dropin"
            chmod 440 "$dropin"
            ok "已写入 $dropin，启用 wheel 组 sudo"
        fi
    elif [[ -f /etc/sudoers ]]; then
        if grep -qE '^#?\s*%wheel ALL=\(ALL:ALL\) ALL' /etc/sudoers; then
            sed -i -E 's/^#?\s*%wheel ALL=\(ALL:ALL\) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers
            ok "已启用 wheel 组的 sudo 权限"
        elif ! grep -q '^%wheel ALL=(ALL:ALL) ALL' /etc/sudoers; then
            echo '%wheel ALL=(ALL:ALL) ALL' >> /etc/sudoers
            ok "已追加 wheel 组的 sudo 权限"
        fi
    fi

    # 校验 sudoers 语法，避免写入坏配置导致 sudo 全局失效
    if command -v visudo >/dev/null 2>&1; then
        if ! visudo -cf /etc/sudoers >/dev/null 2>&1; then
            warn "visudo 校验 /etc/sudoers 失败，请手动检查 sudoers 配置"
        fi
    fi
}

exec_create_user() {
    if id "$NEW_USERNAME" &>/dev/null; then
        warn "用户 $NEW_USERNAME 已存在，跳过 useradd（可安全重跑）"
        usermod -aG wheel "$NEW_USERNAME" 2>/dev/null || true
    else
        info "创建用户: $NEW_USERNAME"
        useradd -m -G wheel -s /bin/bash "$NEW_USERNAME"
        echo "请为新用户 $NEW_USERNAME 设置密码:"
        passwd "$NEW_USERNAME"
    fi

    enable_wheel_sudo

    if is_wsl && $WSL_DEFAULT_USER; then
        WSL_PENDING_DEFAULT_USER="$NEW_USERNAME"
        info "WSL 默认登录用户将在全部步骤成功后再写入，避免中途失败卡在新用户"
    fi

    TARGET_USER="$NEW_USERNAME"
    if ! id "$TARGET_USER" &>/dev/null; then
        die "useradd 后仍检测不到用户 $TARGET_USER"
    fi
    TARGET_HOME="$(user_home_of "$TARGET_USER")"
    if [[ ! -d "$TARGET_HOME" ]]; then
        die "useradd -m 后家目录不存在: $TARGET_HOME"
    fi
    local owner
    owner="$(stat -c '%U' "$TARGET_HOME")"
    if [[ "$owner" != "$TARGET_USER" ]]; then
        die "新用户家目录 $TARGET_HOME 属于 $owner，不是 $TARGET_USER"
    fi
    ok "用户 $NEW_USERNAME 就绪 (home=$TARGET_HOME)"
}

official_arch_url()   { echo 'https://geo.mirror.pkgbuild.com/$repo/os/$arch'; }
tuna_arch_url()       { echo 'https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch'; }
ustc_arch_url()       { echo 'https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch'; }
aliyun_arch_url()     { echo 'https://mirrors.aliyun.com/archlinux/$repo/os/$arch'; }
tencent_arch_url()    { echo 'https://mirrors.cloud.tencent.com/archlinux/$repo/os/$arch'; }
huawei_arch_url()     { echo 'https://mirrors.huaweicloud.com/archlinux/$repo/os/$arch'; }

official_cn_url() { echo 'https://repo.archlinuxcn.org/$arch'; }
tuna_cn_url()     { echo 'https://mirrors.tuna.tsinghua.edu.cn/archlinuxcn/$arch'; }
ustc_cn_url()     { echo 'https://mirrors.ustc.edu.cn/archlinuxcn/$arch'; }
aliyun_cn_url()   { echo 'https://mirrors.aliyun.com/archlinuxcn/$arch'; }
tencent_cn_url()  { echo 'https://mirrors.cloud.tencent.com/archlinuxcn/$arch'; }
huawei_cn_url()   { echo 'https://mirrors.ustc.edu.cn/archlinuxcn/$arch'; }

arch_url_of() {
    case "$1" in
        official) official_arch_url ;;
        tuna)     tuna_arch_url ;;
        ustc)     ustc_arch_url ;;
        aliyun)   aliyun_arch_url ;;
        tencent)  tencent_arch_url ;;
        huawei)   huawei_arch_url ;;
        *)        official_arch_url ;;
    esac
}

cn_url_of() {
    case "$1" in
        official) official_cn_url ;;
        tuna)     tuna_cn_url ;;
        ustc)     ustc_cn_url ;;
        aliyun)   aliyun_cn_url ;;
        tencent)  tencent_cn_url ;;
        huawei)   huawei_cn_url ;;
        *)        official_cn_url ;;
    esac
}

# 所选源排第一，其余作回退
write_mirrorlist() {
    local primary="$1"
    local order=(official tuna ustc aliyun tencent huawei)
    local id
    {
        echo "# 首选: $(mirror_label "$primary")"
        printf 'Server = %s\n' "$(arch_url_of "$primary")"
        for id in "${order[@]}"; do
            [[ "$id" == "$primary" ]] && continue
            printf 'Server = %s\n' "$(arch_url_of "$id")"
        done
    } > /etc/pacman.d/mirrorlist
}

write_archlinuxcn_mirrorlist() {
    local primary="$1"
    local order=(official tuna ustc aliyun tencent huawei)
    local id
    {
        echo "# 首选: $(mirror_label "$primary")"
        printf 'Server = %s\n' "$(cn_url_of "$primary")"
        for id in "${order[@]}"; do
            [[ "$id" == "$primary" ]] && continue
            printf 'Server = %s\n' "$(cn_url_of "$id")"
        done
    } > /etc/pacman.d/archlinuxcn-mirrorlist
}

ensure_archlinuxcn_repo() {
    write_archlinuxcn_mirrorlist "$MIRROR_PROVIDER"
    if grep -qE '^\[archlinuxcn\]' /etc/pacman.conf; then
        if ! grep -qE '^Include\s*=\s*/etc/pacman.d/archlinuxcn-mirrorlist' /etc/pacman.conf; then
            sed -i '/^\[archlinuxcn\]/a Include = /etc/pacman.d/archlinuxcn-mirrorlist' /etc/pacman.conf
        fi
        return 0
    fi
    cat << 'PACMAN_EOF' >> /etc/pacman.conf

[archlinuxcn]
Include = /etc/pacman.d/archlinuxcn-mirrorlist
PACMAN_EOF
}

pacman_sync() {
    if pacman -Syy --noconfirm; then
        return 0
    fi
    warn "软件源同步失败，正在重试一次 …"
    if pacman -Syy --noconfirm; then
        return 0
    fi
    return 1
}

exec_mirror() {
    if [[ "$MIRROR_PROVIDER" == "official" ]]; then
        info "已选择官方源，跳过修改 /etc/pacman.d/mirrorlist 与 pacman.conf"
        return 0
    fi

    info "配置镜像源：$(mirror_label "$MIRROR_PROVIDER")（所选源优先，其余回退）…"
    if [[ -f /etc/pacman.d/mirrorlist ]]; then
        cp /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist.bak.$(date +%s)
    fi

    write_mirrorlist "$MIRROR_PROVIDER"
    ensure_archlinuxcn_repo

    pacman-key --init || { warn "pacman-key --init 失败，继续尝试"; record_failure "pacman-key --init 失败，可能影响包签名校验"; }
    pacman-key --populate archlinux || { warn "pacman-key --populate archlinux 失败，继续尝试"; record_failure "pacman-key --populate archlinux 失败，可能影响包签名校验"; }

    if ! pacman_sync; then
        die "软件源同步失败。请检查网络后重跑本脚本（可安全重跑，不会重复创建用户）"
    fi

    if ! pacman -S --needed --noconfirm archlinuxcn-keyring; then
        warn "archlinuxcn-keyring 安装失败，后续 archlinuxcn 软件可能无法签名校验"
        record_failure "archlinuxcn-keyring 安装失败，请手动执行: pacman -S archlinuxcn-keyring"
    else
        pacman-key --populate archlinuxcn 2>/dev/null || true
    fi

    ok "镜像源配置完成"
}

exec_base_software() {
    info "安装基础软件包 …"
    local pkgs=(sudo git base-devel make cmake vim neovim tree docker curl wget openssh man-db man-pages which less unzip)

    $INSTALL_ZSH && pkgs+=(zsh zsh-completions)

    if is_wsl; then
        info "检测到 WSL 环境"
    fi

    if pacman -S --needed --noconfirm "${pkgs[@]}"; then
        ok "基础软件包安装完成"
    else
        record_failure "基础软件包安装失败，请手动执行: pacman -S ${pkgs[*]}"
        warn "基础软件包安装失败，脚本继续（后续依赖可能缺失）"
        return 0
    fi

    assert_target

    if [[ "$TARGET_USER" != "root" ]]; then
        if usermod -aG docker "$TARGET_USER" 2>/dev/null; then
            postwarn_now "$TARGET_USER 已加入 docker 组，需重新登录或执行 'newgrp docker' 后才能免 sudo 使用 docker"
        else
            record_failure "无法将 $TARGET_USER 加入 docker 组"
        fi
    fi

    if is_wsl; then
        record_failure "WSL 环境未执行 systemctl enable docker（systemd 不可用）"
        postwarn_now "如需在 WSL 使用 docker：安装 Docker Desktop 并启用 WSL 集成，或在 WSL 内手动启动 dockerd"
    else
        if ! systemctl enable docker; then
            err "systemctl enable docker 失败"
            record_failure "systemctl enable docker 失败，请手动执行: systemctl enable --now docker"
        else
            ok "docker 服务已启用"
        fi
    fi

exec_docker_mirror() {
    if ! $DOCKER_MIRROR; then
        return 0
    fi
    info "配置 Docker 国内镜像源 …"
    local cfg="/etc/docker"
    install -d -m 755 "$cfg"
    if [[ -f "$cfg/daemon.json" ]]; then
        cp "$cfg/daemon.json" "$cfg/daemon.json.bak.$(date +%s)"
        warn "已备份原 daemon.json"
    fi
    cat << 'DOCKER_EOF' > "$cfg/daemon.json"
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
DOCKER_EOF
    if ! is_wsl && command -v systemctl >/dev/null 2>&1; then
        if systemctl restart docker 2>/dev/null; then
            ok "docker 服务已重启加载镜像源"
        else
            record_failure "docker 重启加载镜像源失败，请手动执行: systemctl restart docker"
        fi
    else
        postwarn_reboot "WSL/无 systemd：daemon.json 已写入，启动 dockerd 时自动读取生效（无需手动操作）"
    fi
    ok "Docker 镜像源已写入 /etc/docker/daemon.json"
}

exec_locale() {
    info "配置 Locale (en_US.UTF-8 + zh_CN.UTF-8) …"
    local loc
    for loc in "en_US.UTF-8" "zh_CN.UTF-8"; do
        if grep -qE "^#${loc}[[:space:]]" /etc/locale.gen 2>/dev/null; then
            sed -i "s/^#${loc}[[:space:]].*/${loc} UTF-8/" /etc/locale.gen
        elif ! grep -qE "^${loc}[[:space:]]" /etc/locale.gen 2>/dev/null; then
            echo "${loc} UTF-8" >> /etc/locale.gen
        fi
    done
    locale-gen || { record_failure "locale-gen 失败，Locale 可能未生效"; warn "locale-gen 执行失败，locale 配置可能未生效"; return 0; }
    printf '%s\n' 'LANG=en_US.UTF-8' > /etc/locale.conf
    ok "Locale 已写入 /etc/locale.conf (LANG=en_US.UTF-8)，已生成中英 UTF-8"
}

exec_fonts() {
    info "安装字体 (Meslo Nerd Font + 中文/Emoji) …"
    if ! pacman -S --needed --noconfirm ttf-meslo-nerd noto-fonts-cjk noto-fonts-emoji; then
        warn "部分字体安装失败，p10k 图标或中文可能显示异常"
        record_failure "字体安装失败 (ttf-meslo-nerd / noto-fonts-cjk / noto-fonts-emoji)，请手动执行: pacman -S ttf-meslo-nerd noto-fonts-cjk noto-fonts-emoji"
        return 0
    fi
    if is_wsl; then
        postwarn_now "WSL:请在 Windows Terminal → 配置文件 → 外观 → 字体 选择 MesloLGS NF"
    fi
    ok "字体安装完成"
}

exec_aur() {
    assert_target
    if command -v yay >/dev/null 2>&1; then
        info "yay 已安装，跳过"
        return 0
    fi

    # yay 已收录在 archlinuxcn 仓库，直接用 pacman 全局安装；软件全局可用，无需 makepkg
    info "安装 yay（来自 archlinuxcn 仓库）…"
    if ! pacman -S --needed --noconfirm yay; then
        record_failure "yay 安装失败：请确认 archlinuxcn 仓库已配置后手动执行: pacman -S yay"
        return 0
    fi
    ok "yay 安装完成"
}

exec_wsl_systemd() {
    if ! is_wsl; then
        return 0
    fi
    info "写入 /etc/wsl.conf [boot] systemd=true"
    wsl_conf_set "boot" "systemd" "true"
    postwarn_reboot "WSL systemd 已写入 /etc/wsl.conf，wsl --shutdown 后重开自动生效"
    ok "WSL systemd 已写入"
}

apply_wsl_default_user() {
    if ! is_wsl || [[ -z "$WSL_PENDING_DEFAULT_USER" ]]; then
        return 0
    fi
    wsl_conf_set "user" "default" "$WSL_PENDING_DEFAULT_USER"
    postwarn_reboot "WSL 默认登录用户已设为 $WSL_PENDING_DEFAULT_USER，wsl --shutdown 后重开自动生效"
}

exec_zsh() {
    assert_target
    info "配置 Zsh (目标: $TARGET_USER , 家目录: $TARGET_HOME) …"

    if ! command -v zsh &>/dev/null; then
        if ! pacman -S --needed --noconfirm zsh zsh-completions; then
            record_failure "zsh 安装失败，Zsh 配置将跳过"
            warn "zsh 安装失败，跳过 Zsh 配置"
            return 0
        fi
    fi

    ensure_zsh_in_shells

    local zsh_dir="$TARGET_HOME/.zsh"
    install -d -o "$TARGET_USER" -g "$(target_group)" "$zsh_dir"

    # 用 | 分隔 URL 与目录名，避免 https:// 中的冒号被截断
    local plugins=(
        "https://github.com/zsh-users/zsh-autosuggestions|zsh-autosuggestions"
        "https://github.com/zsh-users/zsh-syntax-highlighting|zsh-syntax-highlighting"
        "https://github.com/romkatv/powerlevel10k.git|powerlevel10k"
    )
    local item url name dest
    for item in "${plugins[@]}"; do
        url="${item%%|*}"
        name="${item##*|}"
        dest="$zsh_dir/$name"
        if [[ ! -d "$dest/.git" ]]; then
            runas_target "git clone --depth=1 '$url' '$dest'" \
                || { warn "以 $TARGET_USER 克隆失败，改用当前用户克隆到 $dest"; git clone --depth=1 "$url" "$dest" \
                    || { record_failure "zsh 插件 $name 克隆失败，请手动安装"; warn "zsh 插件 $name 克隆失败"; }; }
        fi
    done

    if [[ -f "$TARGET_HOME/.zshrc" ]] && grep -q 'Zsh 配置 — 美化版' "$TARGET_HOME/.zshrc"; then
        info "已检测到本脚本写入的 .zshrc，跳过覆盖（可安全重跑）"
    else
        if [[ -f "$TARGET_HOME/.zshrc" ]]; then
            mv "$TARGET_HOME/.zshrc" "$TARGET_HOME/.zshrc.bak.$(date +%s)"
            warn "已备份原 .zshrc"
        fi
        cat << 'ZSHCFG' > "$TARGET_HOME/.zshrc"
# ============================
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

if grep -qi "microsoft\|wsl" /proc/version 2>/dev/null; then
    alias winhome='cd /mnt/c/Users/$([ ! -z "$USER" ] && echo $USER || echo $USERNAME)'
fi

[[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh
[[ -f ~/.zsh_env ]] && source ~/.zsh_env
ZSHCFG
    fi

    chown -R "$TARGET_USER:$(target_group)" "$TARGET_HOME/.zshrc" "$zsh_dir"

    chsh -s /bin/zsh "$TARGET_USER" 2>/dev/null || { warn "$TARGET_USER 切换默认 shell 为 zsh 失败"; record_failure "$TARGET_USER 切换 zsh 失败，请手动执行: chsh -s /bin/zsh $TARGET_USER"; }
    if is_root && [[ "$(whoami)" != "$TARGET_USER" ]]; then
        chsh -s /bin/zsh root 2>/dev/null || { warn "root 切换 zsh 失败，su - 后仍为原 shell"; record_failure "root 切换 zsh 失败，请手动执行: chsh -s /bin/zsh root"; }
        if [[ ! -f /root/.zshrc ]]; then
            cat << 'ZSHCFG' > /root/.zshrc
# ============================
#  Zsh 配置 — 美化版 (root)
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

[[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh
[[ -f ~/.zsh_env ]] && source ~/.zsh_env
ZSHCFG
            install -d -o root -g root /root/.zsh
            cp -r "$TARGET_HOME/.zsh/powerlevel10k" /root/.zsh/ 2>/dev/null || true
            cp -r "$TARGET_HOME/.zsh/zsh-autosuggestions" /root/.zsh/ 2>/dev/null || true
            cp -r "$TARGET_HOME/.zsh/zsh-syntax-highlighting" /root/.zsh/ 2>/dev/null || true
            ok "已为 root 创建 .zshrc 并复制插件"
        fi
    fi

    postwarn_now "Zsh 已配置：注销重新登录或执行 'exec zsh' 加载；首次进入会触发 p10k 个性化向导"
    ok "Zsh 美化配置完成"
}

exec_nvim() {
    assert_target
    info "配置 NeoVim LazyVim (目标: $TARGET_USER , 家目录: $TARGET_HOME) …"

    info "安装 LazyVim 前置依赖 …"
    local deps=(ripgrep fd unzip lazygit fzf nodejs npm gcc make)
    pacman -S --needed --noconfirm "${deps[@]}" || { warn "部分 LazyVim 依赖安装失败，首次启动可能报缺工具"; record_failure "LazyVim 依赖安装失败 (ripgrep/fd/lazygit/fzf/nodejs 等)，请手动安装"; }

    local nvim_dir="$TARGET_HOME/.config/nvim"
    local share_dir="$TARGET_HOME/.local/share/nvim"
    local state_dir="$TARGET_HOME/.local/state/nvim"
    local cache_dir="$TARGET_HOME/.cache/nvim"

    install -d -o "$TARGET_USER" -g "$(target_group)" \
        "$TARGET_HOME/.config" \
        "$TARGET_HOME/.local" \
        "$TARGET_HOME/.local/share" \
        "$TARGET_HOME/.local/state" \
        "$TARGET_HOME/.cache"

    if [[ -f "$nvim_dir/init.lua" && -d "$nvim_dir/lua" ]]; then
        info "已检测到 NeoVim 配置，跳过克隆（可安全重跑）"
        chown -R "$TARGET_USER:$(target_group)" "$nvim_dir"
        ok "NeoVim LazyVim 配置已存在，未覆盖"
        return 0
    fi

    local ts
    ts="$(date +%s)"
    local d
    for d in "$nvim_dir" "$share_dir" "$state_dir" "$cache_dir"; do
        if [[ -d "$d" ]]; then
            mv "$d" "$d.bak.$ts"
            warn "已备份不完整目录: $d -> $d.bak.$ts"
        fi
    done

    runas_target "git clone --depth=1 https://github.com/LazyVim/starter '$nvim_dir'" \
        || { warn "以 $TARGET_USER 克隆失败，改用当前用户克隆到 $nvim_dir"; git clone --depth=1 https://github.com/LazyVim/starter "$nvim_dir" \
            || { record_failure "NeoVim LazyVim 克隆失败，请手动执行: git clone https://github.com/LazyVim/starter $nvim_dir"; return 0; }; }
    rm -rf "$nvim_dir/.git"

    chown -R "$TARGET_USER:$(target_group)" "$nvim_dir"

    postwarn_now "NeoVim: 首次 'nvim' 会自动下载 LazyVim 插件，请保持网络畅通"
    ok "NeoVim LazyVim 配置完成"
}

# =============================================================================
#  主流程
# =============================================================================
run_questions() {
    # 重置选择，避免"重新配置"时残留旧值
    CREATE_USER=false
    NEW_USERNAME=""
    MIRROR_PROVIDER="official"
    INSTALL_BASE=false
    DOCKER_MIRROR=false
    INSTALL_LOCALE=false
    INSTALL_FONTS=false
    INSTALL_ZSH=false
    INSTALL_NEOVIM=false
    INSTALL_AUR=false
    WSL_SYSTEMD=false
    TARGET_USER=""
    TARGET_HOME=""
    WSL_PENDING_DEFAULT_USER=""
    WSL_DEFAULT_USER=false
    ask_create_user
    ask_mirror
    ask_base_software
    ask_docker_mirror
    ask_locale
    ask_zsh
    ask_fonts
    ask_nvim
    ask_aur
    ask_wsl_systemd
}

run_execution() {
    $CREATE_USER    && exec_create_user
    exec_mirror
    $INSTALL_BASE   && exec_base_software
    exec_docker_mirror
    $INSTALL_LOCALE && exec_locale
    $INSTALL_ZSH    && exec_zsh
    $INSTALL_FONTS  && exec_fonts
    $INSTALL_NEOVIM && exec_nvim
    $INSTALL_AUR    && exec_aur
    $WSL_SYSTEMD    && exec_wsl_systemd
    apply_wsl_default_user

    heading "初始化配置全部完成！"
    assert_target
    echo "目标用户: $TARGET_USER"
    echo "家目录  : $TARGET_HOME"
    if $CREATE_USER; then
        echo "请使用: su - $TARGET_USER   切换到新用户"
    elif [[ "$TARGET_USER" == "root" ]]; then
        echo "本次未创建普通用户，用户级配置已写入 root (/root)"
    fi
    print_postaction_summary
    echo ""
    if $INSTALL_ZSH; then
        echo "建议重启终端或执行 'exec zsh' 以加载新配置"
    fi
}

main() {
    ensure_root "$@"

    if [[ ! -f /etc/arch-release ]]; then
        warn "未检测到 /etc/arch-release，当前可能不是 Arch Linux"
        confirm "是否继续执行" || exit 0
    fi

    heading "Arch Linux 初始化配置脚本"
    echo "支持原生 Arch / WSL Arch，所有配置均针对最终目标用户"
    echo "提示: 询问步骤直接回车视为是 (Y)"
    echo ""

    while true; do
        run_questions
        show_summary

        local confirm_answer
        while true; do
            read -rp "$(echo -e "${YELLOW}确认以上配置并执行? (y=执行 / n=退出 / r=重新配置) [y]: ${NC}")" confirm_answer
            if [[ -z "$confirm_answer" ]]; then
                confirm_answer="y"
            fi
            case "$confirm_answer" in
                [Yy]|[Yy][Ee][Ss]) run_execution; exit 0 ;;
                [Nn]|[Nn][Oo])     info "已取消，退出"; exit 0 ;;
                [Rr])              info "重新开始配置 …"; break ;;
                *) echo "请输入 y / n / r（直接回车视为 y）" ;;
            esac
        done
    done
}

main "$@"
