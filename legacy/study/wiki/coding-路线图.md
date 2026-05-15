# AI 编程与大模型 - 学习路线图

> 状态：进行中  
> 方向：AI 辅助编程 + 大模型原理 → 算法研究级别  
> 前提：Python 有基础（变量、循环、函数）

---

## 两条并行主线

```
主线 A：AI 编程能力（工具 + 工程）
  → 用 AI 工具高效写代码 → 用 API 搭应用 → 搭训练/推理 pipeline

主线 B：大模型原理（理论 + 研究）
  → 数学基础 → ML/DL 基础 → Transformer → LLM 训练 → 前沿论文
```

两条线**同时推进**，互相支撑：学原理时用 AI 工具辅助写代码，用工具时理解底层在做什么。

---

## 主线 A：AI 编程能力

### A1: Python for AI（2 周）
**验收标准**：能用 NumPy 做矩阵运算，能用 Python class 组织代码

- [ ] NumPy 核心操作：array, reshape, broadcasting, 矩阵乘法
- [ ] 数据处理：pandas 基础，读写 CSV/JSON
- [ ] Python 进阶：class, decorator, context manager, type hints
- [ ] 虚拟环境 & 包管理：conda / venv / pip
- [ ] **里程碑**：用 NumPy 手写一个简单的线性回归

### A2: AI 编程工具链（2 周）
**验收标准**：能高效使用 AI 工具完成编程任务，能判断 AI 生成代码的质量

- [ ] Cursor：Tab 补全、Cmd+K 编辑、Chat、Composer 的使用场景
- [ ] Claude Code / Copilot：命令行 AI 编程
- [ ] Prompt Engineering for Code：如何写出好的编程 prompt
- [ ] AI 生成代码的审查：识别 hallucination、安全隐患、性能问题
- [ ] **里程碑**：用 AI 工具从零搭一个完整项目，记录哪些 AI 做得好/哪些需要人工修正

### A3: AI 应用开发（3 周）
**验收标准**：能用 LLM API 搭建一个带 RAG 的应用

- [ ] OpenAI / Anthropic API 调用
- [ ] Prompt Engineering 进阶：system prompt, few-shot, chain-of-thought
- [ ] RAG 基础：Embedding, Vector DB (FAISS/Chroma), 检索增强生成
- [ ] AI Agent 框架：LangChain / LlamaIndex 基础
- [ ] 工具调用（Tool Use / Function Calling）
- [ ] **里程碑**：搭一个能检索自己 wiki/ 文件夹的 AI 学习助手

### A4: 训练与微调工程（4 周）
**验收标准**：能在自己的数据上 fine-tune 一个小模型

- [ ] PyTorch 基础：Tensor, autograd, nn.Module, DataLoader
- [ ] Hugging Face 生态：Transformers, Datasets, Tokenizers, PEFT
- [ ] Fine-tuning 实战：LoRA / QLoRA 微调一个 7B 模型
- [ ] 训练监控：Loss 曲线、Wandb
- [ ] 推理部署：量化（GPTQ, AWQ）、vLLM、Ollama
- [ ] **里程碑**：用 LoRA 在自定义数据集上微调并部署一个模型

---

## 主线 B：大模型原理

### B1: 数学基础（3-4 周，与 A1 并行）
**验收标准**：能手推 backpropagation，能解释 softmax 的概率含义

- [ ] 线性代数：向量、矩阵乘法、特征值、SVD
- [ ] 微积分：偏导数、链式法则、梯度
- [ ] 概率论：条件概率、贝叶斯、分布（高斯、多项式）
- [ ] 优化：梯度下降、学习率、Adam、Loss Landscape
- [ ] 信息论基础：Entropy, Cross-Entropy, KL Divergence
- [ ] **里程碑**：手推一个 2 层神经网络的 forward + backward pass

### B2: 机器学习基础（3 周）
**验收标准**：能解释 bias-variance tradeoff，能选择合适的模型和评估方式

- [ ] 监督学习：线性回归、逻辑回归、SVM、决策树
- [ ] 核心概念：过拟合/欠拟合、正则化、交叉验证
- [ ] 评估指标：Accuracy, Precision, Recall, F1, AUC
- [ ] 无监督学习：K-means、PCA（降维）
- [ ] **里程碑**：在一个真实数据集上完成完整的 ML pipeline

