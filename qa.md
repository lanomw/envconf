# 环境问题汇总

## windows环境cmake编译各种失败
cmake默认使用visual studio相关的环境，所以需要手动指定需要使用的工具链
```shell
cmake -B build -G "MinGW Makefiles" -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ -DCMAKE_MAKE_PROGRAM=make
```

## windows环境vscode+clangd，默认使用clangd内置头文件而不是mingw的头文件
创建文件`%LocalAppData%/clangd/config.yaml`并写入以下内容
```yaml
CompileFlags:
  Add: [
    # -nostdinc,                  # 禁止再搜 clang 内置目录
    -isystem, D:/Scoop/apps/mingw/current/x86_64-w64-mingw32/include,
  ]

```
