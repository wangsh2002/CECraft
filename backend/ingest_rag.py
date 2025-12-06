"""
python ingest_rag.py --source ./docs --collection docs_md --chunk_size 1000
"""

import os
import re
import json
import time
import argparse
from typing import List, Dict, Any, Optional

import requests
from tqdm import tqdm
from dotenv import load_dotenv
from unstructured.partition.auto import partition
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pymilvus import (
    connections,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
    utility,
    Index
)

from openai import OpenAI

# 从 .env 文件加载环境变量
load_dotenv()  

# --- utilities ---

def find_markdown_files(source: str, recursive: bool = True) -> List[str]:
    """
    查找目录下所有 markdown 文件，也支持单个文件路径
    Args:
        source (str): 文件或目录路径
        recursive (bool): 是否递归查找子目录
    Returns:
        List[str]: 找到的 markdown 文件路径列表
    """
    files = []
    
    # 单个文件
    if os.path.isfile(source):
        if source.lower().endswith('.md'):
            return [source]
        return []
    
    # 目录下多个文件
    for root, dirs, filenames in os.walk(source):
        for fn in filenames:
            if fn.lower().endswith('.md'):
                files.append(os.path.join(root, fn))
        if not recursive:
            break
    
    found = sorted(files)
    
    print(f"find_markdown_files: found {len(found)} markdown files")
    return found


