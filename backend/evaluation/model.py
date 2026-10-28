
from langchain_openai import ChatOpenAI
from evaluation.structured_output import JudgeResult
def get_judge_model(JUDGE_MODEL = "gpt-5-mini", temperature = 0.0):
  return ChatOpenAI(model=JUDGE_MODEL, temperature=temperature).with_structured_output(JudgeResult)
