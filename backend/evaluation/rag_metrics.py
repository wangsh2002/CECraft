import os
import sys
from typing import List
from openai import OpenAI

# Ensure backend is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

class RAGEvaluator:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.api_url = settings.OPENAI_API_BASE
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_url)
        self.model = settings.LLM_MODEL_PRO  # Use a capable model for judging

    def evaluate_faithfulness(self, question: str, contexts: List[str], answer: str) -> float:
        """
        评估忠实度：生成的回答是否完全基于检索到的上下文？(避免幻觉)
        """
        context_text = "\n".join(contexts)
        prompt = f"""
        你是一个事实核查员。请判断下面的【回答】是否与【检索上下文】（包含参考资料和用户原始信息）保持一致。
        
        评估标准：
        1. 如果回答中的关键事实（如技能、经历、数据）在上下文中能找到依据，得高分。
        2. 允许对语言进行润色、总结和逻辑重组，这不算幻觉。
        3. 如果回答编造了上下文中完全不存在的虚假事实（如捏造了未提及的项目或技能），得低分。
        
        问题: {question}
        检索上下文: {context_text}
        回答: {answer}
        
        请打分 (0.0 到 1.0)：
        1.0: 事实完全忠实于上下文，仅作了合理的润色。
        0.0: 包含严重的虚构事实。
        
        仅输出数字。
        """
        return self._get_score(prompt)

    def evaluate_answer_relevance(self, question: str, answer: str) -> float:
        """
        评估相关性：回答是否直接解决了用户的问题？
        """
        prompt = f"""
        你是一个评估员。请判断下面的【回答】是否切题且有帮助地回答了【问题】。
        
        问题: {question}
        回答: {answer}
        
        请打分 (0.0 到 1.0)：
        1.0: 回答非常切题且完整。
        0.0: 回答完全不相关或没有回答问题。
        
        仅输出数字。
        """
        return self._get_score(prompt)

    def evaluate_context_recall(self, question: str, contexts: List[str], ground_truth: str) -> float:
        """
        评估召回率：检索到的上下文是否包含标准答案所需的信息？
        """
        context_text = "\n".join(contexts)
        prompt = f"""
        你是一个评估员。请判断下面的【检索上下文】是否包含了回答【问题】所需的关键信息（参考【标准答案】）。
        
        问题: {question}
        标准答案: {ground_truth}
        检索上下文: {context_text}
        
        请打分 (0.0 到 1.0)：
        1.0: 上下文包含所有关键信息。
        0.0: 上下文完全不相关。
        
        仅输出数字。
        """
        return self._get_score(prompt)

    def calculate_mrr(self, question: str, contexts: List[str], ground_truth: str) -> float:
        """
        计算 MRR (Mean Reciprocal Rank): 正确答案在检索列表中的倒数排名。
        如果第一个文档就相关，MRR=1.0；第二个相关，MRR=0.5；都不相关，MRR=0.0。
        """
        for i, context in enumerate(contexts):
            # 简化版：只要该文档包含 ground_truth 的关键信息，就认为命中
            # 这里为了效率，我们只检查 Top-3，且使用 LLM 快速判断单条相关性
            prompt = f"""
            判断下面的【文档】是否包含回答【问题】所需的关键信息（参考【标准答案】）。
            
            问题: {question}
            标准答案: {ground_truth}
            文档: {context}
            
            是则输出 "YES"，否则输出 "NO"。
            """
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0
                )
                if "YES" in resp.choices[0].message.content.strip().upper():
                    return 1.0 / (i + 1)
            except:
                continue
        return 0.0

    def _get_score(self, prompt: str) -> float:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            score_str = resp.choices[0].message.content.strip()
            # Debug: print raw score
            # print(f"DEBUG: Raw score output: {score_str}")
            
            import re
            match = re.search(r"(\d+(\.\d+)?)", score_str)
            if match:
                val = float(match.group(1))
                # Normalize if model outputs 0-100 instead of 0-1
                if val > 1.0: val = val / 100.0
                if val > 1.0: val = 1.0 # Cap at 1.0
                return val
            return 0.0
        except Exception as e:
            print(f"Error in evaluation: {e}")
            return 0.0
