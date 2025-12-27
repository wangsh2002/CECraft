import asyncio
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# 1) 配置 Python 路径：确保能 import app.*
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)


try:
    from app.services.agent_workflow import llm_service
    from langchain_core.messages import HumanMessage
except Exception as e:
    print("错误：无法导入 app 模块或初始化配置失败。请确保在 backend 目录下运行，且 backend/.env 配置正确。")
    print(f"详细错误: {e}")
    raise


INTENTS: Tuple[str, ...] = (
    "chat",
    "modify",
    "research_consult",
    "research_modify",
)

RESEARCH_MODIFY_TOOLS: Tuple[str, ...] = (
    "web",
    "rag",
    "both",
)


@dataclass(frozen=True)
class Case:
    expected: str
    prompt: str
    expected_tool: Optional[str] = None


def build_cases() -> List[Case]:
    """每个意图 10 条样例；research_modify 细分 web/rag/both 各 10 条。

    注意：
    - 大类用 Supervisor 输出的 next_agent。
    - 当 next_agent == research_modify 时，再用 ToolRouter 选择 web/rag/both。
    """

    # chat：闲聊/功能询问/通用建议（不要求搜索、不要求改简历）
    chat_prompts = [
        "你好，你是谁？能做什么？",
        "你能简单介绍一下怎么写一份好简历吗？",
        "我最近有点焦虑，找工作该怎么规划？",
        "面试时如何自我介绍更自然？给我一个通用模板。",
        "我想从后端转前端，你觉得可行吗？",
        "你觉得简历最重要的三点是什么？",
        "请给我一些职业发展建议：3年后端如何进阶？",
        "你能解释一下 STAR 法则是什么吗？",
        "你支持哪些格式的简历内容？",
        "我应该如何选择城市：北京还是上海？",
    ]

    # modify：明确的文本润色/改写/翻译/纠错（不强调对标市场/JD/调研）
    modify_prompts = [
        "把这句话润色得更专业：我负责写代码，修bug，维护服务器。",
        "把这段经历改短一些（两句话以内）：主导接口开发，优化数据库查询，提升响应速度。",
        "请纠正错别字并优化表达：我熟悉pyhton和flask，能独立完成接口开发。",
        "把下面内容翻译成英文：熟悉 Python、FastAPI，负责过支付系统的开发与维护。",
        "帮我把语气改得更自信：我可能做过一些性能优化。",
        "把这段话改成要点列表：搭建CI/CD；监控报警；容器化部署。",
        "帮我把这段描述改成更有冲击力但不夸张：优化查询性能，减少线上超时。",
        "把下面这句话改成更正式：我会用Redis。",
        "请把这段话按技术栈拆分并润色：做过微服务，消息队列，缓存和日志系统。",
        "将以下内容改写成简历风格：我在学校做过很多项目，学到了很多东西。",
    ]

    # research_consult：只想查信息（薪资/面试题/公司/行业趋势），不要求改简历
    research_consult_prompts = [
        "帮我查一下 2025 年上海 Python 后端工程师的薪资范围。",
        "请调研一下现在大厂对 DevOps 工程师的核心要求有哪些？",
        "字节跳动后端面试一般会考哪些题型？",
        "2025 年数据分析师的主流技能栈是什么？",
        "帮我搜集一下 AI Agent 岗位的典型职责和常见技能要求。",
        "现在 Java 高级工程师的行情怎么样？大概多少薪资？",
        "请查一下 Spring Boot 面试高频题有哪些，并简单归类。",
        "最近两年前端岗位更看重哪些能力？",
        "帮我了解一下‘大模型算法工程师’常用的技术栈和方向。",
        "请调研一下外企和互联网公司简历风格差异有哪些？",
    ]

    # research_modify：要利用调研/JD/范例来改简历（对标、根据要求优化、参考等）
    # ToolRouter 语义（见 graph_workflow.py）：
    # - web: 公司/JD/市场/实时信息
    # - rag: 简历写作技巧、STAR范例、内部知识
    # - both: 二者都需要

    research_modify_web_prompts = [
        "根据字节跳动后端 JD 的要求（可以先查一下核心能力点），帮我重写这段项目经历：负责订单系统开发。",
        "请先搜索一下 2025 年‘AI Agent 工程师’岗位 JD 的常见关键词，再据此优化我的技能描述：熟悉 Python、LangChain。",
        "对标阿里云 DevOps 岗位要求（先查 JD），优化我的简历要点：负责发布流程。",
        "先查一下美团后端工程师常见面试/能力要求，然后把我这段经历改得更贴合：做过接口开发。",
        "请调研一下外企（例如微软/谷歌）SWE 简历写法偏好，再按那个风格改写：做过微服务项目。",
        "先查一下 2025 年上海 Python 后端的主流技术要求，然后据此优化我的技能栈：会 FastAPI、Redis。",
        "根据最新行业对数据分析师的要求（请先调研），改写我的技能清单：SQL、Excel、Python。",
        "先查一下大模型算法工程师 JD 常见要求，再对标改写我的项目亮点：训练过分类模型。",
        "请先搜索一下前端高级工程师岗位常见要求，再据此改写我的项目经历：做过中后台性能优化。",
        "对标某头部互联网公司后端 JD（先查要求），优化我的自我评价：熟悉分布式与高并发。",
    ]

    research_modify_rag_prompts = [
        "参考 STAR 法则，把这段经历重写得更专业：负责订单系统开发。",
        "请参考优秀简历常用表达，润色这段经历并输出更强动词：负责接口开发与维护。",
        "用 STAR 法则把这段项目经历改写成 3 条要点：做过性能优化。",
        "参考简历写作模板，把这段描述写得更量化：优化了系统响应速度。",
        "请参考常见的‘项目背景-职责-结果’写法，改写：参与微服务改造。",
        "参考面向招聘官的写法，把这段经历改成更有说服力：修复线上 bug，保障稳定性。",
        "用简历范文的风格，把这段经历改成更专业：负责服务器维护。",
        "参考常见技术简历的措辞，改写这段技能描述：会 Python、Redis、MySQL。",
        "请参考 STAR 范例，把这段经历补全背景/行动/结果：做过日志系统。",
        "参考优秀案例，把这段经历改成更清晰的 2-3 条 bullet：做过 CI/CD。",
    ]

    research_modify_both_prompts = [
        "先查一下 AI Agent 岗位 JD 的核心技能点，再结合 STAR 法则重写这段经历：做过聊天机器人。",
        "请先调研 2025 年资深前端常见要求，再参考大厂简历写法改写我的项目亮点：做过中后台。",
        "先搜集 Python 后端高并发常见关键词，再参考优秀范例把这段经历写得更量化：优化了接口性能。",
        "请先查一下数据分析师岗位主流技能栈，再按简历范文的风格改写我的技能描述：会 SQL、Excel。",
        "先搜索外企简历风格差异，再参考 STAR 模板重写：主导微服务改造。",
        "先查一下 DevOps 关键词（IaC、可观测性、CI/CD），再参考优秀简历措辞改写：维护发布流程。",
        "请先调研大模型算法工程师常用技术栈，再参考大厂简历写法优化：熟悉 PyTorch。",
        "先查一下某大厂后端 JD 的要求，再用 STAR 法则重写：负责订单系统开发。",
        "请先搜索高级 Python 后端要求，再参考简历范文重写：做过支付系统开发与维护。",
        "先调研前端岗位趋势，再参考优秀范例把我的项目经历写得更专业：做过性能优化。",
    ]

    buckets: Dict[str, List[str]] = {
        "chat": chat_prompts,
        "modify": modify_prompts,
        "research_consult": research_consult_prompts,
    }

    for intent in INTENTS:
        if intent == "research_modify":
            continue
        if intent not in buckets:
            raise ValueError(f"Missing intent bucket: {intent}")
        if len(buckets[intent]) != 10:
            raise ValueError(f"Intent '{intent}' needs 10 examples, got {len(buckets[intent])}")

    if len(research_modify_web_prompts) != 10:
        raise ValueError(f"research_modify:web needs 10 examples, got {len(research_modify_web_prompts)}")
    if len(research_modify_rag_prompts) != 10:
        raise ValueError(f"research_modify:rag needs 10 examples, got {len(research_modify_rag_prompts)}")
    if len(research_modify_both_prompts) != 10:
        raise ValueError(f"research_modify:both needs 10 examples, got {len(research_modify_both_prompts)}")

    cases: List[Case] = []
    for intent in INTENTS:
        if intent == "research_modify":
            continue
        for prompt in buckets[intent]:
            cases.append(Case(expected=intent, prompt=prompt))

    for prompt in research_modify_web_prompts:
        cases.append(Case(expected="research_modify", expected_tool="web", prompt=prompt))
    for prompt in research_modify_rag_prompts:
        cases.append(Case(expected="research_modify", expected_tool="rag", prompt=prompt))
    for prompt in research_modify_both_prompts:
        cases.append(Case(expected="research_modify", expected_tool="both", prompt=prompt))

    return cases


