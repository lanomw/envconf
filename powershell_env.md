## powershel 环境配置

## 配置文件
打开配置文件`notepad $PROFILE`后写入以下内容
```shell
Invoke-Expression (&starship init powershell)

Import-Module PSReadLine
Set-PSReadLineOption -EditMode Emacs

Import-Module scoop-completion

New-Alias -Name l -Value "ls"
```

