from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from typing import Optional


class Planner:
    """
    Planner che chiama Ollama locale via HTTP.
    Default:
      http://127.0.0.1:11434/api/generate
    """

    def __init__(
        self,
        model: str = "phi3",
        base_url: str = "http://127.0.0.1:11434",
        timeout_s: int = 20,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def propose_goal(self, prompt: str) -> str:
        """
        Chiamata sincrona a Ollama.
        Ritorna una stringa goal pulita.
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            return f"error: ollama unreachable ({e})"
        except Exception as e:
            return f"error: {e}"

        text = self._parse_ollama_stream(raw)
        goal = self._extract_goal(text)

        return goal or "survive"

    async def propose_goal_async(self, prompt: str) -> str:
        """
        Wrapper non bloccante.
        Esegue propose_goal in thread separato.
        """
        return await asyncio.to_thread(self.propose_goal, prompt)

    def _parse_ollama_stream(self, raw: str) -> str:
        """
        Ollama spesso ritorna più righe JSON:
        {"response":"...","done":false}
        {"response":"...","done":true}
        """
        parts = []

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)

                if isinstance(obj, dict):
                    if "response" in obj:
                        parts.append(str(obj["response"]))
                    elif "error" in obj:
                        parts.append(f"error: {obj['error']}")
            except json.JSONDecodeError:
                # fallback: se non è JSON, prova a tenere il testo
                parts.append(line)

        return "".join(parts).strip()

    def _extract_goal(self, text: str) -> Optional[str]:
        """
        Estrae un goal da:
        - testo normale
        - JSON
        - ```json ... ```
        """
        if not text:
            return None

        cleaned = text.strip()

        # rimuovi code fences markdown
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        # prova parsing JSON diretto
        try:
            obj = json.loads(cleaned)

            if isinstance(obj, dict):
                g = obj.get("goal") or obj.get("task") or obj.get("objective")
                if isinstance(g, str) and g.strip():
                    return g.strip()
        except Exception:
            pass

        # fallback: prima riga utile
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return None

        return lines[0][:120].strip()