import os
import json
import sys
import asyncio
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from app.services.tools.rag_retriever import search_and_rerank, retrieve_resume_examples
from app.core.config import settings

# load_dotenv() # Config handles this

class SimpleRAGEvaluator:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.api_url = settings.OPENAI_API_BASE
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_url)

    def evaluate_context_recall(self, question: str, contexts: List[str], ground_truth: str) -> float:
        """
        评估上下文召回率：检索到的上下文是否包含回答问题所需的信息？
        """
        context_text = "\n".join(contexts)
        prompt = f"""
        你是一个严格的评估员。请判断下面的【检索上下文】是否包含了回答【问题】所需的关键信息（参考【标准答案】）。
        
        问题: {question}
        标准答案: {ground_truth}
        检索上下文: {context_text}
        
        请仅输出一个 0 到 1 之间的分数，表示信息的覆盖程度。
        1.0 表示完全包含所有关键信息。
        0.0 表示完全不相关。
        只输出数字，不要解释。
        """
        try:
            resp = self.client.chat.completions.create(
                model="qwen-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            score_str = resp.choices[0].message.content.strip()
            return float(score_str)
        except Exception as e:
            print(f"Error evaluating context recall: {e}")
            return 0.0

    def evaluate_answer_faithfulness(self, question: str, answer: str, contexts: List[str]) -> float:
        """
        评估回答忠实度：生成的回答是否完全基于检索到的上下文？
        """
        context_text = "\n".join(contexts)
        prompt = f"""
        你是一个严格的评估员。请判断下面的【生成回答】是否完全基于【检索上下文】生成，而没有凭空编造信息。
        
        检索上下文: {context_text}
        生成回答: {answer}
        
        请仅输出一个 0 到 1 之间的分数。
        1.0 表示回答完全由上下文支持。
        0.0 表示回答包含大量未在上下文中出现的信息（幻觉）。
        只输出数字，不要解释。
        """
        try:
            resp = self.client.chat.completions.create(
                model="qwen-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            score_str = resp.choices[0].message.content.strip()
            return float(score_str)
        except Exception as e:
            print(f"Error evaluating faithfulness: {e}")
            return 0.0

    def run_evaluation(self, dataset_path: str):
        with open(dataset_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)

        print(f"🚀 Starting RAG Evaluation on {len(dataset)} samples...\n")
        
        total_recall = 0.0
        total_faithfulness = 0.0
        
        for idx, item in enumerate(dataset):
            question = item['question']
            ground_truth = item['ground_truth']
            
            print(f"[{idx+1}/{len(dataset)}] Evaluating: {question}")
            
            # 1. Retrieve Contexts (using the new search_and_rerank function)
            try:
                docs = search_and_rerank(question, top_k=3)
                contexts = [d.get('text', '') or d.get('text_snippet', '') for d in docs]
            except Exception as e:
                print(f"  ❌ Retrieval failed: {e}")
                continue
                
            # 2. Generate Answer
            try:
                answer = retrieve_resume_examples(question, topk=3)
            except Exception as e:
                print(f"  ❌ Generation failed: {e}")
                continue

            # 3. Evaluate
            recall_score = self.evaluate_context_recall(question, contexts, ground_truth)
            faithfulness_score = self.evaluate_answer_faithfulness(question, answer, contexts)
            
            print(f"  - Context Recall: {recall_score}")
            print(f"  - Faithfulness:   {faithfulness_score}")
            print("-" * 30)
            
            total_recall += recall_score
            total_faithfulness += faithfulness_score

        avg_recall = total_recall / len(dataset) if dataset else 0
        avg_faithfulness = total_faithfulness / len(dataset) if dataset else 0
        
        print("\n📊 Evaluation Report")
        print("=" * 30)
        print(f"Average Context Recall:    {avg_recall:.2f}")
        print(f"Average Faithfulness:      {avg_faithfulness:.2f}")
        print("=" * 30)

if __name__ == "__main__":
    evaluator = SimpleRAGEvaluator()
    dataset_file = os.path.join(current_dir, "data", "eval_dataset.json")
    evaluator.run_evaluation(dataset_file)
