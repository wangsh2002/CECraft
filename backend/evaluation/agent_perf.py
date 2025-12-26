import os
import sys
import time
import asyncio
import json
from typing import List, Dict

# Ensure backend is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mocking the agent workflow for testing if not fully importable, 
# but ideally we import the actual workflow.
# Assuming we can import the supervisor or workflow entry point.
from app.services.agent_workflow import run_agent_workflow

class AgentPerformanceEvaluator:
    def __init__(self):
        pass

    async def evaluate_intent_accuracy(self, test_cases: List[Dict]) -> Dict:
        """
        评估意图识别准确率
        test_cases: [{"input": "...", "expected_intent": "research_consult"}, ...]
        """
        correct = 0
        total = len(test_cases)
        results = []

        print(f"Starting Intent Accuracy Test on {total} cases...")

        for case in test_cases:
            start_time = time.time()
            try:
                # 这里我们需要一种方式只运行 Supervisor 或者从完整工作流结果中提取意图
                # 假设 run_agent_workflow 返回完整状态，其中包含意图
                # 为了简化，我们假设 run_agent_workflow 的输出包含 'intent' 或 'next_agent'
                
                # 注意：实际调用可能需要根据 agent_workflow.py 的具体签名调整
                # 这里假设 run_agent_workflow(user_input, context) -> dict
                result = await run_agent_workflow(case["input"], case.get("context", {}))
                
                # 假设 result 结构中有意图信息，这里需要根据实际 agent_workflow.py 的返回调整
                # 如果 agent_workflow 返回的是最终结果，我们可能需要 hack 一下或者
                # 专门暴露 supervisor 的测试接口。
                # 暂时假设 result['metadata']['intent'] 或类似结构
                # 如果没有，我们可能需要修改 agent_workflow.py 来返回中间状态
                
                # 临时方案：检查返回结果的类型或日志 (模拟)
                # 在实际项目中，建议将 Supervisor 逻辑解耦出来单独测试
                # 这里我们假设 result 包含 'intent' 字段
                predicted_intent = result.get("intent", "unknown") 
                
                is_correct = predicted_intent == case["expected_intent"]
                if is_correct:
                    correct += 1
                
                latency = time.time() - start_time
                results.append({
                    "input": case["input"],
                    "expected": case["expected_intent"],
                    "predicted": predicted_intent,
                    "correct": is_correct,
                    "latency": latency
                })
            except Exception as e:
                print(f"Error processing case {case['input']}: {e}")
                results.append({
                    "input": case["input"],
                    "error": str(e),
                    "correct": False
                })

        accuracy = correct / total if total > 0 else 0
        avg_latency = sum(r.get("latency", 0) for r in results) / total if total > 0 else 0
        
        return {
            "accuracy": accuracy,
            "avg_latency": avg_latency,
            "details": results
        }

    async def evaluate_format_compliance(self, test_cases: List[Dict]) -> float:
        """
        评估输出格式合规率 (是否为有效的 Delta/JSON)
        """
        valid_count = 0
        total = len(test_cases)
        
        for case in test_cases:
            try:
                result = await run_agent_workflow(case["input"], case.get("context", {}))
                # 检查 result 是否包含 content 且 content 是否为有效格式
                # 假设 result['content'] 应该是 Delta 格式的 JSON
                content = result.get("content")
                if isinstance(content, (dict, list)): # 已经是 JSON 对象
                    valid_count += 1
                elif isinstance(content, str):
                    json.loads(content) # 尝试解析
                    valid_count += 1
            except Exception:
                pass
                
        return valid_count / total if total > 0 else 0.0
