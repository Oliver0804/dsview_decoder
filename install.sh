#!/bin/zsh

# 獲取腳本所在的目錄
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# DSView解碼器目標目錄
DSVIEW_DECODER_DIR="/Applications/DSView.app/Contents/MacOS/decoders"

# 檢查目標目錄是否存在
if [ ! -d "$DSVIEW_DECODER_DIR" ]; then
  echo "目標目錄不存在：$DSVIEW_DECODER_DIR"
  exit 1
fi

# 檢查是否需要提升權限
if [ ! -w "$DSVIEW_DECODER_DIR" ]; then
  echo "目標目錄需要管理員權限。嘗試使用sudo執行。"
  exec sudo "$0" "$@"
fi

# 創建符號鏈接，將所在目錄下的所有子目錄鏈接到目標目錄
for SUBDIR in "$SCRIPT_DIR"/*/; do
  if [ -d "$SUBDIR" ]; then
    LINK_NAME="$DSVIEW_DECODER_DIR/$(basename "$SUBDIR")"
    ln -s "$SUBDIR" "$LINK_NAME"
    if [ $? -eq 0 ]; then
      echo "符號鏈接已成功創建：$LINK_NAME -> $SUBDIR"
    else
      echo "符號鏈接創建失敗：$SUBDIR"
    fi
  fi
done

