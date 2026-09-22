from sentence_transformers import SentenceTransformer

class RAGService:
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        
    async def embed_query(self, query: str) -> list:
        embeddings = self.model.encode(query)
        return embeddings.tolist()
        
    async def search_similar(self, query: str) -> str:
        return "Mocked context relevant to the query from database."
