import os

from mem0 import Memory  # type: ignore[import-untyped]

from core.config import LLMConfig, MemoryConfig


class LearningMemory:
    def __init__(self, memory_config: MemoryConfig, llm_config: LLMConfig):
        # Determine LLM endpoint for mem0's extraction
        if llm_config.backend == "api":
            llm_base_url = llm_config.api.base_url
            llm_model = llm_config.api.model
            api_key = os.environ.get(llm_config.api.api_key_env, "")
        else:
            llm_base_url = llm_config.local.base_url
            llm_model = llm_config.local.model
            api_key = "not-needed"

        storage_path = os.path.expanduser(memory_config.storage_path)
        os.makedirs(storage_path, exist_ok=True)

        self.memory = Memory.from_config(
            {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "collection_name": "voxaos",
                        "path": storage_path,
                    },
                },
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": llm_model,
                        "openai_base_url": llm_base_url,
                        "api_key": api_key,
                    },
                },
            }
        )

    def add(self, user_msg: str, assistant_msg: str, user_id: str = "default") -> None:
        messages = [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
        ]
        self.memory.add(messages, user_id=user_id)

    def search(self, query: str, user_id: str = "default", limit: int = 5) -> list[str]:
        results = self.memory.search(query, user_id=user_id, limit=limit)
        return [r["memory"] for r in results.get("results", [])]

    def get_all(self, user_id: str = "default") -> list[str]:
        results = self.memory.get_all(user_id=user_id)
        return [r["memory"] for r in results.get("results", [])]
