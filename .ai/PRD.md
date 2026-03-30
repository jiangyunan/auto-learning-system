# 全自动文档学习系统（Auto Learning System）PRD + 技术方案

## 一、项目目标

构建一个**本地优先、低成本、可扩展、可开源**的系统，实现：

* 自动抓取任意技术文档（如 LlamaIndex / LangGraph / API Docs）
* 自动分析结构
* 自动生成学习笔记（中文）
* 自动写入 Obsidian
* 支持增量更新
* 支持工作流编排（n8n / 自定义）

---

## 二、核心设计原则

1. **低 Token 成本优先**

   * 先压缩再翻译
   * 分块处理
   * 本地模型优先

2. **模块化（适合开源）**

   * crawler（抓取）
   * processor（处理）
   * llm（推理）
   * exporter（输出）

3. **完全可替换**

   * 支持 OpenAI / Ollama / 其他模型
   * 支持不同存储（Obsidian / DB）

---

## 三、系统架构

```
                ┌──────────────┐
                │   Scheduler   │
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │   Crawler     │
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │   Chunker     │
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ Summarizer L1 │（压缩）
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ Summarizer L2 │（整理+翻译）
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ Formatter     │（Obsidian）
                └──────┬───────┘
                       ↓
                ┌──────────────┐
                │ Exporter      │
                └──────────────┘
```

---

## 四、功能模块拆解

### 1. 文档抓取模块（Crawler）

#### 功能

* 抓取单页
* 抓取整站（递归）
* 支持 sitemap

#### 输入

```
{
  "url": "https://docs.xxx.com",
  "depth": 2
}
```

#### 输出

```
[
  {
    "url": "...",
    "title": "...",
    "content": "..."
  }
]
```

---

### 2. 文本分块模块（Chunker）

#### 目的

* 控制 token
* 提高总结质量

#### 策略

* 每块 1000~2000 tokens
* 按段落切分

---

### 3. 一级总结（压缩层）

#### Prompt

```
Summarize into key bullet points:
- Keep only core concepts
- Remove examples
- Max 200 words
```

#### 输出

* 高密度信息摘要（英文）

---

### 4. 二级总结（学习笔记层）

#### Prompt

```
将以下内容整理为中文学习笔记：

要求：
1. 分模块
2. 提取核心概念
3. 输出 Markdown
```

---

### 5. Obsidian 格式化模块

#### 输出标准

```
# 标题

## 模块
- 概念

## [[关联概念]]

#标签
```

---

### 6. 导出模块（Exporter）

支持：

* Obsidian（.md）
* JSON
* Markdown 文件夹结构

---

## 五、数据结构设计

### Document

```
{
  "id": "",
  "url": "",
  "content": "",
  "metadata": {}
}
```

---

### Chunk

```
{
  "doc_id": "",
  "text": "",
  "index": 0
}
```

---

### Summary

```
{
  "chunk_id": "",
  "summary": ""
}
```

---

### Note

```
{
  "title": "",
  "content": "",
  "tags": []
}
```

---

## 六、核心工作流（可导入 Claude Code）

```
1. fetch_docs(url)
2. split_chunks(docs)
3. summarize_level1(chunks)
4. merge_summary()
5. summarize_level2()
6. format_obsidian()
7. save_file()
```

---

## 七、配置设计（config.yaml）

```
model:
  type: ollama
  name: llama3

crawler:
  max_depth: 2

chunk:
  size: 1500

output:
  format: obsidian
  path: ./vault/

language:
  target: zh
```

---

## 八、项目目录结构（GitHub友好）

```
auto-learning-system/
│
├── README.md
├── requirements.txt
├── config.yaml
│
├── crawler/
│   └── crawler.py
│
├── processor/
│   ├── chunker.py
│   ├── summarizer.py
│
├── llm/
│   └── client.py
│
├── exporter/
│   └── obsidian.py
│
├── workflows/
│   └── pipeline.py
│
└── main.py
```

---

## 九、README（开源模板）

### 项目介绍

自动学习任意技术文档，并生成 Obsidian 笔记。

### 功能

* 自动抓文档
* 自动总结
* 自动翻译
* 自动生成知识库

### 快速开始

```
pip install -r requirements.txt
python main.py --url https://docs.xxx.com
```

---

## 十、n8n 工作流设计（可选）

节点：

```
HTTP → Function → LLM → Merge → LLM → File
```

---

## 十一、性能优化

### 1. Token优化

* 分块
* 压缩优先
* 避免重复总结

### 2. 缓存

```
hash(url) → summary
```

### 3. 增量更新

* 只处理新增页面

---

## 十二、未来扩展

* 多语言支持
* 自动知识图谱
* AI问答接口
* GitHub同步
* 多文档融合学习

---

## 十三、版本规划

### v1

* 单文档学习
* Obsidian输出

### v2

* 全站抓取
* 增量更新

### v3

* 多文档融合
* 知识图谱

---

## 十四、一句话总结

这是一个：

> **“自动学习任何技术文档，并沉淀为知识库”的系统**

核心优势：

* 低成本
* 可控
* 可扩展
* 适合开源
