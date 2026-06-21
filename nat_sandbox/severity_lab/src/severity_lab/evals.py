"""Task-specific eval: score the field that GATES AUTONOMY (severity), not generic text.

The triage workflow returns a JSON blob, so plain exact_match is useless. This custom
evaluator parses the JSON, pulls `severity`, and compares it to the expected severity in
the dataset → an accuracy score. That accuracy is one half of the promotion decision (the
other half is the online dev accept-rate from segment_metrics).
"""
import logging

from nat.plugin_api import EvalBuilder
from nat.plugin_api import EvaluatorBaseConfig
from nat.plugin_api import EvaluatorInfo
from nat.plugin_api import register_evaluator
from nat.plugins.eval.data_models.evaluator_io import EvalOutput, EvalOutputItem

from .scoring import extract_severity, severity_matches   # shared brain (also used by Phoenix)

logger = logging.getLogger(__name__)


class SeverityAccuracyConfig(EvaluatorBaseConfig, name="severity_accuracy"):
    """Scores how often triage's severity matches the expected severity (exact match)."""


@register_evaluator(config_type=SeverityAccuracyConfig)
async def register_severity_accuracy(config: SeverityAccuracyConfig, builder: EvalBuilder):

    async def evaluate(eval_input) -> EvalOutput:
        items: list[EvalOutputItem] = []
        scores: list[float] = []
        for it in eval_input.eval_input_items:
            expected = str(it.expected_output_obj).strip().lower()
            got = extract_severity(it.output_obj)         # shared parse ("" if malformed)
            score = 1.0 if severity_matches(got, expected) else 0.0
            scores.append(score)
            items.append(EvalOutputItem(
                id=it.id, score=score, reasoning=f"expected={expected!r} got={got!r}"))
        avg = sum(scores) / len(scores) if scores else 0.0
        return EvalOutput(average_score=avg, eval_output_items=items)

    yield EvaluatorInfo(config=config, evaluate_fn=evaluate,
                        description="Severity exact-match accuracy")
