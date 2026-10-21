# WSL配置

[Mricosoft WSL安装](https://learn.microsoft.com/zh-cn/windows/wsl/install)

[在 WSL 上安装 Arch Linux](https://wiki.archlinux.org.cn/title/Install_Arch_Linux_on_WSL)

## 命令行自定义WSL安装位置（应该是目前最简单的方案）
```shell
# 安装wsl内核和工具
wsl --install

# arch离线安装示例
wsl --install --from-file C:\Users\atk\Downloads\archlinux.wsl --location E:\WSL\ArchLinux
```

安装后后，执行`wsl -d root`进入wsl并执行脚本`archlinux-setup/arch-setup.py`
