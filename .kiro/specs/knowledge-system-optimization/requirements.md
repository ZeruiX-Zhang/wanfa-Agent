# Requirements Document

## Introduction

本文档定义 Reality OS 知识系统优化的需求规格。该优化针对现有系统的三个核心子系统进行增强：

1. **知识入库管线** — 引入模型 API 辅助的知识总结与优化，同时保留 Skill 驱动的结构化验证和人工监督门控，确保入库信息的准确性和可复用性。
2. **搜索策略引擎** — 将搜索策略从硬编码触发词匹配升级为 Skill 驱动的可配置策略系统，使搜索行为更贴合用户实际场景。
3. **现实辅助推理** — 将现有的代码层思维模型 + Skill 组合升级为混合推理架构，引入上下文感知的动态策略选择，提升对用户实际情况的辅助质量。

本优化基于现有 `knowledge_core.py`、`expert_search.py`、`thinking_models/` 和 `orchestrator.py` 模块进行增强，不破坏现有 API 契约。

## Glossary

- **Knowledge_Pipeline**: 知识入库管线，负责从原始内容到正式知识条目的完整处理流程，包括清洗、评分、验证、入库
- **Quality_Gate**: 质量门控，在知识入库前执行的多层验证检查点，包括 Skill 验证和人工审核
- **Model_Summarizer**: 模型总结器，调用配置的 LLM API 对知识内容进行摘要、结构化和优化
- **Skill_Validator**: Skill 验证器，基于 SKILL.md 定义的结构化规则对知识内容进行确定性验证
- **Search_Strategy_Engine**: 搜索策略引擎，根据查询意图、用户画像和领域上下文动态选择搜索策略
- **Search_Skill**: 搜索 Skill，以 SKILL.md 格式定义的可插拔搜索策略模板
- **Reality_Advisor**: 现实辅助推理器，结合用户画像、知识库证据和外部搜索结果为用户提供情境化建议
- **Hybrid_Reasoning**: 混合推理，将确定性 Skill 路由与 LLM 生成能力结合的推理模式
- **Human_Oversight**: 人工监督，系统中需要人类明确确认才能继续的决策点
- **Confidence_Score**: 置信度分数，0.0-1.0 范围内表示系统对某条知识或答案可靠性的评估值
- **Absorption_Pipeline**: 吸收管线，现有 `KnowledgeCore.absorb()` 方法实现的知识入库流程
- **Evidence_Snapshot**: 证据快照，对外部来源内容的不可变记录，用于溯源和审计

## Requirements

### Requirement 1: 模型辅助知识总结

**User Story:** As a 知识管理者, I want 系统调用模型 API 对入库知识进行智能总结和结构化优化, so that 知识条目更精炼、更易检索和复用。

#### Acceptance Criteria

1. WHEN 一条新知识通过 Absorption_Pipeline 入库, THE Model_Summarizer SHALL 调用已配置的 generator 模型槽位生成该知识的结构化摘要，摘要包含：核心观点、适用场景、关键约束
2. IF generator 模型槽位未配置或调用失败, THEN THE Knowledge_Pipeline SHALL 回退到现有的确定性摘要逻辑，不阻塞入库流程
3. WHEN Model_Summarizer 生成摘要完成, THE Knowledge_Pipeline SHALL 将原始内容和模型生成摘要同时保存，原始内容作为 evidence，摘要标记为 `model_generated`
4. THE Model_Summarizer SHALL 在摘要生成时记录所用模型、耗时和 token 消耗到 trace 系统

### Requirement 2: Skill 驱动的入库验证

**User Story:** As a 知识管理者, I want 系统使用结构化 Skill 规则对知识准确性进行自动验证, so that 不准确或低质量的内容在入库前被标记出来。

#### Acceptance Criteria

