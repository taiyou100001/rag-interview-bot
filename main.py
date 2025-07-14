from question_generator import generate_question
from search_engine import ask_next_question, load_questions
import os

if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    print("👋 歡迎使用智慧模擬面試系統！")
    job = input("請輸入應徵職位：")
    resume = input("請簡述履歷重點：")

    # 第一步：LLM 產生第一題
    first_question = generate_question(job, resume)
    print(f"\n📝 第一題：{first_question}")
    answer = input("你的回答（輸入 '退出' 結束）：")
    if answer.lower() == "退出":
        exit()

    # 第二步：進入動態追問流程
    previous_question = first_question
    previous_answer = answer

    try:
        questions = load_questions()
        while True:
            question = ask_next_question(questions, previous_answer, previous_question)
            print(f"\n📝 問題：{question}")
            answer = input("你的回答（輸入 '退出' 結束）：")
            if answer.lower() == "退出":
                print("✅ 面試練習結束。")
                break
            previous_question = question
            previous_answer = answer
    except Exception as e:
        print(f"❌ 錯誤：{str(e)}")
