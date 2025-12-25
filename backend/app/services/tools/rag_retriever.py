from __future__ import annotations

import os
import json
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from pymilvus import connections, Collection, utility


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

    # 问题向量化
    embeddings = _call_embedding_api([query], api_url=api_url, api_key=api_key)
    if not embeddings:
        raise RuntimeError("Failed to obtain embedding for query")
    q_emb = embeddings[0]


    # 向量检索
    search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
    results = coll.search([q_emb], "embedding", param=search_params, limit=topk, output_fields=["metadata"])

    # 解析检索结果
    hits = results[0] if results else []
    if not hits:
        return "未找到匹配的结果。"

    out_items: List[str] = []
    for hit in hits:
        score = hit.score if hasattr(hit, "score") else hit.distance

        meta_raw = None
        try:
            if hasattr(hit, "fields") and isinstance(hit.fields, dict):
                meta_raw = hit.fields.get("metadata", None)
        except:
            pass

        if meta_raw is None:
            try:
                ent = getattr(hit, "entity", None)
                if ent and isinstance(ent, dict):
                    meta_raw = ent.get("metadata", None)
            except:
                pass

        if isinstance(meta_raw, dict):
            meta = meta_raw
        else:
            try:
                meta = json.loads(meta_raw) if meta_raw else {}
            except:
                meta = {}

        snippet = meta.get("text_snippet") or meta.get("snippet") or "(no snippet)"
        source = meta.get("source") or meta.get("file") or "(unknown)"
        chunk_index = meta.get("chunk_index")

        out = (
            f"source: {source} | chunk: {chunk_index} | score: {score}\n"
            f"{snippet}"
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
