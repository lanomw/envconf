PREFIX = 
CC = $(PREFIX)gcc
AR = $(PREFIX)ar

CFLAGS := -std=c11 -D_GNU_SOURCE
CFLAGS += -Wall -Wno-unused-function -Wno-unused-variable

SRC_DIR = . # 源码目录
BUILD_DIR = ./build
TARGET_DIR = $(BUILD_DIR)/target # 库编译产物输出目录，cc编译不需要
TARGET = $(TARGET_DIR)/xxx.a # 编译输出产物

INC = $(foreach dir,$(SRC_DIR), -I$(dir))
LIBS = 

SRCS = $(wildcard $(foreach dir, $(SRC_DIR), $(dir)/*.c))
OBJS = $(patsubst %.c, $(BUILD_DIR)/%.o, $(SRCS))

VPATH := $(SRC_DIR)
.PHONY := builddir clean

all: builddir $(TARGET)

builddir:
	@echo "===== mkdir start ====="
	mkdir -p $(TARGET_DIR) # 库编译产物输出，cc编译不需要
	mkdir -p $(foreach dir, $(SRC_DIR), $(BUILD_DIR)/$(dir))
	@echo "===== mkdir end ====="

$(OBJS): $(BUILD_DIR)/%.o: %.c
	@echo "[CC] -c $@ $<"
	@$(CC) $(CFLAGS) $(INC) -c $< -o $@

$(TARGET): $(OBJS)
	@echo "===== build start ====="
	$(AR) rcs $@ $^
	# $(CC) $^ $(LIBS) -o $@
	@echo "===== build end ====="

clean:
	@echo "===== clean start ====="
	rm -rf $(BUILD_DIR)
	@echo "===== clean end ====="
