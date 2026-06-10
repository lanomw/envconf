# powershell scoop 环境配置

[Scoop管理Windows下的软件和开发环境](https://blog.dejavu.moe/posts/windows-scoop/)

**注意：scoop安装软件时的日志输出需要留意，日志中会提醒需要手动执行的命令**

## 安装scoop
管理员执行命令`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`允许执行本地脚本

```shell
irm get.scoop.sh -OutFile 'install.ps1'
.\install.ps1 -RunAsAdmin -ScoopDir 'D:\Scoop'
rm .\install.ps1
```

## 安装软件包
```shell
scoop bucket add dorado https://github.com/chawyehsu/dorado

scoop install 7zip git gsudo scoop-completion starship
scoop install busybox curl fzf
scoop install cmake make python llvm-mingw
scoop install neovim luarocks fd lazygit ripgrep
scoop install snipaste sumatrapdf pandoc windterm wireshark SpaceSniffer
```
注：如果使用msys环境则无需安装`llvm-mingw、cmake、make`


### msys2
```shell
scoop install mingw-winlibs-ucrt msys2
```

取消`msys2_shell.cmd`中的`MSYS2_PATH_TYPE=inherit`注释使继承windows环境
msys2集成到`windows terminal`的命令行配置：`D:\Scoop\apps\msys2\current\msys2_shell.cmd -defterm -here -no-start -use-full-path -msys -shell zsh`

代理配置写入`~/.zprofile`
```file
export https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 all_proxy=socks5://127.0.0.1:7897
```

## 配置文件
打开配置文件`notepad $PROFILE`后写入以下内容
```shell
# ========== 基础设置（启动时必需，开销极小） ==========
$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding
# $env:HTTP_PROXY = "http://127.0.0.1:7890"
# $env:HTTPS_PROXY = "http://127.0.0.1:7890"

'rm','cat','cp','mv','pwd','ps' | % { Remove-Alias $_ -Force -ErrorAction Ignore }
New-Alias -Name l -Value "ls"

# Starship 初始化（本身就是异步的，保持原样）
Invoke-Expression (&starship init powershell)

# ========== 延迟加载区域 ==========
# 注册 OnIdle 事件，在终端空闲时自动导入模块
$action = {
    # 导入 PSReadLine
    Import-Module PSReadLine -ErrorAction Stop
    Set-PSReadLineOption -EditMode Emacs
    # 导入 scoop-completion
    Import-Module scoop-completion -ErrorAction Stop
    # 任务完成后解除事件注册，避免重复执行
    Unregister-Event -SourceIdentifier ProfileIdle -Force
}

# 创建事件订阅（仅在 PowerShell 7+ 中支持 OnIdle）
Register-EngineEvent -SourceIdentifier PowerShell.OnIdle -SupportEvent -Action $action
```