1. WHEN 一条知识通过质量评分后准备入库, THE Skill_Validator SHALL 加载与该知识领域匹配的验证 Skill，执行结构化检查
2. THE Skill_Validator SHALL 检查以下维度：事实一致性（与已有知识是否矛盾）、时效性（是否过期）、完整性（关键字段是否缺失）、来源可信度
3. IF Skill_Validator 检测到 critical 级别问题, THEN THE Knowledge_Pipeline SHALL 将该知识标记为 `review_required` 并阻止自动入库
4. WHEN Skill_Validator 检测到 warning 级别问题, THE Knowledge_Pipeline SHALL 在知识条目上附加警告标签，但允许入库
5. THE Skill_Validator SHALL 支持通过新增 SKILL.md 文件扩展验证规则，无需修改代码

### Requirement 3: 人工监督门控

**User Story:** As a 系统管理员, I want 对模型生成的摘要和自动验证结果保留人工审核权, so that 最终入库的知识质量由人类把关。

#### Acceptance Criteria

1. WHEN Model_Summarizer 生成的摘要与原始内容的语义偏差超过可配置阈值, THE Quality_Gate SHALL 触发人工审核流程
2. WHILE 人工审核流程处于激活状态, THE Knowledge_Pipeline SHALL 将待审核知识保持在 `pending_review` 状态，不写入正式知识库
3. WHEN 管理员批准一条待审核知识, THE Knowledge_Pipeline SHALL 将其状态更新为 `approved` 并完成正式入库
4. WHEN 管理员拒绝一条待审核知识, THE Knowledge_Pipeline SHALL 将其状态更新为 `rejected` 并记录拒绝原因到审计日志
5. THE Quality_Gate SHALL 提供批量审核接口，支持管理员一次审核多条待审核知识

### Requirement 4: 知识筛选与入库标准

**User Story:** As a 用户, I want 系统对不同来源的知识应用差异化的入库标准, so that 高可信来源的知识快速入库而低可信来源需要更严格审核。

#### Acceptance Criteria

1. WHEN 知识来源为 `browser_capture`（桌面插件捕获）, THE Knowledge_Pipeline SHALL 将信任级别设为 `untrusted` 并要求至少通过 Skill_Validator 的完整性检查
2. WHEN 知识来源为 `direct_import`（项目文件导入）, THE Knowledge_Pipeline SHALL 将信任级别设为 `internal` 并跳过来源可信度检查，但保留事实一致性检查
3. WHEN 知识来源为 `expert_search`（指定网址搜索）, THE Knowledge_Pipeline SHALL 执行完整的多层过滤：安全扫描 → 来源可信度评分 → Skill 验证 → 用户确认
4. THE Knowledge_Pipeline SHALL 支持用户在入库前预览知识条目的完整评分报告，包括各维度分数和潜在问题
5. IF 知识内容触发 Security_Scanner 的 high 或 critical 级别告警, THEN THE Knowledge_Pipeline SHALL 拒绝自动入库并通知用户

### Requirement 5: Skill 驱动的搜索策略

**User Story:** As a 用户, I want 搜索系统根据我的查询意图和领域自动选择最优搜索策略, so that 搜索结果更贴合我的实际需求。

#### Acceptance Criteria

1. THE Search_Strategy_Engine SHALL 支持以 SKILL.md 格式定义搜索策略，每个策略包含：适用意图信号、源选择规则、结果评分权重调整、后处理指令
2. WHEN 用户发起搜索, THE Search_Strategy_Engine SHALL 根据查询文本的意图信号匹配最佳搜索 Skill
3. WHEN 搜索 Skill 被激活, THE Search_Strategy_Engine SHALL 按照 Skill 定义的规则调整源选择、评分权重和结果排序
4. IF 没有搜索 Skill 匹配当前查询, THEN THE Search_Strategy_Engine SHALL 回退到现有的 `_infer_sources` 确定性逻辑
5. THE Search_Strategy_Engine SHALL 在搜索结果中标注所使用的策略名称，便于用户理解和反馈