async def classify(prompt: str) -> str:
    decision = await llm_service.process_supervisor_request(prompt, history=[])
    # Supervisor 输出字段是 next_agent
    predicted = (decision.get("next_agent") or "").strip()
    return predicted


async def choose_tool(query: str) -> str:
    """复用 graph_workflow.py 中的 ToolRouter prompt，输出 web/rag/both。"""

    router_prompt = (
        f"Analyze the following query and decide which tool to use.\n"
        f"Query: {query}\n\n"
        f"Tools:\n"
        f"1. 'web': For specific company info, JD (Job Description), market data, real-time info.\n"
        f"2. 'rag': For resume writing tips, STAR method examples, standard phrases, internal knowledge.\n"
        f"3. 'both': If both are needed.\n\n"
        f"Return only one word: 'web', 'rag', or 'both'."
    )

    try:
        router_response = await llm_service.llm.ainvoke([HumanMessage(content=router_prompt)])
        tool_choice = (router_response.content or "").strip().lower()
    except Exception:
        tool_choice = "both"

    if tool_choice not in RESEARCH_MODIFY_TOOLS:
        tool_choice = "both"
    return tool_choice


def _pct(n: int, d: int) -> str:
    if d == 0:
        return "0.00%"
    return f"{(n / d) * 100:.2f}%"


