from config import create_client, asyncio, ollama_client, logger, message_queue


async def generate_local_embedding(text: str) -> list:
    try:
        response = await asyncio.to_thread(
            ollama_client.embed,
            model="nomic-embed-text",
            input=text
        )
        return response['embeddings'][0]
    except Exception as e:
        logger.error(f"Ollama embedding error: {e}")
        return []
