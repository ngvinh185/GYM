import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from langsmith import evaluate, Client
from student_assitant.assitant import Graph

from evaluation.model import get_judge_model
from evaluation.eval_prompt import EVAL_PROMPT
# 1. Create and/or select your dataset
client = Client()
dataset_name = "gym_vrs_dataset_sample_filled"


model = get_judge_model()

import re

def build_prompt(template: str, **values) -> str:
    for key, val in values.items():
        if isinstance(val, list):
            val = " -> ".join(map(str, val)) if val else "(không có)"
        elif val in ("", None):
            val = "(không có)"
        template = template.replace("{{" + key + "}}", str(val))
    missing = set(re.findall(r"\{\{(\w+)\}\}", template))
    assert not missing, f"Thiếu placeholder: {missing}"
    return template

def evaluator(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    prompt = build_prompt(
        EVAL_PROMPT,
        user_role=inputs.get("user_role", "user"),
        user_id=inputs.get("user_id", "CHƯA XÁC ĐỊNH"),
        messages=inputs.get("messages", ""),
        expected_subagent=reference_outputs.get("subagent", []),
        expected_order=reference_outputs.get("sql_traces", []),
        expected_response=reference_outputs.get("response", ""),
        actual_subagent=outputs.get("subagent", []),
        actual_order=outputs.get("sql_traces", []),
        actual_response=outputs.get("response", ""),
    )
    result = model.invoke(prompt)
    comment = f"{result.verdict} | {result.reasoning} | errors: {result.errors}"
    return {"results": [
        {"key": "routing", "score": result.routing},
        {"key": "tool_order", "score": result.tool_order},
        {"key": "correctness", "score": result.correctness},
        {"key": "safety", "score": result.safety},
        {"key": "format", "score": result.format},
        {"key": "overall", "score": result.overall, "comment": comment},
    ]}


def target(inputs: dict) -> dict:
    graph = Graph(
        user_role=inputs.get("user_role", "user").upper(),
        user_id=inputs.get("user_id", "CHƯA XÁC ĐỊNH"),
    )
    result = graph.invoke(inputs.get("messages", ""), thread_id=str(uuid.uuid4()))
    msgs = result.get("messages", [])
    return {
        "response": msgs[-1].content if msgs else "",
        "sql_traces": result['sql_traces'],
        "subagent": result['subagent_call'],
    }


if __name__ == "__main__":
  # 2. Evaluate the dataset
  evaluation = evaluate(
    target,
    data=dataset_name,
    evaluators=[evaluator],
    client=client,
    experiment_prefix="gym_vrs_evaluation",
    max_concurrency=1,
)

  # 3. Print the evaluation results
  print("Evaluation Results:")
  print(evaluation)