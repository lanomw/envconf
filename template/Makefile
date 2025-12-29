CROSS_COMPILE 	?=
CC	= $(CROSS_COMPILE)gcc
AR	= $(CROSS_COMPILE)ar

# 定义编译选项
CFLAGS 		:= -std=c11 -D_GNU_SOURCE -MMD -MP -Wall -Wno-unused-function -Wno-unused-variable
LDFLAGS 	:= -lpthread -lm

# 输入
SRC_DIR 	= 
INCS = 
LIBS = 

# 输出
TARGET 		= app
OUT_DIR 	:= build
BUILD_DIR 	:= $(OUT_DIR)/_build
TARGET_DIR	:= $(OUT_DIR)/output

# 头文件路径、源文件、依赖
INCS += -I. $(foreach dir,$(SRC_DIR),-I$(dir))
SRCS = $(wildcard ./*.c $(foreach dir,$(SRC_DIR),$(dir)/*.c))
OBJS = $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))
DEPS = $(OBJS:.o=.d)
VPATH = $(SRC_DIR)

# 命令
RM =
MKDIR =

# 环境兼容
ifeq ($(OS), Windows_NT)
	RM = cmd /c rd /s /q
	MKDIR = mkdir
else ifeq ($(shell uname -s), Linux)
	LDFLAGS += -Llib/linux -L/usr/x86_64-w64-mingw32/lib -lglfw3 -lgdi32 -lopengl32 -limm32 -static
	RM = rm -rf
	MKDIR = mkdir -p
endif


all: $(TARGET)

$(TARGET): $(OBJS) | $(TARGET_DIR)
# 	@echo "[AR] $(TARGET_DIR)/$(TARGET) $(LIBS)"
# 	@$(AR) rcs $(TARGET_DIR)/$(TARGET) $^ $(LIBS)

	@echo "[CC] $(TARGET_DIR)/$(TARGET) $(LIBS)"
	@$(CC) $(LDFLAGS) $^ $(LIBS) -o $(TARGET_DIR)/$(TARGET)

	@echo "\ncompile success\n"

$(OBJS): $(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	@echo "[CC] $<"
	@$(CC) $(CFLAGS) $(INCS) -c $< -o $@

$(TARGET_DIR):
	mkdir -p $(BUILD_DIR) $(TARGET_DIR)

$(BUILD_DIR):
	mkdir -p $(foreach dir,$(SRC_DIR),$(BUILD_DIR)/$(dir))

clean:
	rm -rf $(OUT_DIR)

.PHONY: all clean

# include 所有.d文件，使头文件依赖生效
# 如果依赖文件列表不为空, 就直接包含(include)依赖文件列表
ifneq ($(DEPS),)
	include $(DEPS)
endif