def read_markdown(path: str) -> str:
    """
    使用 Unstructured 解析文档
    Args:
        path (str): markdown 文件路径
    Returns:
        str: 解析后的纯文本内容
    """
    # 解析文档
    # 这里可以做优化，第一次处理会卡在这里比较久
    elements = partition(filename=path)

    parts = []
    for el in elements:
        # 抽取纯文本的部分
        text = getattr(el, 'text', None)
        if not text:
            # 对于非文本元素，尝试直接转换为字符串
            text = str(el)
        if text:
            parts.append(text.strip())

    result = '\n\n'.join(parts) if parts else ''

    print(f"read_markdown {path}: parsed length={len(result)} chars, parts={len(parts)}")
    return result


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 200) -> List[str]:
    """
    使用 RecursiveCharacterTextSplitter 切分文本
    Args:
        text (str): 输入文本
        max_chars (int): 每块最大字符数
        overlap (int): 块之间的重叠字符数
    Returns:
        List[str]: 切分后的文本块列表
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = splitter.split_text(text)
    print(f"chunk_text: produced {len(chunks)} chunks")
    return chunks


# --- embedding API wrapper ---

def call_embedding_api(texts: List[str], api_url: str, api_key: Optional[str] = None) -> List[List[float]]:
    """
    调用阿里云 DashScope (兼容 OpenAI 协议) 嵌入 API
    Args:
        texts (List[str]): 待嵌入的文本列表
        api_url (str): 嵌入 API 地址
        api_key (Optional[str]): API Key
    Returns:
        List[List[float]]: 嵌入向量列表
    """
    # 预处理，去除换行符，有助于 embedding 质量
    texts = [t.replace("\n", " ") for t in texts]
    
    try:
        # 初始化 OpenAI 客户端 (用于连接阿里云兼容接口)
        client = OpenAI(
            api_key=api_key,
            base_url=api_url
        )

        # 调用接口
        resp = client.embeddings.create(
            model="text-embedding-v3", 
            input=texts,
            encoding_format="float"
        )
        
        # 提取向量
        # OpenAI SDK 返回的是对象，按 index 排序确保顺序一致
        data_items = sorted(resp.data, key=lambda x: x.index)
        embeddings = [item.embedding for item in data_items]
        
        return embeddings

    except Exception as e:
        raise RuntimeError(f"阿里云 Embedding 调用失败: {e}")


# --- Milvus helpers ---

def connect_milvus(host: str, port: str):
    """
    连接 Milvus
    Args:
        host (str): Milvus 主机地址。
        port (str): Milvus 端口号。
    Returns:
        None
    """
    try:
        print(f"connecting to Milvus at {host}:{port} ...")
        connections.connect(host=host, port=port)
        print("connected to Milvus")
        
    except Exception as e:
        print(f"Failed to connect to Milvus: {e}")
        raise


def ensure_collection(collection_name: str, dim: int, metric: str = 'COSINE') -> Collection:
    # 阿里云 v3 模型通常使用 COSINE 相似度效果较好，也可以用 L2
    
    # =========== 检查集合是否存在 ==========
    if utility.has_collection(collection_name):
        coll = Collection(collection_name)
        # 检查现有集合的维度
        field = [f for f in coll.schema.fields if f.dtype == DataType.FloatVector]
        if field and field[0].params.get('dim') == dim:
            print(f"[DEBUG] ensure_collection: collection {collection_name} exists and dim matches")
            return coll
        else:
            print(f"[DEBUG] ensure_collection: dropping collection {collection_name} due to dim mismatch")
            utility.drop_collection(collection_name)

    # ========== 创建新集合 ==========
    # 定义Schema
    #  定义主键字段
    pk = FieldSchema(name='pk', dtype=DataType.INT64, is_primary=True, auto_id=True)
    #  定义向量字段
    vec = FieldSchema(name='embedding', dtype=DataType.FLOAT_VECTOR, dim=dim)
    #  定义标量字段
    meta = FieldSchema(name='metadata', dtype=DataType.VARCHAR, max_length=65535)
    schema = CollectionSchema(fields=[pk, vec, meta], description='rag chunks')
    
    # 创建集合
    coll = Collection(name=collection_name, schema=schema)
    
    # 创建索引
    index_params = {
        'index_type': 'IVF_FLAT',
        'metric_type': metric,
        'params': {'nlist': 128}
    }
    coll.create_index(field_name='embedding', index_params=index_params)
    coll.load()
    print(f"[DEBUG] ensure_collection: created and loaded collection {collection_name}")
    return coll


def insert_embeddings(collection: Collection, embeddings: List[List[float]], metadatas: List[str]):
    # Milvus expects columnar data: [[metadatas], [embeddings]] with pk auto
    entities = [embeddings, metadatas]
    # field order must match schema: pk auto -> skip, embedding, metadata
    # Using insert with field names: provide data as dict mapping field name -> list
    print(f"[DEBUG] insert_embeddings: inserting {len(embeddings)} vectors")
    res = collection.insert([embeddings, metadatas])
    print(f"[DEBUG] insert_embeddings: insert finished")
    return res


# --- main ingest pipeline ---

def ingest_directory(
    source: str,
    milvus_host: str,
    milvus_port: str,
    api_url: str,
    api_key: Optional[str],
    collection_name: str = 'md_collection',
    chunk_size: int = 1000,
    overlap: int = 200,
    recursive: bool = True,
):
    """
    读取MARKDOWN文件，切分文本，调用嵌入API，插入Milvus
    Args:
        source: markdown文件或目录路径
        milvus_host: Milvus主机地址
        milvus_port: Milvus端口
        api_url: 嵌入API地址
        api_key: 嵌入API密钥
        collection_name: Milvus集合名称
        chunk_size: 文本切分块大小
        overlap: 文本切分重叠大小
        recursive: 是否递归查找目录下的文件
    Returns:
        None
    """
    # 查找 markdown 文件
    files = find_markdown_files(source, recursive=recursive)
    if not files:
        print(f"未找到 markdown 文件: {source}")
        return

    # 连接 Milvus
    connect_milvus(milvus_host, milvus_port)

    total_inserted = 0
    first_dim = None
    collection = None

    for path in tqdm(files, desc="Ingesting markdown files"):
        # 读取并切分文本
        text = read_markdown(path)
        chunks = chunk_text(text, max_chars=chunk_size, overlap=overlap)
        if not chunks:
            continue
        
        # 调用嵌入 API，分批处理
        BATCH = 16
        embeddings_for_file = []
        metadatas_for_file = []
        for i in range(0, len(chunks), BATCH):
            batch_texts = chunks[i:i+BATCH]

            # 调用嵌入 API
            embeddings = call_embedding_api(batch_texts, api_url=api_url, api_key=api_key)
            if not embeddings:
                raise RuntimeError("嵌入 API 未返回向量")
            
            # 初始化 collection
            if first_dim is None:
                first_dim = len(embeddings[0])
                collection = ensure_collection(collection_name, dim=first_dim)
            
            # 检查维度一致性
            for emb in embeddings:
                if len(emb) != first_dim:
                    raise RuntimeError(f"嵌入维度不一致: 期望 {first_dim}, 实际 {len(emb)}")

            # 构建元数据
            for idx, emb in enumerate(embeddings):
                chunk_idx = i + idx
                meta = json.dumps({
                    'source': path,
                    'chunk_index': chunk_idx,
                    'text_snippet': chunks[chunk_idx][:200]
                }, ensure_ascii=False)
                embeddings_for_file.append(emb)
                metadatas_for_file.append(meta)

        # 批量插入 Milvus
        INSERT_BATCH = 64
        for j in range(0, len(embeddings_for_file), INSERT_BATCH):
            sub_emb = embeddings_for_file[j:j+INSERT_BATCH]
            sub_meta = metadatas_for_file[j:j+INSERT_BATCH]
            # Milvus expects list of embeddings and list of metadata (in column order matching schema fields after pk)
            print(f"[DEBUG] ingest_directory: inserting batch {j}..{j+len(sub_emb)}")
            collection.insert([sub_emb, sub_meta])
            total_inserted += len(sub_emb)
        # make sure collection loaded
        collection.load()
        print(f"已插入: {path} -> {len(embeddings_for_file)} vectors")

    # flush and report
    if collection:
        print(f"[DEBUG] ingest_directory: flushing collection {collection_name}")
        collection.flush()
    print(f"全部完成，插入向量总数: {total_inserted}")


def main():
    parser = argparse.ArgumentParser(description='Ingest local markdown to Milvus via embedding API')
    parser.add_argument('--source', required=True, help='Markdown 文件或目录')
    parser.add_argument('--collection', default='md_collection', help='Milvus collection 名称')
    parser.add_argument('--milvus-host', default=os.getenv('MILVUS_HOST', '127.0.0.1'))
    parser.add_argument('--milvus-port', default=os.getenv('MILVUS_PORT', '19530'))
    parser.add_argument('--api-url', default=os.getenv('DASHSCOPE_API_URL'))
    parser.add_argument('--api-key', default=os.getenv('DASHSCOPE_API_KEY'))
    parser.add_argument('--chunk-size', type=int, default=1000)
    parser.add_argument('--overlap', type=int, default=200)
    parser.add_argument('--recursive', action='store_true')
    
    args = parser.parse_args()

    if not args.api_url:
        print('错误：未配置嵌入 API 地址，请设置环境变量 DASHSCOPE_API_URL 或使用 --api-url 参数')
        return

    ingest_directory(
        source=args.source,
        milvus_host=args.milvus_host,
        milvus_port=args.milvus_port,
        api_url=args.api_url,
        api_key=args.api_key,
        collection_name=args.collection,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        recursive=args.recursive,
    )


if __name__ == '__main__':
    main()
