"""Planner for a second local model. Exploratory arms only; the frozen planner is untouched.

The frozen planner (``evibound.planner.LocalPlanner``) renders a conversation with the model's own
chat template and passes no further argument. The Qwen3 template opens a reasoning block unless it is
told not to, and the 224 new tokens of the frozen settings would be spent inside it. ``DirectAnswerPlanner``
is the frozen planner with one change: the template is rendered with ``enable_thinking=False``.
Prompt text, sampling, token limit, seeding and parsing are the frozen code, unchanged. A template
without that switch (Qwen2.5) renders exactly as it did before.
"""
from functools import partial

from evibound.planner import LocalPlanner

PROBE = [{'role': 'system', 'content': 'probe'}, {'role': 'user', 'content': 'probe'}]


def describe_switch(tokenizer):
    """What ``enable_thinking`` does to this tokenizer's template, without running the model."""
    render = partial(tokenizer.apply_chat_template, PROBE, tokenize=False, add_generation_prompt=True)
    plain, on, off = render(), render(enable_thinking=True), render(enable_thinking=False)
    template = getattr(tokenizer, 'chat_template', None)
    return {
        'template_mentions_enable_thinking': isinstance(template, str) and 'enable_thinking' in template,
        'switch_changes_the_prompt': on != off,
        'default_equals_thinking_on': plain == on,
        'prompt_tail_as_used': off[-48:],
    }


class DirectAnswerPlanner(LocalPlanner):
    """The frozen planner; the chat template is rendered with thinking switched off."""

    def __init__(self, path, max_new_tokens=224):
        super().__init__(path, max_new_tokens)
        self.switch = describe_switch(self.tokenizer)
        self.tokenizer.apply_chat_template = partial(self.tokenizer.apply_chat_template, enable_thinking=False)
