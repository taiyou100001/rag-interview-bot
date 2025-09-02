# main.py
from question_generator import generate_question, ask_next_question
from feedback_generator import generate_feedback
from search_engine import load_filtered_questions
import os

def main():
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    print("👋 歡迎使用智慧模擬面試系統！")
    job = input("請輸入應徵職位：")
    resume = input("請簡述履歷重點：")

    try:
        questions = load_filtered_questions(job)  # 使用封裝過的職位過濾功能
        if not questions:
            raise ValueError("❌ 無可用的題庫，請檢查資料檔案。")

        # 初始化面試歷史記錄
        interview_history = []

        # 使用 LLM 產生第一題
        first_question = generate_question(job, resume)
        print(f"\n📝 第一題：{first_question}")
        answer = input("你的回答（輸入 '退出' 結束）：")
        if answer.lower() == "退出":
            print("✅ 結束面試練習。")
            return

        interview_history.append((first_question, answer))
        previous_question = first_question
        previous_answer = answer

        # 問答迴圈
        while True:
            question = ask_next_question(questions, previous_question, previous_answer)
            print(f"\n📝 問題：{question}")
            answer = input("你的回答（輸入 '退出' 結束）：")
            if answer.lower() == "退出":
                break

            interview_history.append((question, answer))
            previous_question = question
            previous_answer = answer

        # 面試結束後生成反饋
        if interview_history:
            print("\n🔍 生成面試反饋中...")
            feedback = generate_feedback(job, resume, interview_history)
            print(f"\n📊 面試反饋：\n{feedback}")
        else:
            print("⚠️ 無面試記錄，無法生成反饋。")

        print("✅ 結束面試練習。")

    except Exception as e:
        print(f"❌ 發生錯誤：{str(e)}")

if __name__ == "__main__":
    main()