"""CLI test harness for the Kirana agent loop.

Runs the ADK control loop on stdin — type messages, see responses.
Useful for testing before wiring Telegram.
"""

import asyncio
import sys


async def main():
    chat_id = "cli-test"
    print("Kirana Agent CLI — type a message")
    print("  /new    — new chat (preferences preserved)")
    print("  /quit   — exit\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input == "/quit":
            break
        if user_input == "/new":
            from kirana.agent.loop import clear_session
            await clear_session(chat_id)
            print("(New chat — preferences still active)\n")
            continue

        from kirana.agent.loop import handle_message
        result = await handle_message(chat_id, user_input)

        print(f"Agent: {result['text']}")
        suggestions = result.get("suggestions", [])
        if suggestions:
            for i, opt in enumerate(suggestions, 1):
                print(f"  [{i}] {opt}")
            print("(Type a number or your own answer)")
        print()
        if result.get("files"):
            for f in result["files"]:
                print(f"  📎 {f}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
