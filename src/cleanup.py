# cleanup.py - 清理不需要的檔案
import os
import shutil

def cleanup_project():
    """清理專案中不需要的檔案"""
    
    files_to_remove = [
        'rag_engine.py',  # 已被 knowledge_rag.py 取代
        'test_selectors.py',  # 測試用，不需要
    ]
    
    dirs_to_remove = [
        'data',  # 題庫已被知識庫取代
    ]
    
    print("開始清理專案...")
    
    # 刪除檔案
    for file in files_to_remove:
        if os.path.exists(file):
            os.remove(file)
            print(f"✓ 已刪除: {file}")
    
    # 刪除資料夾
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✓ 已刪除資料夾: {dir_name}")
    
    print("\n清理完成！")

if __name__ == "__main__":
    cleanup_project()