### Requirement 6: 搜索查询优化增强

**User Story:** As a 用户, I want 搜索系统利用模型 API 对我的查询进行智能扩展和优化, so that 即使我的表述不精确也能获得高质量结果。

#### Acceptance Criteria

1. WHEN generator 模型槽位已配置且启用, THE Search_Strategy_Engine SHALL 调用模型对用户查询进行语义扩展，生成同义词、相关概念和精确搜索词
2. IF 模型调用失败或超时, THEN THE Search_Strategy_Engine SHALL 回退到现有的 tokenize + stopword 过滤逻辑
3. THE Search_Strategy_Engine SHALL 将模型优化后的查询与原始查询同时执行搜索，取两者结果的并集并去重
4. WHEN 搜索结果返回, THE Search_Strategy_Engine SHALL 在响应中包含原始查询和优化后查询的对比信息

### Requirement 7: 混合推理架构

**User Story:** As a 用户, I want 系统在辅助我解决实际问题时能动态组合确定性 Skill 推理和 LLM 生成能力, so that 我获得既有结构又有深度的建议。

#### Acceptance Criteria

1. WHEN 用户提问且 Orchestrator 处于激活状态, THE Reality_Advisor SHALL 先执行确定性 Skill 路由获取结构化分析框架，再将框架作为约束传递给 LLM 生成详细建议
2. THE Reality_Advisor SHALL 在 LLM 生成阶段将用户画像（level、constraints、error_patterns）注入提示词，使建议贴合用户实际情况
3. IF LLM 生成的建议与 Skill 框架的结构化输出存在矛盾, THEN THE Reality_Advisor SHALL 标记矛盾点并在响应中同时展示两种观点
4. WHEN 用户水平为 `beginner`, THE Reality_Advisor SHALL 在 LLM 建议后附加逐步行动指南和术语解释
5. WHEN 用户水平为 `expert`, THE Reality_Advisor SHALL 省略基础解释，仅输出核心洞察、反例和盲点提示

### Requirement 8: 上下文感知的策略选择

**User Story:** As a 用户, I want 系统根据我的历史交互和当前任务上下文自动调整推理策略, so that 系统的建议随着我的使用越来越精准。

#### Acceptance Criteria

1. WHEN 用户连续 3 次对同一概念领域提问, THE Reality_Advisor SHALL 自动提升该领域的检索深度（增加 top_k）和证据要求
2. THE Reality_Advisor SHALL 读取 Context_Anchor（如果存在）中的当前目标和约束，将其作为推理的前置条件
3. WHEN 用户的 learning_signals 表明某概念掌握度低, THE Reality_Advisor SHALL 在涉及该概念的回答中自动增加解释深度
4. THE Reality_Advisor SHALL 记录每次推理策略选择到 trace 系统，包括选择原因和最终效果评分

### Requirement 9: 知识库总结与定期优化

**User Story:** As a 知识管理者, I want 系统定期对知识库中的存量知识进行总结和优化, so that 知识库保持精炼、无冗余、易于检索。

#### Acceptance Criteria

1. WHEN 管理员触发知识库优化任务, THE Model_Summarizer SHALL 识别内容重叠度超过 70% 的知识条目并建议合并
2. WHEN 知识条目的 freshness_date 超过可配置的过期阈值, THE Knowledge_Pipeline SHALL 将其标记为 `needs_refresh` 并在搜索结果中降低其权重
3. THE Model_Summarizer SHALL 为每个概念节点生成概念摘要，汇总该概念下所有知识条目的核心信息
4. IF 优化过程中发现知识条目之间存在事实矛盾, THEN THE Knowledge_Pipeline SHALL 将冲突条目标记为 `disputed` 并通知管理员
5. THE Knowledge_Pipeline SHALL 保留所有优化操作的完整审计日志，包括合并前后的内容快照
