# Implementation Plan: 知识系统优化

## Overview

本实现计划将知识系统优化分为 6 个主要阶段：数据库 Schema 扩展、新增核心模块（model_summarizer、skill_validator、quality_gate、search_strategy、reality_advisor）、现有模块增强、集成联调和最终验证。每个阶段按依赖关系排列，确保基础模块先行、上层模块后续。

## Tasks

- [x] 1. 数据库 Schema 扩展与数据模型更新
  - [x] 1.1 扩展 knowledge_items 表并新增 review_queue、knowledge_summaries、concept_summaries、query_history 表
    - 在 `knowledge_core.py` 的 `_init_schema` 方法中新增 `model_summary_id TEXT`、`needs_refresh INTEGER NOT NULL DEFAULT 0`、`validation_status TEXT NOT NULL DEFAULT 'not_validated'` 列
    - 创建 `review_queue` 表（id, tenant_id, knowledge_item_id, title, original_body, model_summary, divergence_score, validation_result_json, status, reviewer, reject_reason, created_at, reviewed_at）
    - 创建 `knowledge_summaries` 表（id, tenant_id, item_id, core_viewpoint, applicable_scenario, key_constraints, full_summary, model_used, source, divergence_score, created_at）
    - 创建 `concept_summaries` 表（id, tenant_id, concept_id, summary, item_count, model_used, created_at）
    - 创建 `query_history` 表（id, tenant_id, query, domain_concepts, strategy_used, created_at）
    - 添加迁移逻辑确保现有数据库兼容
    - _Requirements: 1.3, 3.1, 3.2, 8.1, 9.3_

  - [x] 1.2 扩展 KnowledgeItem 数据类新增字段
    - 在 `KnowledgeItem` dataclass 中添加 `model_summary_id: str | None = None`、`needs_refresh: bool = False`、`validation_status: Literal["not_validated", "passed", "warning", "failed"] = "not_validated"`
    - 更新 `to_dict()` 方法包含新字段
    - 更新 `_hydrate_item()` 方法从数据库读取新字段
    - _Requirements: 1.3, 9.2_

- [x] 2. 实现 Model Summarizer 模块
  - [x] 2.1 创建 `apps/api/app/model_summarizer.py` 核心实现
    - 实现 `SummaryResult` 数据类（core_viewpoint, applicable_scenario, key_constraints, full_summary, model_used, source, latency_ms, token_estimate, divergence_score）
    - 实现 `ModelSummarizer` 类的 `summarize()` 方法：调用 generator 模型槽位生成结构化摘要
    - 实现 `_deterministic_summary()` 回退方法：基于 tokenize + 句子权重的确定性摘要
    - 实现 `_compute_divergence()` 方法：计算摘要与原文的语义偏差分数
    - 集成 `model_registry.call_model()` 进行 LLM 调用
    - 集成 `trace.record_step()` 和 `trace.record_model_call()` 记录模型调用信息
    - _Requirements: 1.1, 1.2, 1.4_

  - [ ]* 2.2 编写属性测试：模型总结结构完整性
    - **Property 1: 模型总结结构完整性**
    - **Validates: Requirements 1.1**

  - [ ]* 2.3 编写属性测试：模型不可用时的优雅降级
    - **Property 2: 模型不可用时的优雅降级**
    - **Validates: Requirements 1.2, 6.2**

  - [x] 2.4 实现 `summarize_concept()` 和 `detect_overlap()` 方法
    - 实现 `summarize_concept()`：为概念节点生成汇总摘要
    - 实现 `detect_overlap()`：识别内容重叠度超过阈值的知识条目对，基于 token 集合的 Jaccard 相似度
    - _Requirements: 9.1, 9.3_

  - [ ]* 2.5 编写属性测试：内容重叠检测
    - **Property 19: 内容重叠检测**
    - **Validates: Requirements 9.1**

  - [ ]* 2.6 编写属性测试：原始内容与摘要的双重保存
    - **Property 3: 原始内容与摘要的双重保存**
    - **Validates: Requirements 1.3**

  - [ ]* 2.7 编写属性测试：Trace 记录完整性
    - **Property 4: Trace 记录完整性**
    - **Validates: Requirements 1.4, 8.4**

