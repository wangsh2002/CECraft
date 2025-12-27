import os
import sys
import json
from openai import OpenAI

# Ensure backend is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

class BusinessValueEvaluator:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.api_url = settings.OPENAI_API_BASE
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_url)
        self.model = settings.LLM_MODEL_PRO

    def evaluate_star_compliance(self, original_text: str, optimized_text: str) -> dict:
        """
        评估 STAR 法则符合度提升
        """
        prompt = f"""
        你是一个资深招聘专家。请对比【修改前】和【修改后】的简历片段，评估其对 STAR 法则 (Situation, Task, Action, Result) 的符合程度。
        
        修改前: {original_text}
        修改后: {optimized_text}
        
        请分别给两者打分 (1-5分)，并简要说明理由。
        
        输出格式 (JSON):
        {{
            "original_score": <float>,
            "optimized_score": <float>,
            "improvement_percentage": <float>, // (optimized - original) / original * 100
            "reason": "<string>"
        }}
        """
        return self._get_json_result(prompt)

    def evaluate_jd_match(self, jd_text: str, resume_text: str) -> float:
        """
        评估简历与 JD 的匹配度
        """
        prompt = f"""
        你是一个招聘系统。请评估下面的【简历内容】与【岗位描述 (JD)】的匹配程度。
        重点关注技能关键词、经验要求和软技能的覆盖率。
        
        岗位描述: {jd_text}
        简历内容: {resume_text}
        
        请打分 (0.0 到 1.0)，1.0 表示完美匹配。
        仅输出数字。
        """
        return self._get_score(prompt)

    def _get_score(self, prompt: str) -> float:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            score_str = resp.choices[0].message.content.strip()
            import re
            match = re.search(r"(\d+(\.\d+)?)", score_str)
            if match:
                return float(match.group(1))
            return 0.0
        except Exception as e:
            print(f"Error in evaluation: {e}")
            return 0.0

    def _get_json_result(self, prompt: str) -> dict:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            print(f"Error in json evaluation: {e}")
            return {"original_score": 0, "optimized_score": 0, "improvement_percentage": 0, "reason": "Error"}