async def main():
    cases = build_cases()

    total = 0
    correct_combined = 0

    # 大类准确率（只看 next_agent）
    correct_top = 0

    per_label_total: Dict[str, int] = defaultdict(int)
    per_label_correct: Dict[str, int] = defaultdict(int)

    per_top_total: Dict[str, int] = defaultdict(int)
    per_top_correct: Dict[str, int] = defaultdict(int)

    sub_total = 0
    sub_correct = 0
    per_tool_total: Dict[str, int] = defaultdict(int)
    per_tool_correct: Dict[str, int] = defaultdict(int)

    confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    print("========================================")
    print("🧪 意图分类准确率评测")
    print("- 大类：Supervisor 输出 next_agent（chat/modify/research_consult/research_modify）")
    print("- 子类：当 next_agent=research_modify 时，ToolRouter 细分 web/rag/both")
    print("========================================")

    for idx, case in enumerate(cases, start=1):
        decision = await llm_service.process_supervisor_request(case.prompt, history=[])
        predicted_top = (decision.get("next_agent") or "").strip()
        predicted_tool: Optional[str] = None

        if predicted_top == "research_modify":
            query = (decision.get("search_query") or "").strip() or case.prompt
            predicted_tool = await choose_tool(query)

        expected_top = case.expected
        expected_tool = case.expected_tool

        expected_label = expected_top
        predicted_label = predicted_top
        if expected_top == "research_modify":
            expected_label = f"research_modify:{expected_tool}"
        if predicted_top == "research_modify":
            predicted_label = f"research_modify:{predicted_tool}"

        total += 1
        per_label_total[expected_label] += 1
        confusion[expected_label][predicted_label] += 1

        per_top_total[expected_top] += 1

        ok_top = predicted_top == expected_top
        if ok_top:
            correct_top += 1
            per_top_correct[expected_top] += 1

        ok_combined = predicted_label == expected_label
        if ok_combined:
            correct_combined += 1
            per_label_correct[expected_label] += 1

        if expected_top == "research_modify":
            sub_total += 1
            if predicted_top == "research_modify":
                per_tool_total[expected_tool or ""] += 1
                if predicted_tool == expected_tool:
                    sub_correct += 1
                    per_tool_correct[expected_tool or ""] += 1

        status = "✅" if ok_combined else "❌"
        exp_show = expected_label
        pred_show = predicted_label
        print(f"[{idx:02d}/{len(cases)}] {status} 期望={exp_show:<22} 预测={pred_show:<22} | {case.prompt}")

    print("\n----------------------------------------")
    print(f"总体正确率(大类): {correct_top}/{total} = {_pct(correct_top, total)}")
    print(f"总体正确率(大类+子类): {correct_combined}/{total} = {_pct(correct_combined, total)}")

    print("\n分大类正确率:")
    for intent in INTENTS:
        c = per_top_correct[intent]
        t = per_top_total[intent]
        print(f"- {intent:<15}: {c:02d}/{t:02d} = {_pct(c, t)}")

    print("\nresearch_modify 子类正确率 (仅在期望为 research_modify 的样例上统计):")
    print(f"- 子类总体: {sub_correct}/{sub_total} = {_pct(sub_correct, sub_total)}")
    for tool in RESEARCH_MODIFY_TOOLS:
        c = per_tool_correct[tool]
        t = per_tool_total[tool]
        print(f"- {tool:<5}: {c:02d}/{t:02d} = {_pct(c, t)}")

    print("\n分标签(含子类)正确率:")
    ordered_labels = [
        "chat",
        "modify",
        "research_consult",
        "research_modify:web",
        "research_modify:rag",
        "research_modify:both",
    ]
    for label in ordered_labels:
        c = per_label_correct[label]
        t = per_label_total[label]
        print(f"- {label:<22}: {c:02d}/{t:02d} = {_pct(c, t)}")

    print("\n混淆统计 (期望 -> 预测: 次数):")
    for expected_label in ordered_labels:
        row = confusion[expected_label]
        parts = []
        for predicted_label in ordered_labels:
            cnt = row.get(predicted_label, 0)
            if cnt:
                parts.append(f"{predicted_label}={cnt}")
        parts_str = ", ".join(parts) if parts else "(无)"
        print(f"- {expected_label:<22} -> {parts_str}")


if __name__ == "__main__":
    asyncio.run(main())