- [x] 3. Checkpoint - 确保模型总结器测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [x] 4. 实现 Skill Validator 模块
  - [x] 4.1 创建 `apps/api/app/skill_validator.py` 核心实现
    - 实现 `ValidationDimension` 和 `ValidationResult` 数据类
    - 实现 `SkillValidator` 类的 `__init__()` 方法：加载验证 Skill 注册表（从 `thinking_skills/` 目录扫描 validation 类型 Skill）
    - 实现 `validate()` 方法：执行完整验证流程
    - 实现 `_match_skill()` 方法：根据领域标签匹配最佳验证 Skill
    - 实现 `_check_fact_consistency()` 方法：检查与已有知识的事实一致性
    - 实现 `_check_timeliness()` 方法：检查时效性
    - 实现 `_check_completeness()` 方法：检查关键字段完整性
    - 实现 `_check_source_credibility()` 方法：检查来源可信度
    - 实现 `reload_skills()` 方法：支持热更新
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 4.2 编写属性测试：验证维度完整性
    - **Property 5: 验证维度完整性**
    - **Validates: Requirements 2.2**

  - [ ]* 4.3 编写属性测试：Critical 验证阻止自动入库
    - **Property 6: Critical 验证阻止自动入库**
    - **Validates: Requirements 2.3, 4.5**

  - [ ]* 4.4 编写属性测试：Warning 验证允许入库但附加标签
    - **Property 7: Warning 验证允许入库但附加标签**
    - **Validates: Requirements 2.4**

  - [x] 4.5 创建示例验证 Skill 文件
    - 创建 `thinking_skills/validation/finance/SKILL.md`：金融领域验证规则
    - 创建 `thinking_skills/validation/tech/SKILL.md`：技术领域验证规则
    - 确保 Skill 文件格式符合设计文档中的 YAML frontmatter 规范
    - _Requirements: 2.5_

- [x] 5. 实现 Quality Gate 模块
  - [x] 5.1 创建 `apps/api/app/quality_gate.py` 核心实现
    - 实现 `ReviewItem` 数据类
    - 实现 `QualityGate` 类的 `submit_for_review()` 方法：提交知识条目到审核队列
    - 实现 `approve()` 方法：批准待审核知识，更新状态为 approved 并完成正式入库
    - 实现 `reject()` 方法：拒绝待审核知识，记录拒绝原因到审计日志
    - 实现 `batch_approve()` 和 `batch_reject()` 方法：批量审核接口
    - 实现 `list_pending()` 方法：列出待审核条目
    - 实现 `get_preview_report()` 方法：生成入库前的完整评分预览报告
    - 集成 `trace.py` 记录审核操作
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.4_

  - [ ]* 5.2 编写属性测试：审核状态机不变量
    - **Property 8: 审核状态机不变量**
    - **Validates: Requirements 3.2, 3.3**

  - [ ]* 5.3 编写属性测试：拒绝操作的审计完整性
    - **Property 9: 拒绝操作的审计完整性**
    - **Validates: Requirements 3.4**

- [x] 6. Checkpoint - 确保入库管线核心模块测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [x] 7. 增强 knowledge_core.py 入库管线
  - [x] 7.1 实现 `absorb_with_pipeline()` 方法
    - 在 `KnowledgeCore` 类中新增 `absorb_with_pipeline()` 方法
    - 集成 ModelSummarizer：调用 `summarize()` 生成摘要，保存到 `knowledge_summaries` 表
    - 集成 SkillValidator：调用 `validate()` 执行验证
    - 集成 QualityGate：当 divergence_score 超过阈值或 severity == critical 时触发人工审核
    - 实现来源差异化信任级别逻辑：browser_capture → untrusted、direct_import → internal、expert_search → 全部检查
    - 实现安全扫描拦截：high/critical 级别告警拒绝自动入库
    - 返回 `(KnowledgeItem, pipeline_metadata)` 元组
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.3, 2.4, 3.1, 4.1, 4.2, 4.3, 4.5_

  - [ ]* 7.2 编写属性测试：来源差异化信任级别
    - **Property 10: 来源差异化信任级别**
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [x] 7.3 实现 `mark_needs_refresh()` 和 `search_with_freshness_penalty()` 方法
    - 实现 `mark_needs_refresh()`：扫描 freshness_date 超过阈值的条目，标记为 needs_refresh
    - 实现 `search_with_freshness_penalty()`：搜索时对 needs_refresh 条目降低权重
    - 记录操作到审计日志
    - _Requirements: 9.2, 9.4, 9.5_

  - [ ]* 7.4 编写属性测试：过期知识的降权
    - **Property 20: 过期知识的降权**
    - **Validates: Requirements 9.2**

  - [ ]* 7.5 编写属性测试：优化操作审计完整性
    - **Property 21: 优化操作审计完整性**
    - **Validates: Requirements 9.5**

