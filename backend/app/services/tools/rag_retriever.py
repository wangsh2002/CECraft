from __future__ import annotations

import os
import json
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from openai import OpenAI
from pymilvus import connections, Collection, utility

# 尝试导入 dashscope 用于 Rerank
try:
    import dashscope
except ImportError:
    dashscope = None


load_dotenv()


def _call_embedding_api(texts: List[str], api_url: str, api_key: Optional[str]) -> List[List[float]]:
    """
    调用嵌入模型API，获取文本的嵌入表示。
    Args:
        texts (List[str]): 需要获取嵌入表示的文本列表。
        api_url (str): 嵌入模型API的URL。
        api_key (Optional[str]): 用于API认证的密钥。
    Returns:
        List[List[float]]: 文本的嵌入表示列表。
    """
    texts = [t.replace("\n", " ") for t in texts]
    
    client = OpenAI(api_key=api_key, 
                    base_url=api_url)
    
    resp = client.embeddings.create(model="text-embedding-v3", 
                                    input=texts, 
                                    encoding_format="float")
    
    data_items = sorted(resp.data, key=lambda x: x.index)

    embeddings = [item.embedding for item in data_items]

    return embeddings


def _ensure_milvus_connection(host: str, port: str):
    """
    连接Milvus
    Args:
        host (str): Milvus主机地址。
        port (str): Milvus端口号。
    """
    try:
        connections.connect(host=host, port=port)
    except Exception as e:
        raise RuntimeError(f"无法连接到Milvus: {e}")


def _generate_answer_with_llm(query: str, context: str, api_url: str, api_key: Optional[str]) -> str:
    """Use the OpenAI-compatible API to generate a final answer given query and retrieved context.

    Returns the text response from the model.
    """
    client = OpenAI(api_key=api_key, base_url=api_url)

    prompt = (
        "你是一个有帮助的助理。使用下面的检索到的上下文回答用户的问题：\n\n"
        "上下文:\n" + context + "\n\n"
        "问题: " + query + "\n\n"
        "请给出简明、中文的摘要式回答，仅基于上面的检索上下文回答，不要列出或暴露原始片段的路径、chunk 索引或其他元数据。严禁凭空编造事实；如果上下文不足以回答，请明确说明并给出建议。"
    )

    resp = None
    resp = client.chat.completions.create(model="qwen-turbo", 
                                          messages=[{"role": "user", "content": prompt}])
    # 从响应中提取文本，兼容多种返回格式
    text = None
    try:
        text = getattr(resp, "output_text", None)
    except Exception:
        text = None

    if not text:
        try:
            out = getattr(resp, "output", None)
            if out and isinstance(out, list) and len(out) > 0:
                parts = []
                for item in out:
                    cont = item.get("content") if isinstance(item, dict) else None
                    if cont and isinstance(cont, list):
                        for c in cont:
                            if isinstance(c, dict) and c.get("type") == "output_text":
                                parts.append(c.get("text", ""))
                            elif isinstance(c, str):
                                parts.append(c)
                text = "".join(parts)
        except Exception:
            text = None

    if not text:
        try:
            choices = getattr(resp, "choices", None)
            if choices and len(choices) > 0:
                # handle both object and dict shapes
                first = choices[0]
                if hasattr(first, "message"):
                    text = first.message.get("content") if isinstance(first.message, dict) else getattr(first.message, "content", None)
                else:
                    # dict-like
                    text = first.get("text") if isinstance(first, dict) else None
        except Exception:
            text = None

    if not text:
        raise RuntimeError("无法从大模型响应中提取文本输出")

    return text


def retrieve_resume_examples(query: str, topk: Optional[int] = 5) -> str:
    """
    查询RAG向量数据库，获取相关文本片段并生成回答
    Args:
        query (str): 查询文本。
        topk (Optional[int]): 返回的相似文本片段数量，默认为5
    Returns:
        str: 大模型生成的回答
    """
    api_url = os.getenv("DASHSCOPE_API_URL")
    api_key = os.getenv("DASHSCOPE_API_KEY")
    milvus_host = os.getenv("MILVUS_HOST", "127.0.0.1")
    milvus_port = os.getenv("MILVUS_PORT", "19530")
    collection_name = os.getenv("RAG_COLLECTION", "md_collection")

    if not api_url:
        raise RuntimeError("API URL is not set")

    # 连接Mlivus
    _ensure_milvus_connection(milvus_host, milvus_port)

    # 加载集合
    if not utility.has_collection(collection_name):
        raise RuntimeError(f"Milvus collection '{collection_name}' does not exist")

    coll = Collection(collection_name)
    coll.load()

