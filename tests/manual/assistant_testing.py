"""Test stubs and drivers for assistant manual tests."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, Optional
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dsl_todolist.assistant import AssistantResult, TodoAssistant


@dataclass
class AssistantScenario:
    name: str
    description: str
    nl_input: str
    model_responses: list[str]
    api_responses: Dict[str, Dict[str, object]]
    expected_action: str
    expected_summary: str


def load_scenarios(path: Optional[Path] = None) -> Dict[str, AssistantScenario]:
    """Load scenario definitions from JSON."""
    file_path = path or Path(__file__).with_name("assistant_scenarios.json")
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    scenarios: Dict[str, AssistantScenario] = {}
    for name, payload in raw.items():
        scenarios[name] = AssistantScenario(
            name=name,
            description=payload.get("description", ""),
            nl_input=payload["nl_input"],
            model_responses=list(payload["model_responses"]),
            api_responses=payload.get("api_responses", {}),
            expected_action=payload.get("expected_action", ""),
            expected_summary=payload.get("expected_summary", ""),
        )
    return scenarios


class ScenarioAssistant(TodoAssistant):
    """TodoAssistant subclass that replays pre-canned model/API responses."""

    def __init__(self, scenario: AssistantScenario) -> None:
        super().__init__(model_name="stub-model", endpoint="http://stub")
        self._scenario = scenario
        self._model_iter: Iterator[str] = iter(scenario.model_responses)

    def _call_model(self, prompt: str) -> str:  # type: ignore[override]
        try:
            response = next(self._model_iter)
        except StopIteration as exc:  # pragma: no cover - manual guard
            raise RuntimeError(
                f"场景 {self._scenario.name} 的 model_responses 已耗尽，请检查定义"
            ) from exc
        print("\n=== Stubbed Prompt ===")
        print(prompt)
        print("=== Stubbed Response ===")
        print(response)
        return response

    def _call_api(self, action: str, data: Dict[str, object]) -> Dict[str, object]:  # type: ignore[override]
        responses = self._scenario.api_responses
        if action not in responses:
            # 默认返回一个成功结果
            return {"status": "ok", "data": {}}
        return responses[action]


def run_scenario(name: str, scenario: AssistantScenario) -> AssistantResult:
    assistant = ScenarioAssistant(scenario)
    return assistant.run_instruction(scenario.nl_input, apply_changes=True)
