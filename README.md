# lazyvim配置片段

## lua/config/options.lua
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

### wsl2和windows剪切板互通win32yank方案
``` bash
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


## lua/plugins/conform.lua
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
