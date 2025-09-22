# nvim配置

[vim常用快捷键](https://vim.rtorr.com/lang/zh_cn)

## 一、安装nvim
ubuntu包管理器中的nvim版本过旧，需手动进行安装。
从[nvim](https://github.com/neovim/neovim/releases)下载压缩包并执行以下命令
```shell
tar zxvf nvim-linux-x86_64.tar.gz
sudo mv nvim-linux-x86_64 /usr/local/nvim
sudo ln -sf /usr/local/nvim/bin/nvim /usr/bin/nvim
nvim -V1 -v
```

## 二、安装lazyvim
参考[lazyvim](https://www.lazyvim.org/installation)内的安装方式进行安装

## 三、WSL和windows剪切板互通

### powershell方案（推荐）

参考自[与WSL/Windows共享NeoVim剪贴板](https://bogdan-calapod.github.io/posts/neovim-wsl-clipboard/)

lua/config/options.lua
```lua
-- 缩进
local opt = vim.opt
opt.shiftwidth = 4

-- 和windows剪切板互通
-- 如运行在windows上则需要移除`-c chcp 65001 &&`
vim.g.clipboard = {
  name = "WslClipboard",
  copy = {
    ["+"] = { "clip.exe" },
    ["*"] = { "clip.exe" },
  },
  paste = {
    ["+"] = {
      "/mnt/c/Windows/System32/WindowsPowerShell/v1.0///powershell.exe",
      "-c chcp 65001 &&",
      '[Console]::Out.Write($(Get-Clipboard -Raw).tostring().replace("`r", ""))',
    },
    ["*"] = {
      "/mnt/c/Windows/System32/WindowsPowerShell/v1.0///powershell.exe",
      "-c chcp 65001 &&",
      '[Console]::Out.Write($(Get-Clipboard -Raw).tostring().replace("`r", ""))',
    },
  },
  cache_enabled = 0,
}
```

### win32yank方案
``` shell
curl -sLO https://github.com/equalsraf/win32yank/releases/latest/download/win32yank-x64.zip
unzip win32yank-x64.zip && chmod +x win32yank.exe
sudo mv win32yank.exe /usr/local/bin/
```
``` lua
-- lua/config/options.lua
vim.g.clipboard = {
  name = "Win32Yank",
  copy = {
    ["+"] = "win32yank.exe -i --crlf",
    ["*"] = "win32yank.exe -i --crlf",
  },
  paste = {
    ["+"] = "win32yank.exe -o --lf",
    ["*"] = "win32yank.exe -o --lf",
  },
  cache_enabled = 0,
}
```

### ssh方案
配置稍显复杂，详情见[穿透wsl和ssh跨设备任意复制](https://www.cnblogs.com/sxrhhh/p/18234652/neovim-copy-anywhere)

## 四、`c/c++`格式化配置

将[.clang-format](./template/.clang-format)放在系统环境的用户目录下作为全局配置

lua/plugins/conform.lua
```lua
-- clang-format格式化配置，并指定.clang-format
return {
  {
    "stevearc/conform.nvim",
    opts = {
      formatters = {
        clang_format = {
          command = "clang-format",
          args = {
            -- windows环境需更换为os.getenv("USERPROFILE")
            "--style=file:" .. os.getenv("HOME") .. "/.clang-format",
            "-assume-filename=$FILENAME",
          },
          stdin = true,
        },
      },
      formatters_by_ft = {
        c = { "clang_format" },
        cpp = { "clang_format" },
      },
    },
  },
}
```
## 问题记录

- [记录LazyVim安装使用过程中解决的一些问题](https://zhuanlan.zhihu.com/p/671439100)
- [未找到tree-sitter可执行文件](https://github.com/nvim-treesitter/nvim-treesitter/issues/1097#issuecomment-1368177624)
