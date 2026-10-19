# WSL配置

将[.wslconfig](./template/.clang-format)放在系统环境的用户目录下作为全局配置

命令行使用及配置参考[Mricosoft WSL安装](https://learn.microsoft.com/zh-cn/windows/wsl/install)

## 命令行自定义WSL安装位置（应该是目前最简单的方案）
```shell
# 安装wsl内核和工具
wsl --install

# arch离线安装示例
wsl --install --from-file C:\Users\atk\Downloads\archlinux-2026.08.01.174141.wsl --location E:\WSL\ArchLinux
```

安装后后，执行`wsl -d root`进入wsl并执行脚本`archlinux-setup/arch-setup.py`
