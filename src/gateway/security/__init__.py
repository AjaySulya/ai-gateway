"""Phase 8 - security engine and request analyzer.

- request_analyzer.py   input shape/size validation (message count, length
                        limits) - cheap, structural, runs first
- content_filter.py     rules-based prompt-injection detection and PII
                        redaction - both opt-in per policy
                        (block_prompt_injection / redact_pii on
                        gateway.policy.schemas.PolicyConfig), not on by
                        default; ML-based detection is explicitly deferred

gateway.api.chat runs these in the reverse of the architecture diagram's
literal box order (Security Engine, then Request Analyzer) - see chat.py
for why: running regex-based content scanning before basic size validation
would make the size check unable to protect against the thing it exists to
guard against.
"""
