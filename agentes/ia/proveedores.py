"""Proveedores de IA sobre la API compatible con OpenAI (ADR-005).

Chat y embeddings son independientes: se configuran por variables de entorno
y cambiar de Ollama a DeepSeek o Qwen cloud no toca el código.
"""

import os
import time
from dataclasses import dataclass

import httpx


@dataclass
class Uso:
    tokens_entrada: int = 0
    tokens_salida: int = 0
    ms: float = 0.0


class ChatProvider:
    def __init__(self, base_url: str, modelo: str, api_key: str = "ollama", timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.modelo = modelo
        self._cliente = httpx.Client(timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})

    @classmethod
    def desde_entorno(cls) -> "ChatProvider":
        return cls(
            os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
            os.environ.get("LLM_MODEL", "qwen2.5:3b"),
            os.environ.get("LLM_API_KEY", "ollama"),
        )

    def completar(self, mensajes: list[dict], json: bool = True, temperatura: float = 0.0,
                  max_tokens: int = 400) -> tuple[str, Uso]:
        cuerpo = {"model": self.modelo, "messages": mensajes, "temperature": temperatura,
                  "max_tokens": max_tokens}
        if json:
            cuerpo["response_format"] = {"type": "json_object"}
        inicio = time.perf_counter()
        r = self._cliente.post(f"{self.base_url}/chat/completions", json=cuerpo)
        r.raise_for_status()
        datos = r.json()
        uso = datos.get("usage") or {}
        return datos["choices"][0]["message"]["content"], Uso(
            uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0),
            (time.perf_counter() - inicio) * 1000,
        )


class EmbeddingProvider:
    # 180 s: la primera llamada incluye cargar el modelo en la GPU (arranque en frío)
    def __init__(self, base_url: str, modelo: str, api_key: str = "ollama", timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.modelo = modelo
        self._cliente = httpx.Client(timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})

    @classmethod
    def desde_entorno(cls) -> "EmbeddingProvider":
        return cls(
            os.environ.get("EMBEDDING_BASE_URL", "http://localhost:11434/v1"),
            os.environ.get("EMBEDDING_MODEL", "bge-m3"),
            os.environ.get("EMBEDDING_API_KEY", "ollama"),
        )

    def calentar(self) -> None:
        """Carga el modelo antes de medir, para que el arranque en frío no cuente en la latencia."""
        self.vectorizar(["calentamiento"])

    def vectorizar(self, textos: list[str], lote: int = 16) -> list[list[float]]:
        vectores: list[list[float]] = []
        for i in range(0, len(textos), lote):
            cuerpo = {"model": self.modelo, "input": textos[i : i + lote]}
            for intento in (1, 2):
                try:
                    r = self._cliente.post(f"{self.base_url}/embeddings", json=cuerpo)
                    r.raise_for_status()
                    break
                except httpx.TimeoutException:
                    if intento == 2:
                        raise
            datos = sorted(r.json()["data"], key=lambda d: d["index"])
            vectores.extend(d["embedding"] for d in datos)
        return vectores
