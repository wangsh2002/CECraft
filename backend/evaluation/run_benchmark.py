import asyncio
import os
import sys
import json
import time
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI

# Ensure backend is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.rag_metrics import RAGEvaluator
from evaluation.business_value import BusinessValueEvaluator
# from evaluation.agent_perf import AgentPerformanceEvaluator # 需要异步环境，暂时在 main 中处理

# 导入系统核心功能
from app.services.tools.rag_retriever import search_and_rerank
from app.services.agent_workflow import run_agent_workflow, llm_service
from app.core.config import settings

# load_dotenv() # Config handles this

class BenchmarkRunner:
    def __init__(self):
        self.rag_evaluator = RAGEvaluator()
        self.biz_evaluator = BusinessValueEvaluator()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_API_BASE)
        self.model = settings.LLM_MODEL_PRO

    async def run_baseline(self, prompt: str, context: str = "") -> str:
        """
        Baseline: 直接问大模型 (Zero-shot), 不查库
        """
        messages = [
            {"role": "system", "content": "你是一个简历助手。请根据用户指令修改简历。"},
            {"role": "user", "content": f"用户指令: {prompt}\n简历内容: {context}"}
        ]
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        return resp.choices[0].message.content

    async def run_system(self, prompt: str, context: dict) -> str:
        """
        System: 我们的 RAG + Agent 系统
        """
        # 调用 agent_workflow
        result = await run_agent_workflow(prompt, context)
        # 假设 result 返回结构包含 'content' (修改后的文本)
        # 如果 result 是 dict 且包含 'content'
        if isinstance(result, dict) and "content" in result:
            # 如果 content 是 Delta 格式 (list/dict)，转为 string 用于评估
            return str(result["content"])
        return str(result)

    async def run_benchmark(self, test_dataset_path: str):
        print(f"Loading dataset from {test_dataset_path}...")
        with open(test_dataset_path, 'r') as f:
            dataset = json.load(f)

        results = {
            "rag_metrics": {"hit_rate": [], "faithfulness": [], "relevance": [], "mrr": []},
            "business_metrics": {"star_improvement": [], "jd_match_improvement": []},
            "agent_eval_metrics": {"pre_score": [], "post_score": [], "score_improvement": []},
            "performance_metrics": {"latency": [], "intent_accuracy": []},
            "win_rate": {"system_wins": 0, "baseline_wins": 0, "ties": 0}
        }

        print("Starting Benchmark...")
        
        for i, item in enumerate(dataset):
            print(f"\n--- Processing Case {i+1}/{len(dataset)} ---")
            question = item.get("question", "") or item.get("instruction", "")
            ground_truth = item.get("ground_truth", "")
            resume_context = item.get("resume_context", {}) # 原始简历片段
            resume_text_raw = json.dumps(resume_context, ensure_ascii=False)
            target_type = item.get("type", "")
            
            # 1. RAG 评估 (如果有 ground_truth)
            # 手动触发检索以评估 RAG 质量
            retrieved_docs = await asyncio.to_thread(search_and_rerank, question)
            
            # Debug: Check retrieval
            if not retrieved_docs:
                print(f"⚠️ [Warning] No docs retrieved for query: {question}")
                print("  -> Did you run 'python ingest_rag.py --source data/resumes_crawled'?")
            else:
                print(f"✅ [Info] Retrieved {len(retrieved_docs)} docs. Top 1 snippet: {retrieved_docs[0].get('text', '')[:50]}...")

            contexts = [doc.get('text', '') for doc in retrieved_docs]
            
            if ground_truth:
                recall = self.rag_evaluator.evaluate_context_recall(question, contexts, ground_truth)
                mrr = self.rag_evaluator.calculate_mrr(question, contexts, ground_truth)
                results["rag_metrics"]["hit_rate"].append(recall)
                results["rag_metrics"]["mrr"].append(mrr)
                print(f"RAG Recall: {recall}, MRR: {mrr}")

            # 2. 生成结果对比 (Baseline vs System) & 性能评估
            baseline_output = await self.run_baseline(question, resume_text_raw)
            
            # 计时开始
            start_time = time.time()
            # 运行系统并获取完整结果（包含 Agent 内部评估分数）
            system_result_full = await run_agent_workflow(question, resume_context)
            # 计时结束
            latency = time.time() - start_time
            results["performance_metrics"]["latency"].append(latency)
            print(f"Latency: {latency:.2f}s")
            
            # 意图识别评估
            predicted_intent = system_result_full.get("intent", "")
            is_intent_correct = False
            if target_type == "consult" and predicted_intent in ["research_consult", "chat"]:
                is_intent_correct = True
            elif target_type == "modify" and predicted_intent in ["modify", "research_modify"]:
                is_intent_correct = True
            
            results["performance_metrics"]["intent_accuracy"].append(1 if is_intent_correct else 0)
            print(f"Intent: {predicted_intent} (Expected: {target_type}) -> {'✅' if is_intent_correct else '❌'}")

            # 提取内容
            if isinstance(system_result_full.get("content"), (dict, list)):
                system_output = json.dumps(system_result_full["content"], ensure_ascii=False)
            else:
                system_output = str(system_result_full.get("content", ""))

            # 3. Agent 内部评估分数对比 (Pre vs Post)
            # 模拟：假设原始简历分数为 60 (Baseline)，Agent 评估后的分数为 system_result_full.get('evaluation', {}).get('score')
            # 如果 Agent 流程中没有返回 evaluation，我们手动调用一次 Review Agent
            
            # Pre-Score: 对原始简历打分
            pre_eval = await llm_service.process_review_request(resume_text_raw)
            pre_score = pre_eval.get("score", 60)
            
            # Post-Score: 对修改后简历打分
            post_eval = await llm_service.process_review_request(system_output)
            post_score = post_eval.get("score", 0)
            
            results["agent_eval_metrics"]["pre_score"].append(pre_score)
            results["agent_eval_metrics"]["post_score"].append(post_score)
            results["agent_eval_metrics"]["score_improvement"].append(post_score - pre_score)
            print(f"Agent Eval Score: {pre_score} -> {post_score} (Diff: {post_score - pre_score})")

            # 4. RAG 生成质量评估 (Faithfulness & Relevance)
            # [改进] 对于 Modify 任务，原始简历也是合法的信息来源，不应被视为幻觉
            # 将原始简历加入到上下文列表中进行评估
            eval_contexts = contexts.copy()
            if resume_text_raw and resume_text_raw != "{}":
                eval_contexts.append(f"【用户原始简历信息】: {resume_text_raw}")

            faithfulness = self.rag_evaluator.evaluate_faithfulness(question, eval_contexts, system_output)
            relevance = self.rag_evaluator.evaluate_answer_relevance(question, system_output)
            results["rag_metrics"]["faithfulness"].append(faithfulness)
            results["rag_metrics"]["relevance"].append(relevance)
            print(f"Faithfulness: {faithfulness}, Relevance: {relevance}")

            # 5. 业务价值评估 (STAR & JD Match)
            # 假设这是一个简历修改任务
            if "modify" in item.get("type", "modify"):
                star_eval = self.biz_evaluator.evaluate_star_compliance(resume_text_raw, system_output)
                results["business_metrics"]["star_improvement"].append(star_eval.get("improvement_percentage", 0))
                print(f"STAR Improvement: {star_eval.get('improvement_percentage', 0)}%")

            # 6. Win Rate (LLM-as-a-Judge)
            winner = self.judge_winner(question, baseline_output, system_output)
            if winner == "system":
                results["win_rate"]["system_wins"] += 1
            elif winner == "baseline":
                results["win_rate"]["baseline_wins"] += 1
            else:
                results["win_rate"]["ties"] += 1
            print(f"Winner: {winner}")

        self.print_report(results)

    def judge_winner(self, question: str, baseline_ans: str, system_ans: str) -> str:
        prompt = f"""
        请对比两个 AI 助手对用户指令的执行结果，选出更好的一个。
        
        用户指令: {question}
        
        【助手 A (Baseline)】:
        {baseline_ans}
        
        【助手 B (System)】:
        {system_ans}
        
        请评价哪个更好。
        如果 B 明显更好（更专业、更符合指令、使用了外部知识），输出 "system"。
        如果 A 更好，输出 "baseline"。
        如果差不多，输出 "tie"。
        仅输出一个单词。
        """
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            content = resp.choices[0].message.content.strip().lower()
            if "system" in content: return "system"
            if "baseline" in content: return "baseline"
            return "tie"
        except:
            return "tie"

    def print_report(self, results):
        total = len(results["rag_metrics"]["hit_rate"])
        if total == 0:
            print("No data to report.")
            return

        avg_hit_rate = sum(results["rag_metrics"]["hit_rate"]) / total
        avg_mrr = sum(results["rag_metrics"]["mrr"]) / total
        avg_faithfulness = sum(results["rag_metrics"]["faithfulness"]) / total
        avg_relevance = sum(results["rag_metrics"]["relevance"]) / total
        
        avg_star_imp = 0
        if results["business_metrics"]["star_improvement"]:
            avg_star_imp = sum(results["business_metrics"]["star_improvement"]) / len(results["business_metrics"]["star_improvement"])

        avg_pre_score = sum(results["agent_eval_metrics"]["pre_score"]) / len(results["agent_eval_metrics"]["pre_score"])
        avg_post_score = sum(results["agent_eval_metrics"]["post_score"]) / len(results["agent_eval_metrics"]["post_score"])
        avg_score_imp = sum(results["agent_eval_metrics"]["score_improvement"]) / len(results["agent_eval_metrics"]["score_improvement"])

        avg_latency = sum(results["performance_metrics"]["latency"]) / len(results["performance_metrics"]["latency"])
        avg_intent_acc = sum(results["performance_metrics"]["intent_accuracy"]) / len(results["performance_metrics"]["intent_accuracy"])

        wins = results["win_rate"]["system_wins"]
        ties = results["win_rate"]["ties"]
        losses = results["win_rate"]["baseline_wins"]
        total_battles = wins + ties + losses
        win_rate = (wins / total_battles) * 100 if total_battles > 0 else 0

        report = f"""
        ================================================
        🏆 CECraft System Benchmark Report
        ================================================
        
        1. RAG Core Metrics (检索与生成)
        ------------------------------------------------
        - Context Recall (Hit Rate): {avg_hit_rate:.2f}
        - MRR (Mean Reciprocal Rank):{avg_mrr:.2f}
        - Faithfulness:              {avg_faithfulness:.2f}
        - Answer Relevance:          {avg_relevance:.2f}
        
        2. Agent Quality Metrics (简历质量评分)
        ------------------------------------------------
        - Pre-Optimization Score:    {avg_pre_score:.1f}
        - Post-Optimization Score:   {avg_post_score:.1f}
        - Average Score Improvement: +{avg_score_imp:.1f} pts
        
        3. Business Value (业务指标)
        ------------------------------------------------
        - Avg STAR Score Improvement: +{avg_star_imp:.1f}%
        
        4. Engineering Performance (工程指标) <-- 新增！
        ------------------------------------------------
        - Avg End-to-End Latency:    {avg_latency:.2f}s
        - Intent Recognition Acc:    {avg_intent_acc*100:.1f}%
        
        5. System vs Baseline (胜率)
        ------------------------------------------------
        - System Win Rate:           {win_rate:.1f}%
        - Record (W-L-T):            {wins}-{losses}-{ties}
        
        ================================================
        """
        print(report)
        # Save report
        with open("benchmark_report.txt", "w") as f:
            f.write(report)

if __name__ == "__main__":
    runner = BenchmarkRunner()
    # 假设数据在 backend/data/benchmark_dataset.json
    dataset_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "benchmark_dataset.json")
    asyncio.run(runner.run_benchmark(dataset_path))
