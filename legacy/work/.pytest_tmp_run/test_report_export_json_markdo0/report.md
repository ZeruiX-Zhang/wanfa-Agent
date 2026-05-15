# Embedding 模型评分报告: BAAI/bge-m3

## 模型信息
- Provider: local_bge
- 维度: 1024
- 最大输入长度: 8192

## 综合评分
- 综合评分: 80 / 100
- 等级: Good
- 进度条: [################....] 80%
- 检索质量: 80
- 语义区分度: 77
- 上下文质量: 80
- 工程可用性: 84

## 指标表格
| 指标 | 当前值 | 归一化分数 | 权重 | 加权得分 | 判断 | 解释 | 建议 |
|---|---:|---:|---:|---:|---|---|---|
| Recall@5 | 0.86 | 86 | 18.00 | 15.48 | Excellent | Whether top 5 results recall the expected evidence. | 补充业务问法、检查切片粒度，必要时开启 hybrid retrieval。 |
| nDCG@10 | 0.79 | 79 | 14.00 | 11.06 | Good | Whether relevant evidence is ranked near the top. | 增加 reranker，或优化 query rewrite 和标题 metadata。 |
| MRR@10 | 0.78 | 78 | 10.00 | 7.80 | Good | Rank of the first relevant evidence. | 提升首个正确证据排名，可加入 rerank 和 hard negative cases。 |
| Hit@1 | 0.72 | 72 | 7.00 | 5.04 | Usable | Whether the first result directly hits expected evidence. | 强化高价值 FAQ、术语同义词和标题路径。 |
| Precision@5 | 0.74 | 74 | 6.00 | 4.44 | Usable | Share of relevant results in top 5. | 降低噪声 chunk，收紧过滤条件或提高 rerank 权重。 |
| Pair Accuracy | 0.88 | 88 | 5.00 | 4.40 | Excellent | Positive pairs should score higher than negative pairs. | 补充正负样本对，覆盖核心业务概念。 |
| Hard Negative Margin | 0.09 | 60 | 7.00 | 4.20 | Usable | Separates near but semantically different business concepts. | 增加容易混淆的 hard negative 测试，如退款流程与退货规则。 |
| Score Distribution Quality | distribution score 100 | 100 | 3.00 | 3.00 | Excellent | Positive and negative score distributions should be separable. | 检查相似度分布，补充更真实的负样本和近义业务问题。 |
| Context Recall | 0.80 | 80 | 5.00 | 4.00 | Good | Required evidence is included in final context. | 提高 top_k、优化切片和召回融合策略。 |
| Context Precision | 0.78 | 78 | 5.00 | 3.90 | Good | Final context is concise and low noise. | 减少过长 chunk，过滤重复内容，启用 rerank。 |
| Citation Support Rate | 0.83 | 83 | 5.00 | 4.15 | Good | Citations support the answer and are system-generated. | 检查 citation formatter 和 chunk metadata，避免引用不支持答案。 |
| Avg Latency | 620ms | 81 | 5.00 | 4.03 | Good | Average embedding and retrieval latency. | 调大 batch，使用本地缓存或更快的 embedding provider。 |
| P95 Latency | 1700ms | 88 | 3.00 | 2.65 | Excellent | Tail latency. | 检查长尾请求、超时重试和并发批处理。 |
| Cost / 1k chunks | 0.0300 | 67 | 3.00 | 2.00 | Usable | API or local inference cost. | 降低 API 调用量，缓存 embedding，或改用本地模型。 |
| Storage / 1k chunks | 3.91 MB | 100 | 2.00 | 2.00 | Excellent | Storage cost from embedding dimension and chunk count. | 控制维度和 chunk 数，按 collection 做生命周期管理。 |
| Stability | 2.0% failure | 98 | 2.00 | 1.96 | Excellent | Failure rate, timeout rate, NaN/Inf and dimension stability. | 排查失败率、超时、NaN/Inf 和维度不一致问题。 |

## 模型对比表
| 模型 | Provider | 维度 | 综合评分 | 等级 | Recall@5 | nDCG@10 | MRR@10 | 推荐用途 |
|---|---|---:|---:|---|---:|---:|---:|---|
| BAAI/bge-m3 | local_bge | 1024 | 80 | Good | 86 | 79 | 78 | 企业知识库试运行 |

## 自然语言解释
BAAI/bge-m3 在当前知识库测试集中综合评分为 80/100，等级 Good。优势在 Score Distribution Quality、Storage / 1k chunks，说明相关证据召回或工程表现较稳。短板是 Hard Negative Margin、Cost / 1k chunks，建议增加容易混淆的 hard negative 测试，如退款流程与退货规则。

## 风险提示
- 当前未发现阻断性风险，仍建议用真实业务 eval set 复测。

## 推荐动作
适合大多数企业知识库场景，可进入试运行。建议继续优化 Hard Negative Margin 和 Cost / 1k chunks。