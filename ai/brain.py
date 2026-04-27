"""
brain.py — Мозг Jarvis через OpenAI ChatGPT API + function calling для команд
"""

import json
from openai import OpenAI
from config import OPENAI_API_KEY, GPT_MODEL, GPT_TEMPERATURE, build_system_prompt, get_lang
from commands import COMMANDS, execute_command, build_tools_schema


class Brain:
    def __init__(self):
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=15.0,    # не висеть при нестабильном интернете
            max_retries=1,   # 1 повтор при обрыве, потом ошибка
        )
        self.history: list = []
        self._rebuild_system()
        print("    ✓ OpenAI подключён")

    def _rebuild_system(self):
        system_msg = {"role": "system", "content": build_system_prompt(COMMANDS)}
        if self.history and self._role(self.history[0]) == "system":
            self.history[0] = system_msg
        else:
            self.history.insert(0, system_msg)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _role(msg) -> str:
        return msg.get("role") if isinstance(msg, dict) else msg.role

    @staticmethod
    def _has_tool_calls(msg) -> bool:
        tc = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
        return bool(tc)

    # ── Основной метод ────────────────────────────────────────────────────────

    def think(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=GPT_MODEL,
                messages=self.history,
                tools=build_tools_schema(),
                tool_choice="auto",
                max_tokens=500,
                temperature=GPT_TEMPERATURE,
            )

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            # ── GPT вызывает инструменты ──────────────────────────────────────
            if finish_reason == "tool_calls" and msg.tool_calls:
                # Сохраняем сообщение ассистента со ВСЕМИ tool_calls
                self.history.append(msg)

                # Выполняем КАЖДЫЙ вызов и добавляем ответ с matching tool_call_id
                for tool_call in msg.tool_calls:
                    cmd_name = tool_call.function.name
                    cmd_args = json.loads(tool_call.function.arguments or "{}")
                    print(f"  [CMD] {cmd_name} {cmd_args}")
                    cmd_result = execute_command(cmd_name, cmd_args)
                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": cmd_result,
                    })

                # Второй запрос — финальный ответ пользователю
                final = self.client.chat.completions.create(
                    model=GPT_MODEL,
                    messages=self.history,
                    max_tokens=200,
                    temperature=0.7,
                )
                answer = final.choices[0].message.content or ""
                answer = answer.strip()
                # Сохраняем финальный ответ в историю
                self.history.append({"role": "assistant", "content": answer})

            # ── Обычный текстовый ответ ───────────────────────────────────────
            else:
                answer = (msg.content or "").strip()
                if not answer:
                    answer = get_lang().get("not_understood", "Не понял, повторите.")
                self.history.append({"role": "assistant", "content": answer})

            self._trim_history()
            return answer

        except Exception as e:
            print(f"  [!] Ошибка OpenAI: {e}")
            self._drop_broken_tail()
            return "Произошла ошибка при обращении к серверу."

    # ── Обрезка истории ───────────────────────────────────────────────────────

    def _trim_history(self, keep: int = 20) -> None:
        """Обрезает историю до keep сообщений, не разрывая tool_calls-цепочки."""
        if len(self.history) <= keep + 1:  # +1 — system
            return

        system = self.history[0]
        tail = self.history[-keep:]

        # Ищем первую безопасную точку среза: сообщение user или
        # assistant без tool_calls (начало чистого диалогового хода)
        for i, m in enumerate(tail):
            role = self._role(m)
            if role == "user":
                self.history = [system] + tail[i:]
                return
            if role == "assistant" and not self._has_tool_calls(m):
                self.history = [system] + tail[i:]
                return

        # Крайний случай: оставляем как есть
        self.history = [system] + tail

    def _drop_broken_tail(self) -> None:
        """Удаляет из хвоста истории оборванные tool_calls без ответов."""
        while len(self.history) > 1:
            last = self.history[-1]
            role = self._role(last)
            if role in ("tool",) or (role == "assistant" and self._has_tool_calls(last)):
                self.history.pop()
            else:
                break

    # ── Прочее ───────────────────────────────────────────────────────────────

    def reset_history(self):
        self.history = []
        self._rebuild_system()

    def refresh_language(self):
        self._rebuild_system()