- [x] 8. 实现 Search Strategy Engine 模块
  - [x] 8.1 创建 `apps/api/app/search_strategy.py` 核心实现
    - 实现 `SearchSkill` 和 `SearchStrategyResult` 数据类
    - 实现 `SearchStrategyEngine` 类的 `__init__()` 方法：加载搜索策略 Skill 注册表
    - 实现 `select_strategy()` 方法：根据查询意图信号匹配最佳搜索 Skill
    - 实现 `_match_search_skill()` 方法：匹配逻辑
    - 实现 `_fallback_strategy()` 方法：回退到 `_infer_sources` 确定性逻辑
    - 实现 `reload_skills()` 方法：支持热更新
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 8.2 实现 `optimize_query_with_model()` 方法
    - 调用 generator 模型槽位对查询进行语义扩展
    - 生成同义词、相关概念和精确搜索词
    - 模型调用失败时回退到现有 tokenize + stopword 过滤逻辑
    - 记录模型调用到 trace 系统
    - _Requirements: 6.1, 6.2_

  - [ ]* 8.3 编写属性测试：搜索策略路由正确性
    - **Property 11: 搜索策略路由正确性**
    - **Validates: Requirements 5.2, 5.4, 5.5**

  - [ ]* 8.4 编写属性测试：搜索 Skill 配置生效
    - **Property 12: 搜索 Skill 配置生效**
    - **Validates: Requirements 5.3**

  - [x] 8.5 创建示例搜索 Skill 文件
    - 创建 `thinking_skills/search/deep-research/SKILL.md`：深度研究策略
    - 创建 `thinking_skills/search/quick-lookup/SKILL.md`：快速查询策略
    - 确保 Skill 文件格式符合设计文档中的 YAML frontmatter 规范
    - _Requirements: 5.1_

- [x] 9. 增强 expert_search.py 集成策略引擎
  - [x] 9.1 修改 `expert_search()` 函数集成 SearchStrategyEngine
    - 新增 `use_strategy_engine` 和 `use_model_optimization` 参数
    - 当 `use_strategy_engine=True` 时，调用 `SearchStrategyEngine.select_strategy()` 替代硬编码逻辑
    - 当 `use_model_optimization=True` 时，调用 `optimize_query_with_model()` 进行查询扩展
    - 将模型优化后的查询与原始查询同时执行搜索，取并集去重
    - 在响应中新增 `strategy_name`、`original_query`、`optimized_query`、`optimization_source` 字段
    - 保持向后兼容：默认参数不改变现有行为
    - _Requirements: 5.2, 5.3, 6.1, 6.3, 6.4_

  - [ ]* 9.2 编写属性测试：查询优化结果合并去重
    - **Property 13: 查询优化结果合并去重**
    - **Validates: Requirements 6.3, 6.4**

- [x] 10. Checkpoint - 确保搜索策略引擎测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [x] 11. 实现 Reality Advisor 混合推理模块
  - [x] 11.1 创建 `apps/api/app/reality_advisor.py` 核心实现
    - 实现 `AdvisorContext` 和 `AdvisorResponse` 数据类
    - 实现 `RealityAdvisor` 类的 `advise()` 方法：执行混合推理
    - 实现 `_build_context()` 方法：构建用户上下文（画像、锚点、掌握度、历史）
    - 实现 `_detect_domain_repetition()` 方法：检测同一领域连续查询次数，返回深度提升值
    - 实现 `_detect_contradictions()` 方法：检测 Skill 框架与 LLM 建议之间的矛盾
    - 实现 `_format_for_level()` 方法：根据用户水平调整输出格式（beginner 附加行动指南和术语解释，expert 省略基础解释）
    - 集成 thinking_models router 获取 Skill 框架
    - 集成 model_registry 调用 LLM 生成建议
    - 集成 query_history 表记录查询历史
    - 集成 trace 系统记录推理策略选择
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4_

  - [ ]* 11.2 编写属性测试：混合推理的 Skill 框架先行
    - **Property 14: 混合推理的 Skill 框架先行**
    - **Validates: Requirements 7.1**

  - [ ]* 11.3 编写属性测试：用户画像注入
    - **Property 15: 用户画像注入**
    - **Validates: Requirements 7.2**

  - [ ]* 11.4 编写属性测试：Level-aware 输出格式
    - **Property 16: Level-aware 输出格式**
    - **Validates: Requirements 7.4, 7.5**

  - [ ]* 11.5 编写属性测试：领域重复查询的深度提升
    - **Property 17: 领域重复查询的深度提升**
    - **Validates: Requirements 8.1**

  - [ ]* 11.6 编写属性测试：Context Anchor 作为推理前置条件
    - **Property 18: Context Anchor 作为推理前置条件**
    - **Validates: Requirements 8.2**

