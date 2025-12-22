CROSS_COMPILE 	=

CC	= $(CROSS_COMPILE)gcc
AR	= $(CROSS_COMPILE)ar

# 定义编译选项
CFLAGS 	:= -std=c11 -D_GNU_SOURCE -MMD -MP -Wall -Wno-unused-function -Wno-unused-variable
LDFLAGS := 

SRC_DIR 	= . # 源码目录
BUILD_DIR 	= build/_build
OUT_DIR		= build/output
TARGET 		= out

INCS = $(foreach dir,$(SRC_DIR),-I$(dir))
LIBS = 

SRCS = $(wildcard $(foreach dir,$(SRC_DIR),$(dir)/*.c))
OBJS = $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))
DEPS := $(OBJS:.o=.d)

VPATH := $(SRC_DIR)

all: $(TARGET)

$(TARGET): $(OBJS)
# 	@echo "[AR] $(OUT_DIR)/$(TARGET) $(LIBS)"
# 	@$(AR) rcs $(OUT_DIR)/$(TARGET) $^ $(LIBS)

	@echo "[CC] $(OUT_DIR)/$(TARGET) $(LIBS)"
	@$(CC) $(LDFLAGS) $^ $(LIBS) -o $(OUT_DIR)/$(TARGET)

	@echo "\ncompile success\n"

$(OBJS): $(BUILD_DIR)/%.o: %.c | $(BUILD_DIR) $(OUT_DIR)
	@echo "[CC] -c $<"
	@$(CC) $(CFLAGS) $(INCS) -c $< -o $@

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR) $(OUT_DIR)
	mkdir -p $(foreach dir,$(SRC_DIR),$(BUILD_DIR)/$(dir))

clean:
	rm -rf $(BUILD_DIR)

.PHONY := all clean

# include 所有.d文件，使头文件依赖生效
# 如果依赖文件列表不为空, 就直接包含(include)依赖文件列表
ifneq ($(DEPS),)
	include $(DEPS)
endif
