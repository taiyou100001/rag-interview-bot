import sys
import os

# 將 src 目錄加入系統路徑，這樣測試程式才能 import src 裡的模組
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))