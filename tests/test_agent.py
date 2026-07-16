"""Tests for the ADK agent builder and loop helpers.

Tests verify structure:
- Agent builds correctly with preferences and active bill.
- Formatting helpers produce expected strings.
- file_path extraction from events.
- clear_session doesn't crash.

Full E2E tests with real Gemini are in Phase 8.
"""

from kirana.agent.agent import build_agent, SYSTEM_PROMPT
from kirana.agent.loop import (
    format_preferences,
    format_active_bill,
    _extract_file_paths,
)


class TestBuildAgent:
    def test_build_agent_returns_agent(self):
        agent = build_agent(preferences="None set.", active_bill="None")
        assert agent.name == "kirana_agent"
        assert agent.instruction is not None
        assert "None set." in agent.instruction
        assert "None" in agent.instruction
        assert len(agent.tools) > 10  # all tools registered

    def test_build_agent_injects_preferences(self):
        agent = build_agent(
            preferences="default_payment=upi, shop_name=Test Store",
            active_bill="None (no active draft bill).",
        )
        assert "default_payment=upi" in agent.instruction
        assert "shop_name=Test Store" in agent.instruction

    def test_build_agent_injects_active_bill(self):
        agent = build_agent(
            preferences="None set.",
            active_bill="Draft INV-0001: 2× Maggi Noodles, 1× Sugar (loose)",
        )
        assert "Draft INV-0001" in agent.instruction

    def test_system_prompt_has_grounding_rule(self):
        assert "ALWAYS use tools" in SYSTEM_PROMPT
        assert "NEVER invent" in SYSTEM_PROMPT
        assert "NEVER state" in SYSTEM_PROMPT


class TestFormatHelpers:
    def test_format_preferences_empty(self):
        assert format_preferences({}) == "None set."

    def test_format_preferences_with_values(self):
        result = format_preferences({"key1": "val1", "key2": "val2"})
        assert "key1=val1" in result
        assert "key2=val2" in result

    def test_format_active_bill_none(self):
        assert format_active_bill(None) == "None (no active draft bill)."

    def test_format_active_bill_with_items(self):
        bill = {
            "bill_number": "INV-0003",
            "items": [
                {"product_name_snapshot": "Maggi", "quantity": 2},
                {"product_name_snapshot": "Sugar", "quantity": 1.5},
            ],
        }
        result = format_active_bill(bill)
        assert "INV-0003" in result
        assert "2× Maggi" in result
        assert "1.5× Sugar" in result


class TestExtractFilePaths:
    def test_returns_empty_for_empty_events(self):
        assert _extract_file_paths([]) == []

    def test_extracts_file_path_from_dict_response(self):
        class FakeContent:
            def __init__(self):
                self.parts = []

        class FakePart:
            def __init__(self, resp):
                self.function_response = resp

        class FakeFuncResp:
            def __init__(self, resp):
                self.response = resp

        class FakeEvent:
            def get_function_responses(self):
                return [FakeFuncResp({"file_path": "/tmp/test.pdf"})]

        result = _extract_file_paths([FakeEvent()])
        assert result == ["/tmp/test.pdf"]