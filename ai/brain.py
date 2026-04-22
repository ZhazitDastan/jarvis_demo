"""
brain.py — Мозг Jarvis через OpenAI ChatGPT API + function calling для команд
"""

import json
from openai import OpenAI
from config import OPENAI_API_KEY, GPT_MODEL, build_system_prompt
from commands.Commands import COMMANDS, execute_command, build_tools_schema


class Brain:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.history: list = []
        self._rebuild_system()
        print("    ✓ OpenAI подключён")

    def _rebuild_system(self):
        """Обновляет системный промпт (при смене языка или команд)."""
        system_msg = {"role": "system", "content": build_system_prompt(COMMANDS)}
        if self.history and self.history[0]["role"] == "system":
            self.history[0] = system_msg
        else:
            self.history.insert(0, system_msg)

    def think(self, user_message: str) -> str:
        """
        Отправляет сообщение GPT.
        Если GPT вызывает команду — выполняет её и возвращает результат.
        """
        self.history.append({"role": "user", "content": user_message})

        try:
            # Первый запрос — с инструментами
            response = self.client.chat.completions.create(
                model=GPT_MODEL,
                messages=self.history,
                tools=build_tools_schema(),
                tool_choice="auto",    # GPT сам решает — команда или текст
                max_tokens=500,
                temperature=0.7,
            )

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            # ── GPT решил вызвать команду ──────────────────────────────────
            if finish_reason == "tool_calls" and msg.tool_calls:
                tool_call = msg.tool_calls[0]
                cmd_name = tool_call.function.name
                cmd_args = json.loads(tool_call.function.arguments or "{}")

                print(f"  [CMD] Выполняю команду: {cmd_name} {cmd_args}")
                cmd_result = execute_command(cmd_name, cmd_args)

                # Добавляем в историю вызов и результат
                self.history.append(msg)  # сообщение ассистента с tool_calls
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": cmd_result,
                })

                # Второй запрос — GPT формулирует финальный ответ
                final = self.client.chat.completions.create(
                    model=GPT_MODEL,
                    messages=self.history,
                    max_tokens=200,
                    temperature=0.7,
                )
                answer = final.choices[0].message.content.strip()

            # ── Обычный текстовый ответ ────────────────────────────────────
            else:
                answer = msg.content.strip() if msg.content else "..."
                self.history.append({"role": "assistant", "content": answer})

            # Ограничиваем историю
            if len(self.history) > 22:
                self.history = [self.history[0]] + self.history[-20:]

            return answer

        except Exception as e:
            print(f"  [!] Ошибка OpenAI: {e}")
            return "Произошла ошибка при обращении к серверу."

    def reset_history(self):
        """Сбрасывает историю диалога."""
        self.history = []
        self._rebuild_system()

    def refresh_language(self):
        """Обновляет системный промпт при смене языка."""
        self._rebuild_system()