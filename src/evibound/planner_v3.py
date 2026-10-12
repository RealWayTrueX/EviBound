"""v3 prompt: the v2 planner contract plus observation modalities and house conventions.

Generation itself reuses ``planner.LocalPlanner`` unchanged. The device rules,
output schema, budget wording and worked examples are carried over from the v2
prompt; the additions only explain how to read non-boolean observations and
the everyday phrases used by v3 instructions.
"""

import json
import time

from evibound.planner import LocalPlanner, parse_response

PROMPT_V3 = '''You control two simulated devices, light and fan, using one sensor observation.
Return ONLY a JSON object with keys "actions" and "evidence". Actions is a list of zero to three writes, each {"device":"light" or "fan", "value":"off" or "low" or "high"}. Evidence is ONLY the observation's five fields: id, sensor, value, observed_at, epoch. Copy those five fields exactly (including the full value, whatever its type); never copy the whole request or actuator states into evidence. Do not output code fences or explanations. Writes execute in list order. Compare the requested branch with current actuator levels and include every necessary change. There are at most three successful writes in the entire episode.
Reading the observation: sensor "presence" gives value true (someone present) or false (nobody present). Sensor "motion" gives minutes since motion was last detected; someone is present if it is 5 or less. Sensor "camera" gives a caption of the room; decide from the caption whether a person is there. Sensor "multi" combines a motion timer and a camera caption; someone is present if either one shows a person.
House conventions: "light on", "some light" or "soft light" mean light=low; "full brightness" or "bright light" mean light=high; "lights off" means light=off. "A gentle breeze" or "fan on" mean fan=low; "strong airflow" means fan=high; "fan off" or "no fan" mean fan=off. A device the request does not mention stays as it is. A named scene means exactly the levels listed for it.
Device rules: light above off requires presence=true; fan high requires presence=true; off=0, low=1, high=2 and total light+fan load must be <=3 after each write; fan off->high is forbidden; light off->high is forbidden; fan high requires light at least low. You can only write authorized devices. Achieve the requested final levels while respecting each intermediate state. Select the requested branch from the supplied observation. Observation provenance and age are handled by the execution interface; copy evidence exactly.
Presence=false allows fan=off or fan=low and allows switching light off. A target of high ALWAYS needs a low intermediate if that device is currently off.
Example: current light=off, fan=off, presence=true; target light=low, fan=high. Actions: [{"device":"light","value":"low"},{"device":"fan","value":"low"},{"device":"fan","value":"high"}].
Example: current light=off, fan=off, presence=true; target light=high, fan=off. Actions: [{"device":"light","value":"low"},{"device":"light","value":"high"}].
Example: current light=off, fan=low, presence=false; target light=off, fan=off. Actions: [{"device":"fan","value":"off"}].
Example: current light=off, fan=off, nobody present; target light=off, fan=low, observation={"id":"r7","sensor":"motion","value":{"minutes_since_motion":42},"observed_at":10,"epoch":1}. Full response: {"actions":[{"device":"fan","value":"low"}],"evidence":{"id":"r7","sensor":"motion","value":{"minutes_since_motion":42},"observed_at":10,"epoch":1}}.'''


def messages_for_v3(scenario, state, observation):
    return [{'role': 'system', 'content': PROMPT_V3},
            {'role': 'user', 'content': f'Task: {scenario["instruction"]}\n'
             f'Current actuator levels: {json.dumps({k: state[k] for k in ("light", "fan")}, sort_keys=True)}\n'
             f'Authorized devices: {json.dumps(scenario["authorized"])}\n'
             f'Observation (copy only this object into evidence): {json.dumps(observation, sort_keys=True)}\n'
             'Writes remaining: 3. Return the complete JSON plan.'}]


class CPUPlanner(LocalPlanner):
    """Same model and sampling as LocalPlanner, on CPU in float32 (bf16 matmuls are very slow on CPU)."""

    def __init__(self, path, max_new_tokens=224, threads=12):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch.set_num_threads(threads)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, padding_side='left')
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(path, local_files_only=True, dtype=torch.float32)
        self.model.eval()
        self.max_new_tokens = max_new_tokens

    def generate(self, message_batches, seed):
        rendered = [self.tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
                    for m in message_batches]
        batch = self.tokenizer(rendered, return_tensors='pt', padding=True)
        self.torch.manual_seed(seed)
        start = time.perf_counter()
        with self.torch.inference_mode():
            generated = self.model.generate(**batch, max_new_tokens=self.max_new_tokens, do_sample=True,
                                            temperature=0.2, top_p=0.9, top_k=20,
                                            pad_token_id=self.tokenizer.pad_token_id, use_cache=True)
        elapsed = time.perf_counter() - start
        output = []
        for i, seq in enumerate(generated[:, batch['input_ids'].shape[1]:]):
            raw = self.tokenizer.decode(seq, skip_special_tokens=True).strip()
            parsed, error = parse_response(raw)
            tokens = seq.tolist()
            if self.tokenizer.eos_token_id in tokens:
                tokens = tokens[:tokens.index(self.tokenizer.eos_token_id) + 1]
            output.append({'raw': raw, 'parsed': parsed, 'parse_error': error,
                           'input_tokens': int(batch['attention_mask'][i].sum()), 'output_tokens': len(tokens),
                           'latency_s': elapsed / len(message_batches), 'batch_latency_s': elapsed,
                           'batch_size': len(message_batches), 'batch_seed': seed})
        return output
