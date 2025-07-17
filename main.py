# main.py
from question_generator import generate_question, ask_next_question
from search_engine import load_filtered_questions
import os

def main():
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    print("👋 歡迎使用智慧模擬面試系統！")
    job = input("請輸入應徵職位：")
    resume = input("請簡述履歷重點：")

    try:
        questions = load_filtered_questions(job)  # << 使用封裝過的職位過濾功能

        # 使用 LLM 產生第一題
        first_question = generate_question(job, resume)
        print(f"\n📝 第一題：{first_question}")
        answer = input("你的回答（輸入 '退出' 結束）：")
        if answer.lower() == "退出":
            print("✅ 結束面試練習。")
            return

        previous_question = first_question
        previous_answer = answer

        # 問答迴圈
        while True:
            question = ask_next_question(questions, previous_question, previous_answer)
            print(f"\n📝 問題：{question}")
            answer = input("你的回答（輸入 '退出' 結束）：")
            if answer.lower() == "退出":
                print("✅ 結束面試練習。")
                break

            previous_question = question
            previous_answer = answer

    except Exception as e:
        print(f"❌ 發生錯誤：{str(e)}")

if __name__ == "__main__":
    main()