- [x] 12. 增强 orchestrator.py 集成 RealityAdvisor
  - [x] 12.1 修改 `orchestrated_ask()` 集成混合推理
    - 新增 `use_reality_advisor` 参数
    - 当 `use_reality_advisor=True` 时，调用 `RealityAdvisor.advise()` 替代现有的简单 Skill 路由
    - 在响应中新增 `advisor_context`、`skill_framework`、`contradictions`、`strategy_used` 字段
    - 保持向后兼容：默认参数不改变现有行为
    - 记录推理策略选择到 trace 系统
    - _Requirements: 7.1, 7.2, 7.3, 8.1, 8.2, 8.4_

- [x] 13. Checkpoint - 确保混合推理模块测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [x] 14. API 端点与集成联调
  - [x] 14.1 新增 API 端点暴露新功能
    - 在 `v2.py` 或新建路由文件中添加审核队列相关端点：`GET /api/v2/review/pending`、`POST /api/v2/review/{id}/approve`、`POST /api/v2/review/{id}/reject`、`POST /api/v2/review/batch`
    - 添加知识库优化端点：`POST /api/v2/knowledge/optimize`（触发重叠检测和过期标记）
    - 添加入库预览端点：`POST /api/v2/knowledge/preview`（返回评分报告）
    - 确保所有新端点遵循现有认证和租户隔离模式
    - _Requirements: 3.5, 4.4, 9.1, 9.2_

  - [ ]* 14.2 编写集成测试：完整入库管线端到端
    - 测试从原始内容到正式入库的完整流程
    - 测试模型不可用时的降级路径
    - 测试不同来源的差异化处理
    - _Requirements: 1.1, 1.2, 2.1, 4.1, 4.2, 4.3_

  - [ ]* 14.3 编写集成测试：搜索策略引擎与 expert_search 集成
    - 测试策略引擎选择正确策略
    - 测试模型查询优化与结果合并
    - 测试回退逻辑
    - _Requirements: 5.2, 6.1, 6.3_

  - [ ]* 14.4 编写集成测试：RealityAdvisor 与 Orchestrator 集成
    - 测试混合推理完整流程
    - 测试不同用户水平的输出差异
    - 测试上下文感知的策略调整
    - _Requirements: 7.1, 7.4, 7.5, 8.1_

- [x] 15. Final Checkpoint - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 所有新模块使用 Python 实现，与现有代码风格保持一致
- 每个任务引用具体的需求编号以确保可追溯性
- 属性测试覆盖所有 21 个正确性属性
- Checkpoints 确保增量验证
- 属性测试使用 hypothesis 库，单元测试使用 pytest
- 所有模型调用均通过 `model_registry.call_model()` 统一入口
- 所有新增流程步骤通过 `trace.py` 记录到追踪系统

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "4.2", "4.3", "4.4", "4.5"] },
    { "id": 3, "tasks": ["2.5", "2.6", "2.7", "5.1"] },
    { "id": 4, "tasks": ["5.2", "5.3", "7.1", "8.1"] },
    { "id": 5, "tasks": ["7.2", "7.3", "8.2", "8.5"] },
    { "id": 6, "tasks": ["7.4", "7.5", "8.3", "8.4", "9.1"] },
    { "id": 7, "tasks": ["9.2", "11.1"] },
    { "id": 8, "tasks": ["11.2", "11.3", "11.4", "11.5", "11.6", "12.1"] },
    { "id": 9, "tasks": ["14.1"] },
    { "id": 10, "tasks": ["14.2", "14.3", "14.4"] }
  ]
}
```
