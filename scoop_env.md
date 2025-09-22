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
scoop install curl wget grep less sed touch fd fzf lazygit ripgrep
scoop install gcc cmake make python clangd llvm
scoop install snipaste pandoc wireshark quicklook SpaceSniffer
```

## 配置文件
打开配置文件`notepad $PROFILE`后写入以下内容
```shell
Invoke-Expression (&starship init powershell)

Import-Module PSReadLine
Set-PSReadLineOption -EditMode Emacs

Import-Module scoop-completion

New-Alias -Name l -Value "ls"
```