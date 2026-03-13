# Model Evaluation: Qwen2.5:14b vs Gemma3:27b

## AutoDocx — LLM Comparison for Code Documentation Generation

---

## Precision & Recall Comparison

### ROUGE Scores (Average across fin-sight & insightforce-ai repositories)

| Metric | Gemma3:27b Precision | Gemma3:27b Recall | Gemma3:27b F1 | Qwen2.5:14b Precision | Qwen2.5:14b Recall | Qwen2.5:14b F1 |
|---|---|---|---|---|---|---|
| ROUGE-1 | 0.512 | **0.671** | 0.581 | **0.641** | 0.574 | **0.605** |
| ROUGE-2 | 0.298 | **0.412** | 0.346 | **0.419** | 0.371 | **0.393** |
| ROUGE-L | 0.476 | **0.624** | 0.540 | **0.612** | 0.548 | **0.578** |

### BERTScore (Semantic Similarity)

| Model | Precision | Recall | F1 |
|---|---|---|---|
| Gemma3:27b | 0.812 | **0.847** | 0.829 |
| **Qwen2.5:14b** | **0.857** | 0.821 | **0.839** |

---

## Overall Comparison Table

| Evaluation Dimension | Gemma3:27b | Qwen2.5:14b | Winner |
|---|---|---|---|
| ROUGE-1 Precision | 0.512 | **0.641** | ✅ Qwen2.5 |
| ROUGE-1 Recall | **0.671** | 0.574 | ✅ Gemma3 |
| ROUGE-1 F1 | 0.581 | **0.605** | ✅ Qwen2.5 |
| ROUGE-2 F1 | 0.346 | **0.393** | ✅ Qwen2.5 |
| ROUGE-L F1 | 0.540 | **0.578** | ✅ Qwen2.5 |
| BERTScore Precision | 0.812 | **0.857** | ✅ Qwen2.5 |
| BERTScore Recall | **0.847** | 0.821 | ✅ Gemma3 |
| BERTScore F1 | 0.829 | **0.839** | ✅ Qwen2.5 |
| Section Coverage Recall | **0.846** | 0.808 | ✅ Gemma3 |
| Code Entity Recall | **0.762** | 0.693 | ✅ Gemma3 |
| Technical Content Precision | 0.694 | **0.847** | ✅ Qwen2.5 |
| Format Compliance | 0.769 | **0.892** | ✅ Qwen2.5 |
| Hallucination Rate ↓ | 14.3% | **7.8%** | ✅ Qwen2.5 |
| Avg. Generation Time ↓ | 82 sec | **54 sec** | ✅ Qwen2.5 |
| Model Parameters | 27B | **14B** | ✅ Qwen2.5 |

---

## Key Takeaway

> **Gemma3:27b** has higher **Recall** — it generates more content and covers more topics.
> **Qwen2.5:14b** has higher **Precision** — what it generates is accurate and code-grounded.

For code documentation, **Precision is the dominant metric** because incorrect technical claims (wrong APIs, hallucinated dependencies) are more harmful than missing sections. Qwen2.5:14b also achieves higher F1 on all metrics, making it the recommended model for AutoDocx.
