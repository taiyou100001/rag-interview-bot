# main.py (完整版 - 自動偵測 RAG 可用性)
import os
from dotenv import load_dotenv
from database import init_db, authenticate_user, create_user

init_db()
email = input("Email: ")
password = input("Password: ")
user = authenticate_user(email, password)
if not user:
    # 註冊邏輯...
    user = create_user(username=input("Username: "), email=email, password=password)

# 強制從 bin/azure.env 載入（相對於專案根目錄）
project_root = os.path.dirname(os.path.abspath(__file__))  # src/
bin_path = os.path.join(project_root, '..', 'bin', 'azure.env')
load_dotenv(bin_path)

def main():
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    print("=" * 60)
    print("   智慧模擬面試系統")
    print("=" * 60)
    
    # 嘗試初始化 RAG 引擎
    rag_engine = None
    use_rag = False
    
    try:
        print("\n檢查知識庫...")
        # from knowledge_rag import KnowledgeRAGEngine
        # rag_engine = KnowledgeRAGEngine()
        from rag_engine import RAGEngine
        rag_engine = RAGEngine()  # ← 自動載入 + FAISS + Redis 快取
        use_rag = True
        print("✓ 知識庫已載入，使用 RAG 增強模式")
    except ImportError as e:
        print(f"提示: 缺少套件 - {e}")
        print("將使用基礎模式（無 RAG）")
    except Exception as e:
        print(f"提示: 知識庫載入失敗 - {e}")
        print("將使用基礎模式（無 RAG）")
    
    # 讀取履歷
    resume_text = ""
    structured_resume = None
    
    while True:
        print("\n" + "-" * 60)
        resume_path = input("請上傳履歷 (PDF/圖片): ").strip('"')
        
        if not os.path.exists(resume_path):
            print("檔案不存在，請重新輸入")
            continue
        
        try:
            from ocr_processor import OCRProcessor
            
            print("\nOCR 處理中...")
            processor = OCRProcessor()
            success, ocr_result = processor.process_file(resume_path)
            
            if not success:
                raise ValueError(f"OCR 處理失敗: {ocr_result.get('error')}")
            
            # 提取文字
            all_text = []
            for page in ocr_result.get('pages', []):
                if page.get('full_text'):
                    all_text.append(page['full_text'])
            
            if not all_text:
                raise ValueError("無法提取文字內容")
            
            resume_text = "\n".join(all_text)
            print("✓ 履歷讀取成功")
            
            # 嘗試結構化
            try:
                from resume_structurer import structure_resume_from_ocr_json
                structured_resume = structure_resume_from_ocr_json(ocr_result)
                if structured_resume:
                    print(f"✓ 結構化完成 ({len(structured_resume)} 欄位)")
            except ImportError:
                print("提示: 未安裝 spacy，跳過結構化處理")
            except Exception as e:
                print(f"提示: 結構化處理失敗，使用純文字模式")
            
            break
            
        except Exception as e:
            print(f"\n錯誤: {e}")
            retry = input("重試? (Y/N): ").lower()
            if retry != 'y':
                print("結束程式")
                return
    
    # 職位推斷
    from agents import JobInferenceAgent
    
    print("\n" + "-" * 60)
    job_agent = JobInferenceAgent()
    job = job_agent.infer_job_title(resume_text, structured_resume)
    
    # 確認職位
    if job:
        print(f"\n推斷職位: {job}")
        confirm = input("正確嗎? (Y/N): ").lower()
        if confirm != 'y':
            job = input("請輸入正確職位: ").strip()
    else:
        print("\n無法推斷職位")
        job = input("請輸入應徵職位: ").strip()
    
    if not job:
        print("未輸入職位，結束程式")
        return
    
    print("\n" + "=" * 60)
    print(f"   面試職位: {job}")
    if use_rag:
        print(f"   模式: RAG 增強（基於知識庫）")
    else:
        print(f"   模式: 基礎（純 LLM）")
    print("=" * 60)
    print()
    
    # 選擇問題生成器
    if use_rag:
        from agents import KnowledgeBasedQuestionAgent
        question_agent = KnowledgeBasedQuestionAgent(rag_engine)
    else:
        from agents import QuestionGeneratorAgent
        question_agent = QuestionGeneratorAgent()
    
    # 面試循環
    history = []
    count = 0
    
    try:
        while True:
            print("生成問題中...")
            question = question_agent.generate_question(job, resume_text, history)
            
            if not question:
                print("\n無法生成問題，結束面試")
                break
            
            count += 1
            print(f"\n【問題 {count}】")
            print(question)
            print()
            
            answer = input("你的回答 (輸入 '退出' 結束): ").strip()
            
            if answer.lower() in ['退出', 'exit', 'quit', 'q']:
                print(f"\n面試結束，共回答 {count} 題")
                break
            
            if not answer:
                print("未輸入回答，請重新回答")
                count -= 1
                continue
            
            history.append({
                "question": question,
                "answer": answer
            })
            
            # 每 3 題顯示提示
            if count % 3 == 0:
                print(f"\n已完成 {count} 題，繼續加油！")
    
    except KeyboardInterrupt:
        print(f"\n\n面試中斷，共回答 {count} 題")
    except Exception as e:
        print(f"\n發生錯誤: {e}")
        import traceback
        traceback.print_exc()
    
    # 面試結束總結
    print("\n" + "=" * 60)
    print("   面試結束")
    print("=" * 60)
    print(f"職位: {job}")
    print(f"問答輪數: {count}")
    print(f"模式: {'RAG 增強' if use_rag else '基礎'}")
    print("\n感謝使用智慧模擬面試系統！")
    print("=" * 60)


if __name__ == "__main__":
    main()