import os
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .config import get_config

def _get_azure_llm():
    """
    內部輔助函式：統一建立 Azure Chat Model 物件
    這樣可以確保所有函式都使用正確的 Config 設定
    """
    config = get_config()
    
    # 確保使用與 main.py 一致的設定
    return AzureChatOpenAI(
        deployment_name=config["quick_think_llm"],  # 例如 gpt-4o-mini
        azure_endpoint=config["backend_url"],       # 例如 https://cmoney...
        api_version=config.get("azure_api_version", "2024-02-15-preview"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),  # 確保有讀到環境變數
        temperature=0.7
    )

def get_stock_news_openai(query, start_date, end_date):
    """
    使用 Azure OpenAI 生成/檢索個股新聞摘要
    """
    llm = _get_azure_llm()
    
    prompt = (
        f"Can you provide news insights for {query} from {start_date} to {end_date}? "
        "Summarize key events based on your knowledge."
    )
    
    # 呼叫模型
    response = llm.invoke([
        SystemMessage(content="You are a helpful financial research assistant."),
        HumanMessage(content=prompt)
    ])
    
    return response.content

def get_global_news_openai(curr_date, look_back_days=7, limit=5):
    """
    使用 Azure OpenAI 生成全球宏觀經濟新聞摘要
    """
    llm = _get_azure_llm()
    
    prompt = (
        f"Search global or macroeconomics news from {look_back_days} days before {curr_date} "
        f"to {curr_date} that would be informative for trading purposes. "
        f"Limit the results to {limit} key points."
    )
    
    response = llm.invoke([
        SystemMessage(content="You are a helpful financial research assistant."),
        HumanMessage(content=prompt)
    ])
    
    return response.content

def get_fundamentals_openai(ticker, curr_date):
    """
    使用 Azure OpenAI 分析基本面數據
    """
    llm = _get_azure_llm()
    
    prompt = (
        f"Provide a fundamental analysis for {ticker} leading up to {curr_date}. "
        "List key metrics like PE ratio, PS ratio, Cash flow if available in your knowledge base."
    )
    
    response = llm.invoke([
        SystemMessage(content="You are a helpful financial research assistant."),
        HumanMessage(content=prompt)
    ])
    
    return response.content