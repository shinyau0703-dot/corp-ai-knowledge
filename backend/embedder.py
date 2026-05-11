from FlagEmbedding import BGEM3FlagModel
import torch
from backend.config import EMBEDDING_MODEL_NAME, EMBEDDING_BATCH_SIZE

_model = None

def get_model():
    global _model
    if _model is None:
        # BGE-M3 在 GPU 上建議開啟 fp16 以提升效能並節省顯存
        use_fp16 = torch.cuda.is_available()
        _model = BGEM3FlagModel(EMBEDDING_MODEL_NAME, use_fp16=use_fp16)
    return _model

def embed_texts(texts: list[str], is_query: bool = False, return_sparse: bool = False) -> list:
    model = get_model()
    # BGE-M3 支援長度達 8192，但 Query 通常較短，限制長度可加速推論
    max_len = 512 if is_query else 8192
    
    # encode 會回傳一個字典，其中包含 'dense_vecs'
    res = model.encode(
        texts, 
        batch_size=EMBEDDING_BATCH_SIZE, 
        max_length=max_len,
        return_dense=True, 
        return_sparse=return_sparse, 
        return_colbert_vecs=False
    )
    if return_sparse and isinstance(res, dict):
        # 同時回傳稠密與稀疏向量 (lexical_weights)
        return res['dense_vecs'].tolist(), res['lexical_weights']
    elif isinstance(res, dict):
        return res['dense_vecs'].tolist()
    return res.tolist()
