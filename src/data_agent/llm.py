from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic


def create_embeddings(settings=None):
    """Reuse the provider's OPENAI_API_KEY handling; no calls until embedding."""
    from langchain_openai import OpenAIEmbeddings
    from data_agent.config import policy_ingestion_settings
    settings = settings or policy_ingestion_settings()
    return OpenAIEmbeddings(model=settings.embedding_model, dimensions=settings.embedding_dimensions,
                            chunk_size=settings.embedding_batch_size, check_embedding_ctx_length=False,
                            request_timeout=60, max_retries=2)

def create_llm(level: str):
    """
    Picks the oppropriate LLM based on the level of question 

    Args:
        Level (str): The of the question, can be "easy", "medium", or "hard".

    Returns:
        str: The name of LLM to be used.
    """

    if level.lower() == "low":
        llm = ChatOpenAI(model_name="gpt-5.6-luna", temperature=0, model_kwargs={"reasoning_effort":"none"})
    elif level.lower() == "medium":
        llm = ChatOpenAI(model_name="gpt-5.6-terra", temperature=0, model_kwargs={"reasoning_effort":"none"})
    elif level.lower() == "high":
        llm = ChatOpenAI(model_name="gpt-5.6-sol", temperature=0, model_kwargs={"reasoning_effort":"none"})
    elif level.lower() == "claude":
        llm = ChatAnthropic(model_name="claude-sonnet-5")
    else:
        raise ValueError(f"Unsupported level: {level}")
    
    return llm
