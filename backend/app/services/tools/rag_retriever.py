from __future__ import annotations

import os
import json
from typing import List, Optional, Dict, Any

from openai import OpenAI
from pymilvus import connections, Collection, utility
from app.core.config import settings

# 尝试导入 dashscope 用于 Rerank
try:
    import dashscope
except ImportError:
    dashscope = None

def _call_embedding_api(texts: List[str]) -> List[List[float]]:
    """
    调用嵌入模型API，获取文本的嵌入表示。
    """
    texts = [t.replace("\n", " ") for t in texts]
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY, 
                    base_url=settings.OPENAI_API_BASE)
    
    resp = client.embeddings.create(model=settings.EMBEDDING_MODEL_NAME, 
                                    input=texts, 
                                    encoding_format="float")
    
    data_items = sorted(resp.data, key=lambda x: x.index)
    embeddings = [item.embedding for item in data_items]
    return embeddings


def _ensure_milvus_connection():
    """
    连接Milvus
    """
    try:
        connections.connect(host=settings.MILVUS_HOST, port=str(settings.MILVUS_PORT))
    except Exception as e:
        raise RuntimeError(f"无法连接到Milvus: {e}")


def _generate_answer_with_llm(query: str, context: str) -> str:
    """Use the OpenAI-compatible API to generate a final answer given query and retrieved context."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_API_BASE)

    prompt = (
        "你是一个有帮助的助理。使用下面的检索到的上下文回答用户的问题：\n\n"
        "上下文:\n" + context + "\n\n"
        "问题: " + query + "\n\n"
        "请给出简明、中文的摘要式回答，仅基于上面的检索上下文回答，不要列出或暴露原始片段的路径、chunk 索引或其他元数据。严禁凭空编造事实；如果上下文不足以回答，请明确说明并给出建议。"
    )

    resp = client.chat.completions.create(model=settings.LLM_MODEL_NAME, 
                                          messages=[{"role": "user", "content": prompt}])
    
    # 简化提取逻辑
    return resp.choices[0].message.content or ""


def _generate_sub_queries(query: str) -> List[str]:
    """
    使用 LLM 生成相关的子查询，用于多路召回
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_API_BASE)
    prompt = (
        f"你是一个搜索专家。请根据用户的问题 '{query}'，生成 3 个相关的搜索查询，"
        "以便从简历数据库或岗位描述中检索到更全面的信息。\n"
        "请直接输出 3 个查询，每行一个，不要包含编号或额外解释。"
    )
    
    try:
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL_NAME,
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
        
    if not dashscope or not settings.DASHSCOPE_API_KEY:
        print("⚠️ [RAG] DashScope SDK not found or API Key missing. Skipping Rerank.")
        return docs[:top_n]

    try:
        dashscope.api_key = settings.DASHSCOPE_API_KEY
        # 提取文本列表
        doc_texts = [d.get("text", "") or d.get("text_snippet", "") for d in docs]
        
        resp = dashscope.TextReRank.call(
            model=settings.RERANK_MODEL_NAME,
            query=query,
            documents=doc_texts,
            top_n=top_n,
            return_documents=True
        )
        
        if resp.status_code == 200:
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
    """
    if not settings.DASHSCOPE_API_URL:
        raise RuntimeError("API URL is not set")

    _ensure_milvus_connection()

    collection_name = settings.RAG_COLLECTION or "md_collection"
    if not utility.has_collection(collection_name):
        raise RuntimeError(f"Milvus collection '{collection_name}' does not exist")

    coll = Collection(collection_name)
    coll.load()

    # 1. 查询扩展
    queries = _generate_sub_queries(query)
    print(f"🔍 [RAG] Expanded queries: {queries}")

    # 2. 批量向量化
    embeddings = _call_embedding_api(queries)
    if not embeddings:
        raise RuntimeError("Failed to obtain embedding for query")
    
    # 3. 向量检索
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

    sorted_candidates = [item['meta'] for item in sorted(unique_hits.values(), key=lambda x: x["score"], reverse=True)]
    
    # 5. 重排序 (Rerank)
    candidates_for_rerank = sorted_candidates[:50]
    final_docs = _rerank_documents(query, candidates_for_rerank, top_n=top_k)
    
    return final_docs


def retrieve_resume_examples(query: str, topk: Optional[int] = 5) -> str:
    """
    查询RAG向量数据库，获取相关文本片段并生成回答
    """
    final_docs = search_and_rerank(query, top_k=topk)

    if not final_docs:
        return "未找到匹配的结果。"

    out_items: List[str] = []
    for doc in final_docs:
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

    answer = _generate_answer_with_llm(query=query, context=context)
    
    return answer

if __name__ == "__main__":
    q = "什么是溯源图？"
    try:
        print(retrieve_resume_examples(q))
    except Exception as e:
        print(f"检索失败: {e}")