def _generate_sub_queries(query: str, api_url: str, api_key: Optional[str]) -> List[str]:
    """
    使用 LLM 生成相关的子查询，用于多路召回
    """
    client = OpenAI(api_key=api_key, base_url=api_url)
    prompt = (
        f"你是一个搜索专家。请根据用户的问题 '{query}'，生成 3 个相关的搜索查询，"
        "以便从简历数据库或岗位描述中检索到更全面的信息。\n"
        "请直接输出 3 个查询，每行一个，不要包含编号或额外解释。"
    )
    
    try:
        resp = client.chat.completions.create(
            model="qwen-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        content = resp.choices[0].message.content
        if not content:
            return [query]
            
        sub_queries = [line.strip() for line in content.split('\n') if line.strip()]
        return [query] + sub_queries[:3] # 包含原始查询
    except Exception:
        return [query]


def _rerank_documents(query: str, docs: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    """
    使用 DashScope Rerank 模型对文档进行重排序
    """
    if not docs:
        return []
        
    # 如果没有 dashscope 库或没有 API Key，直接返回前 N 个
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not dashscope or not api_key:
        print("⚠️ [RAG] DashScope SDK not found or API Key missing. Skipping Rerank.")
        return docs[:top_n]

    try:
        dashscope.api_key = api_key
        # 提取文本列表
        doc_texts = [d.get("text", "") or d.get("text_snippet", "") for d in docs]
        
        # 调用 Rerank API
        # 注意：DashScope Rerank API 调用方式可能随版本变化，这里使用标准调用
        resp = dashscope.TextReRank.call(
            model='gte-rerank',
            query=query,
            documents=doc_texts,
            top_n=top_n,
            return_documents=True
        )
        
        if resp.status_code == 200:
            # 根据返回的 index 重新组织 docs
            reranked_docs = []
            for item in resp.output.results:
                original_idx = item.index
                doc = docs[original_idx]
                doc['rerank_score'] = item.relevance_score
                reranked_docs.append(doc)
            print(f"✅ [RAG] Rerank successful. Top score: {reranked_docs[0]['rerank_score']}")
            return reranked_docs
        else:
            print(f"⚠️ [RAG] Rerank API failed: {resp.message}. Fallback to original order.")
            return docs[:top_n]
            
    except Exception as e:
        print(f"⚠️ [RAG] Rerank exception: {e}. Fallback to original order.")
        return docs[:top_n]


def search_and_rerank(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    执行完整的检索流程：Query Expansion -> Vector Search -> Rerank
    返回文档列表，供 Evaluation 使用
    """
    api_url = os.getenv("DASHSCOPE_API_URL")
    api_key = os.getenv("DASHSCOPE_API_KEY")
    milvus_host = os.getenv("MILVUS_HOST", "127.0.0.1")
    milvus_port = os.getenv("MILVUS_PORT", "19530")
    collection_name = os.getenv("RAG_COLLECTION", "md_collection")

    if not api_url:
        raise RuntimeError("API URL is not set")

    _ensure_milvus_connection(milvus_host, milvus_port)

    if not utility.has_collection(collection_name):
        raise RuntimeError(f"Milvus collection '{collection_name}' does not exist")

    coll = Collection(collection_name)
    coll.load()

    # 1. 查询扩展
    queries = _generate_sub_queries(query, api_url, api_key)
    print(f"🔍 [RAG] Expanded queries: {queries}")

    # 2. 批量向量化
    embeddings = _call_embedding_api(queries, api_url=api_url, api_key=api_key)
    if not embeddings:
        raise RuntimeError("Failed to obtain embedding for query")
    
    # 3. 向量检索 (扩大召回范围，为 Rerank 准备)
    # 如果最终需要 top_k=5，我们召回 top_k * 3 或更多
    recall_k = top_k * 4 
    search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
    limit_per_query = max(2, recall_k // len(queries) + 1)
    
    results = coll.search(embeddings, "embedding", param=search_params, limit=limit_per_query, output_fields=["metadata"])

    # 4. 结果去重与合并
    unique_hits = {} 
    
    for hits in results:
        for hit in hits:
            meta_raw = hit.entity.get("metadata")
            if not meta_raw:
                continue
            try:
                meta = json.loads(meta_raw)
                key = (meta.get("source"), meta.get("chunk_index"))
                # 确保 meta 中有 text 字段，如果没有则回退到 snippet
                if 'text' not in meta:
                    meta['text'] = meta.get('text_snippet', '')
                
                if key not in unique_hits:
                    unique_hits[key] = {
                        "score": hit.score,
                        "meta": meta
                    }
                else:
                    if hit.score > unique_hits[key]["score"]:
                        unique_hits[key]["score"] = hit.score
            except:
                continue

    # 初步排序
    sorted_candidates = [item['meta'] for item in sorted(unique_hits.values(), key=lambda x: x["score"], reverse=True)]
    
    # 5. 重排序 (Rerank)
    # 只对前 50 个候选进行重排序，节省成本
    candidates_for_rerank = sorted_candidates[:50]
    final_docs = _rerank_documents(query, candidates_for_rerank, top_n=top_k)
    
    return final_docs


def retrieve_resume_examples(query: str, topk: Optional[int] = 5) -> str:
    """
    查询RAG向量数据库，获取相关文本片段并生成回答
    """
    api_url = os.getenv("DASHSCOPE_API_URL")
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    # 调用拆分后的检索函数
    final_docs = search_and_rerank(query, top_k=topk)

    if not final_docs:
        return "未找到匹配的结果。"

    out_items: List[str] = []
    for doc in final_docs:
        # 优先使用完整文本
        text_content = doc.get("text") or doc.get("text_snippet") or "(no content)"
        source = doc.get("source") or "(unknown)"
        chunk_index = doc.get("chunk_index")
        score = doc.get("rerank_score", 0)

        out = (
            f"source: {source} | chunk: {chunk_index} | score: {score}\n"
            f"{text_content}"
        )
        out_items.append(out)

    context = "\n\n---\n\n".join(out_items)

    answer = _generate_answer_with_llm(query=query, context=context, api_url=api_url, api_key=api_key)
    
    return answer


if __name__ == "__main__":
    q = "什么是溯源图？"
    try:
        print(retrieve_resume_examples(q))
    except Exception as e:
        print(f"检索失败: {e}")
