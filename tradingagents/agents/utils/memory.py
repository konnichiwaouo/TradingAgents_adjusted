import os
import chromadb
from chromadb.config import Settings
from openai import OpenAI, AzureOpenAI
from dotenv import load_dotenv

# 確保載入環境變數
load_dotenv()

class FinancialSituationMemory:
    def __init__(self, name, config):
        self.config = config
        
        # 1. 判斷是否使用 Azure
        if self.config.get("llm_provider") == "azure":
            self.client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=self.config.get("azure_api_version", "2024-02-15-preview"),
                azure_endpoint=self.config.get("backend_url")
            )
            # 【重要】Azure 必須使用部署名稱 (Deployment Name)
            # 請確保您的 config 中有 "embedding_model" 這個欄位，且填寫的是 Azure 後台的部署名稱
            self.embedding_model = self.config.get("embedding_model", "text-embedding-3-small")
            
        elif config.get("backend_url") == "http://localhost:11434/v1":
            # 本地 Ollama 等設定
            self.client = OpenAI(base_url=config["backend_url"], api_key="ollama")
            self.embedding_model = "nomic-embed-text"
        else:
            # 官方 OpenAI 設定
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.embedding_model = "text-embedding-3-small"

        # 初始化 ChromaDB (使用記憶體模式，重啟會清空)
        self.chroma_client = chromadb.Client(Settings(allow_reset=True))
        
        # 使用 get_or_create 比較安全，避免重複建立報錯
        self.situation_collection = self.chroma_client.get_or_create_collection(name=name)

    def get_embedding(self, text):
        """Get OpenAI/Azure embedding for a text"""
        # 移除換行符號以獲得更好的向量品質
        text = text.replace("\n", " ")
        
        response = self.client.embeddings.create(
            model=self.embedding_model, # Azure 這裡對應的是 Deployment Name
            input=[text]
        )
        return response.data[0].embedding

    def add_situations(self, situations_and_advice):
        """Add financial situations and their corresponding advice."""
        situations = []
        advice = []
        ids = []
        embeddings = []

        # 為了避免 ID 重複，我們加上目前的數量作為 offset
        offset = self.situation_collection.count()

        for i, (situation, recommendation) in enumerate(situations_and_advice):
            situations.append(situation)
            advice.append(recommendation)
            ids.append(f"id_{offset + i}") # 將 ID 轉為字串比較安全
            embeddings.append(self.get_embedding(situation))

        if situations:
            self.situation_collection.add(
                documents=situations,
                metadatas=[{"recommendation": rec} for rec in advice],
                embeddings=embeddings,
                ids=ids,
            )

    def get_memories(self, current_situation, n_matches=1):
        """Find matching recommendations using embeddings"""
        query_embedding = self.get_embedding(current_situation)

        results = self.situation_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_matches,
            include=["metadatas", "documents", "distances"],
        )

        matched_results = []
        # 檢查是否有回傳結果
        if results["documents"]:
            for i in range(len(results["documents"][0])):
                matched_results.append(
                    {
                        "matched_situation": results["documents"][0][i],
                        "recommendation": results["metadatas"][0][i]["recommendation"],
                        # ChromaDB 回傳的是距離，轉換成相似度 (1 - distance) 僅供參考
                        "similarity_score": 1 - results["distances"][0][i],
                    }
                )

        return matched_results


# ==========================================
# 測試區塊 (模擬 Main 程式執行)
# ==========================================
if __name__ == "__main__":
    
    # 1. 建立一個假的 Config 來模擬您的環境
    # 請確保這裡的 embedding_model 填的是您在 Azure 後台的「部署名稱」
    mock_config = {
        "llm_provider": "azure",
        "backend_url": "https://cmoneyfund.openai.azure.com/", # 您的 Endpoint
        "azure_api_version": "2024-02-15-preview",
        "embedding_model": "text-embedding-3-small" # <--- 關鍵！這要是您 Azure 上的部署名稱
    }

    print("正在初始化記憶模組...")
    # 修正：必須傳入 name 和 config
    matcher = FinancialSituationMemory(name="test_memory", config=mock_config)

    # Example data
    example_data = [
        (
            "High inflation rate with rising interest rates and declining consumer spending",
            "Consider defensive sectors like consumer staples and utilities. Review fixed-income portfolio duration.",
        ),
        (
            "Tech sector showing high volatility with increasing institutional selling pressure",
            "Reduce exposure to high-growth tech stocks. Look for value opportunities in established tech companies with strong cash flows.",
        ),
        (
            "Strong dollar affecting emerging markets with increasing forex volatility",
            "Hedge currency exposure in international positions. Consider reducing allocation to emerging market debt.",
        ),
        (
            "Market showing signs of sector rotation with rising yields",
            "Rebalance portfolio to maintain target allocations. Consider increasing exposure to sectors benefiting from higher rates.",
        ),
    ]

    print(f"正在建立 {len(example_data)} 筆記憶向量 (這會呼叫 Azure API)...")
    matcher.add_situations(example_data)

    # Example query
    current_situation = """
    Market showing increased volatility in tech sector, with institutional investors 
    reducing positions and rising interest rates affecting growth stock valuations
    """

    print("正在搜尋相似記憶...")
    try:
        recommendations = matcher.get_memories(current_situation, n_matches=2)

        for i, rec in enumerate(recommendations, 1):
            print(f"\nMatch {i}:")
            print(f"Similarity Score: {rec['similarity_score']:.2f}")
            print(f"Matched Situation: {rec['matched_situation']}")
            print(f"Recommendation: {rec['recommendation']}")

    except Exception as e:
        print(f"Error during recommendation: {str(e)}")