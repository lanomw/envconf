# windows环境问题汇总

## cmake编译各种失败
cmake默认使用visual studio相关的环境，所以需要手动指定需要使用的工具链
```shell
cmake -B build -G "MinGW Makefiles" -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ -DCMAKE_MAKE_PROGRAM=make
```
