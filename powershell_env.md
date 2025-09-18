## powershel 环境配置

## 软件包安装
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
