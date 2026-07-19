"""agent.schemas 单元测试：QuizOutput._coerce_options 容错分支。

纯单元测试，无 DB/LightRAG/LLM 依赖。
"""
import pytest

from teaching_agent_api.agent.schemas import QuizOutput, EvaluationOutput


def _make(**options_override) -> QuizOutput:
    data = {"q_type": "single", "stem": "q", "answer": "a", "analysis": "an"}
    data.update(options_override)
    return QuizOutput.model_validate(data)


def test_options_none():
    assert _make(options=None).options is None


def test_options_list_of_str():
    assert _make(options=["A", "B", "C"]).options == ["A", "B", "C"]


def test_options_list_coerces_non_str_items():
    assert _make(options=["A", 1, True]).options == ["A", "1", "True"]


def test_options_json_string_parsed():
    assert _make(options='["A","B","C"]').options == ["A", "B", "C"]


def test_options_bare_string_wrapped():
    assert _make(options="A").options == ["A"]


def test_options_invalid_json_string_wrapped():
    # 非 JSON 的裸字符串 '[A,B' 应被当作单个选项
    assert _make(options="[A,B").options == ["[A,B"]


def test_options_invalid_type_becomes_none():
    assert _make(options=123).options is None


def test_options_default_none_when_omitted():
    assert _make().options is None


def test_evaluation_output_fields():
    e = EvaluationOutput.model_validate(
        {"verdict": "correct", "diagnosis": "", "analysis": "ok"}
    )
    assert e.verdict == "correct"
    assert e.diagnosis == ""
    assert e.analysis == "ok"


def test_quiz_output_rejects_invalid_q_type():
    with pytest.raises(Exception):
        QuizOutput.model_validate(
            {"q_type": "invalid", "stem": "q", "answer": "a", "analysis": "an"}
        )
