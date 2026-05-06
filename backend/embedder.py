from FlagEmbedding import BGEM3FlagModel
import torch

_model = None

def get_model():
    global _model
    if _model is None:
        # BGE-M3 在 GPU 上建議開啟 fp16 以提升效能並節省顯存
        use_fp16 = torch.cuda.is_available()
        _model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=use_fp16)
    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    # BGEM3FlagModel.encode 會回傳一個字典，其中包含 'dense_vecs'
    res = model.encode(texts, batch_size=32, return_dense=True, return_sparse=False, return_colbert_vecs=False)
    if isinstance(res, dict):
        return res['dense_vecs'].tolist()
    return res.tolist()
