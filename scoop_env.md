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
scoop install 7zip git gsudo scoop-completion starship
scoop install busybox curl fzf
scoop install mingw cmake make python llvm
scoop install neovim luarocks fd lazygit ripgrep
scoop install snipaste sumatrapdf pandoc windterm wireshark SpaceSniffer
```
注：如果使用msys环境则无需安装`mingw、cmake、make`


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
Invoke-Expression (&starship init powershell)

Import-Module PSReadLine
Set-PSReadLineOption -EditMode Emacs

Import-Module scoop-completion

'rm','cat','cp','mv','pwd','ps' | % { Remove-Alias $_ -Force -ErrorAction Ignore }
New-Alias -Name l -Value "ls"
```
