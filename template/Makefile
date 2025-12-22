CROSS_COMPILE 	?=
CC	= $(CROSS_COMPILE)gcc
AR	= $(CROSS_COMPILE)ar

# 定义编译选项
CFLAGS 		:= -std=c11 -D_GNU_SOURCE -MMD -MP -Wall -Wno-unused-function -Wno-unused-variable
LDFLAGS 	:= -lpthread -lm

# 输入
SRC_DIR 	= 
TARGET 		= app
INCS = 
LIBS = 

# 输出
OUT_DIR 	:= build
BUILD_DIR 	:= $(OUT_DIR)/_build
TARGET_DIR	:= $(OUT_DIR)/output

# 头文件路径、源文件、依赖
INCS += -I. $(foreach dir,$(SRC_DIR),-I$(dir))
SRCS = $(wildcard ./*.c $(foreach dir,$(SRC_DIR),$(dir)/*.c))
OBJS = $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRCS))
DEPS = $(OBJS:.o=.d)
VPATH = $(SRC_DIR)


all: $(TARGET)

$(TARGET): $(OBJS)
# 	@echo "[AR] $(TARGET_DIR)/$(TARGET) $(LIBS)"
# 	@$(AR) rcs $(TARGET_DIR)/$(TARGET) $^ $(LIBS)

	@echo "[CC] $(TARGET_DIR)/$(TARGET) $(LIBS)"
	@$(CC) $(LDFLAGS) $^ $(LIBS) -o $(TARGET_DIR)/$(TARGET)

	@echo "\compile success\n"

$(OBJS): $(BUILD_DIR)/%.o: %.c | $(BUILD_DIR) $(TARGET_DIR)
	@echo "[CC] $<"
	@$(CC) $(CFLAGS) $(INCS) -c $< -o $@

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR) $(TARGET_DIR)
	mkdir -p $(foreach dir,$(SRC_DIR),$(BUILD_DIR)/$(dir))

clean:
	rm -rf $(OUT_DIR)

.PHONY: all clean

# include 所有.d文件，使头文件依赖生效
# 如果依赖文件列表不为空, 就直接包含(include)依赖文件列表
ifneq ($(DEPS),)
	include $(DEPS)
endif