### B3: 深度学习基础（3-4 周）
**验收标准**：能从零实现一个简单的神经网络，能解释 CNN/RNN 的核心思想

- [ ] 神经网络：感知机 → MLP → 激活函数 → 反向传播
- [ ] CNN：卷积、池化、特征图（直觉理解即可，非重点）
- [ ] RNN / LSTM / GRU：序列建模（理解局限性，为 Transformer 铺垫）
- [ ] 训练技巧：BatchNorm, Dropout, Learning Rate Scheduling, Weight Init
- [ ] **里程碑**：用 PyTorch 从零实现一个字符级语言模型（参考 Karpathy makemore）

### B4: Transformer 深入（4-6 周）⭐ 核心阶段
**验收标准**：能闭卷画出 Transformer 架构，能解释每个组件的数学原理和设计动机

- [ ] Self-Attention 机制：Q/K/V, Scaled Dot-Product, Multi-Head
- [ ] Positional Encoding：为什么需要、Sinusoidal vs RoPE vs ALiBi
- [ ] Transformer 完整架构：Encoder-Decoder vs Decoder-Only
- [ ] 预训练目标：Masked LM (BERT) vs Autoregressive (GPT) vs Prefix LM
- [ ] Tokenization：BPE, WordPiece, SentencePiece, Tokenizer 的影响
- [ ] Scaling Laws：参数量、数据量、算力的关系
- [ ] 上下文长度扩展：Flash Attention, Sparse Attention, Ring Attention
- [ ] **里程碑**：从零实现一个 mini GPT（参考 Karpathy nanoGPT）

### B5: LLM 训练全流程（4 周）
**验收标准**：能完整描述一个 LLM 从预训练到上线的全流程

- [ ] 预训练（Pre-training）：数据清洗、Tokenization、训练目标
- [ ] 指令微调（SFT）：数据格式、对话模板
- [ ] 人类反馈对齐：RLHF（PPO）、DPO、ORPO
- [ ] 评估方法：Perplexity、人工评估、基准测试（MMLU, HumanEval 等）
- [ ] 安全与对齐：Red Teaming、Constitutional AI、Guardrails
- [ ] 分布式训练：Data Parallel, Tensor Parallel, Pipeline Parallel, ZeRO
- [ ] **里程碑**：读完 LLaMA / Qwen 的技术报告并写出结构化笔记

### B6: 前沿研究（持续）
**验收标准**：能每周读 1-2 篇论文，能识别论文的核心贡献和局限

- [ ] 论文阅读方法论：三遍阅读法、如何判断论文价值
- [ ] Mixture of Experts (MoE)
- [ ] 长上下文建模
- [ ] 多模态模型（Vision-Language Models）
- [ ] Reasoning & Chain-of-Thought
- [ ] AI Agent 系统设计
- [ ] 持续关注 arXiv cs.CL, cs.LG 最新进展
- [ ] **里程碑**：选一篇论文复现其核心实验

---

## 编程领域特殊规则

### 验收方式
| 标准 | 含义 | 验证方式 |
|------|------|----------|
| **能解释** | 用自己的话讲清原理 | 闭卷复述 + 画图 |
| **能推导** | 手推数学公式 | 纸上推导关键步骤 |
| **能实现** | 写出能运行的代码 | 不看文档写代码 |
| **能调试** | 定位训练/推理问题 | 给出异常场景排查 |
| **能批判** | 读论文能找出问题 | 写论文笔记含局限性分析 |

### AI 工具使用原则（关键！）
- **用 AI 写代码 ≠ 你会编程**——你必须能解释 AI 写的每一行
- 用 AI 工具时，先自己想思路，再让 AI 实现，最后 review
- 遇到 AI 写错的代码，是最好的学习机会——分析为什么错
- 原理学习阶段，某些代码必须手写（如 attention, backprop），不要让 AI 代劳

### 学习节奏
- 主线 A 和 B 交替推进，不要只学理论或只用工具
- 每学一个原理，用代码验证（理论:代码 = 4:6）
- 每周至少读一篇论文/技术博客（从 B4 开始）
- 用英文材料为主（论文、文档都是英文，与英语学习交叉）

---
更新记录：
- [初始创建] 调整为 AI 编程 + 大模型方向
