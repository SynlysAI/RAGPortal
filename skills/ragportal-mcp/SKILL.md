---
name: ragportal-mcp
description: 使用 RAGPortal MCP 检索、列出、读取、下载、上传和查询授权知识库中的文档处理状态。适用于已配置 RAGPortal MCP 服务的外部 Agent 回答知识库问题或按用户要求写入文件。
---

# RAGPortal MCP 使用指南

## 接入

先由用户在 RAGPortal 的“API Token”页面创建 Token，绑定目标知识库并授予所需权限。Token 明文只显示一次。外部 Agent 只连接 RAGPortal，不直接连接 WeKnora。将本目录放入外部 Agent 支持的 Skill 目录，并按该 Agent 的 MCP 配置格式提供服务地址和 Token；以下是支持 `mcpServers` 格式的配置示例：

```json
{
  "mcpServers": {
    "ragportal": {
      "type": "streamable-http",
      "url": "https://你的域名/api/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_TOKEN"
      }
    }
  }
}
```

不要把 Token 写进回答、日志或共享的 Skill 文件。服务端用于生成图片和下载链接的 `MCP_PUBLIC_BASE_URL` 应配置为外部 Agent 能访问的 HTTPS 地址；`127.0.0.1` 和 `localhost` 仅适用于本机调试。

Skill 文件提供调用指导，MCP 服务地址和 Token 仍需配置在客户端的 MCP 设置中。连接后由客户端发现工具；若看不到某个工具，检查 Token 是否勾选了下表所列权限。若工具可见但提示知识库无权访问，检查目标知识库是否仍在 Token 绑定范围内。

## 调用与解析

通过 MCP 客户端按工具名和参数调用；若客户端需要原始 JSON-RPC，检索调用格式如下：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "rag_search",
    "arguments": {"query": "实验条件", "top_k": 5}
  }
}
```

成功的 `tools/call` 响应在 `result.structuredContent` 返回结构化对象；`result.content[0].text` 是同一对象的 JSON 字符串。优先读取 `structuredContent`；客户端未提供该字段时，解析第一个文本块的 JSON。不要把文本块当作检索正文直接拼接。MCP JSON-RPC 的 `error` 表示调用失败，不能当作空检索结果。

## 工具与参数

| 工具 | 所需 Token 权限 | 入参 | 返回重点 |
| --- | --- | --- | --- |
| `rag_list_knowledge_bases` | `knowledge-bases:list` | 无 | `items[]`：Token 绑定的知识库，含 `id`、`name`、`type`。 |
| `rag_list_documents` | `documents:list` | `kb_id` 必填；`page` 默认 1；`page_size` 默认 20，范围 1-100 | `items[]`、`page`、`page_size`、`total`。每项新增 `document_id` 和 `kb_id`，其他字段来自 WeKnora。 |
| `rag_search` | `documents:search` | `query` 必填；`top_k` 默认 5，范围 1-20；可选 `kb_id` 或 `kb_ids` | `items[]`、`kb_ids`、`partial`、`errors[]`、`ranking`。命中字段见下节。 |
| `rag_get_document` | `documents:read` | `document_id` 必填 | `document_id`、`kb_id`、`source`；`source` 为 WeKnora 文档详情，字段随上游返回变化。 |
| `rag_download_file` | `documents:download` | `document_id` 必填 | `document_id`、`filename`、`download_url`、`expires_at`。 |
| `rag_upload_document` | `documents:write` | `kb_id`、`filename`、`content_base64` 必填 | `document_id`、`knowledge_id`、`upload_id`、`filename`。 |
| `rag_get_upload_status` | `documents:write` | 上传结果中的 `document_id` 必填 | `document_id`、`upload_id`、`kb_id`、`filename`、`parse_status`、`enable_status`、`error_message`、`checked_at`。仅限本人上传且 Token 仍绑定的知识库。 |

`document_id` 是 WeKnora 文档 ID，可从检索、文档列表或上传结果取得。`upload_id` 只是 RAGPortal 本地上传记录 ID，不能传给读取或下载工具。只可访问 Token 已绑定的知识库；工具列表也会按 Token 权限过滤。

## 检索与回答

1. 不知道知识库 ID 时，先调用 `rag_list_knowledge_bases`。不指定范围的 `rag_search` 会检索 Token 绑定的全部知识库；限定单库传 `kb_id`，限定多库传 `kb_ids`，不要同时传两者。
2. 调用 `rag_search` 后读取 `items[]`。空列表表示没有命中；`partial: true` 表示部分知识库失败，应检查 `errors[]`，不要声称所有库都已检索成功。全部知识库失败会返回调用错误。
3. 每条命中可包含 `id`（片段 ID）、`document_id`、`knowledge_id`、`knowledge_title`、`knowledge_filename`、`content`、`kb_id`、`kb_name`、`score`、`chunk_index`、`chunk_type` 和可选的 `image_info`。引用来源时优先用文档标题、知识库名称和 `document_id`。
4. `content` 是清理后的命中片段，当前最多 600 字符，不代表文档全文。需要核对文档详情时调用 `rag_get_document`；需要原始文件时调用 `rag_download_file`。`rag_get_document.source` 是否含全文取决于 WeKnora 的返回，不能预设一定有完整正文。

跨库结果按各库内部排名交错合并，`top_k` 是最终返回条数。不要直接用不同知识库的 `score` 比较全局相关性。

以下是 `structuredContent` 的检索结果示例；`content[0].text` 是该对象序列化后的 JSON 字符串：

```json
{
  "items": [{
    "id": "chunk-1",
    "document_id": "wk-1",
    "knowledge_id": "wk-1",
    "knowledge_title": "实验论文",
    "knowledge_filename": "实验论文.pdf",
    "content": "凝胶电泳实验结果片段",
    "kb_id": "kb-a",
    "kb_name": "实验知识库",
    "score": 0.83,
    "chunk_index": 2,
    "chunk_type": "text",
    "image_info": [{
      "caption": "凝胶电泳结果图",
      "markdown_url": "https://rag.example.com/api/mcp/images/rim_example"
    }]
  }],
  "kb_ids": ["kb-a"],
  "partial": false,
  "errors": [],
  "ranking": "按各知识库内部排名交错合并"
}
```

若 `partial` 为 `true`，`errors[]` 中每项包含失败的 `kb_id`、`kb_name`、`status` 和 `message`。

### 图片展示

检索命中若附带图片，检查该条 `image_info[]` 中的 `caption` 和 `markdown_url`。`markdown_url` 是可访问的图片 URL，并非已经排版好的 Markdown。**如果需要展示检索图片，直接在回复正文中使用 Markdown 图片语法：`![图片标题或概要](图片URL)`。**例如：

```markdown
![凝胶电泳结果图](https://rag.example.com/api/mcp/images/rim_example)
```

优先以 `caption` 作为图片标题或概要，以同一图片的 `markdown_url` 作为图片 URL。仅在 `markdown_url` 存在且用户需要查看图片时嵌入；不要把 `resource://` 等内部引用当作图片 URL，也不要只把图片 URL 作为普通文字输出。图片链接有有效期，过期后重新检索获取新链接。

## 文档列出、读取与下载

- 要浏览某个知识库的全部文档，调用 `rag_list_documents` 并按 `page`、`page_size` 翻页，直到取完 `total`；该列表不局限于通过 RAGPortal 上传的文件。
- 要查看某条文档的上游详情，用 `rag_get_document` 和 `document_id`。不要将 `source` 的非固定字段当作通用契约。
- 要获取原文件，用 `rag_download_file` 的 `download_url`。链接有效期为 10 分钟，过期后重新调用工具。该链接只对应指定文档，无需在下载请求中再次携带长期 API Token；不要在回答中泄露 Token。

## 写入文档

只在用户要求上传或写入文件时调用 `rag_upload_document`。先确定用户授权的目标 `kb_id`；若不知道 ID 且 Token 有 `knowledge-bases:list` 权限，调用 `rag_list_knowledge_bases`，否则请用户提供目标 ID。读取客户端可访问文件的原始字节并做标准 Base64 编码，传入原文件名和编码结果；`content_base64` 不能是文件路径、下载 URL 或带 `data:` 前缀的 Data URL：

```json
{
  "kb_id": "kb-a",
  "filename": "实验记录.pdf",
  "content_base64": "JVBERi0xLjQK..."
}
```

默认允许的扩展名为 `pdf,doc,docx,xls,xlsx,ppt,pptx,md,txt,csv,html`，默认大小上限 100 MB；部署方可修改配置。成功响应中的 `document_id` 可继续用于读取或下载；上传成功仅表示已提交给 WeKnora，不代表解析和索引已经完成。文件重复、类型不支持、超过大小限制或知识库未授权时，应根据返回错误告知用户，不要擅自改写文件后重试。

记录上传结果中的 `document_id`，需要确认处理结果时将它传给 `rag_get_upload_status`；不要传本地记录的 `upload_id`。通过 MCP 客户端调用时只传 `{"document_id": "wk-1"}`；使用原始 JSON-RPC 的客户端可发送：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "rag_get_upload_status",
    "arguments": {"document_id": "wk-1"}
  }
}
```

从 `result.structuredContent` 读取状态，或解析 `result.content[0].text` 中的 JSON。`parse_status` 是 WeKnora 的实时原值：`pending`、`processing`、`finalizing` 表示仍在处理；`completed` 表示处理完成；`failed`、`cancelled`、`deleted` 表示本次处理未完成，应结合 `error_message` 告知用户。`enable_status` 表示文档是否启用；即使 `completed`，若为 `disabled`，也不要声称该文档已经可以检索。状态缺失或为未知值时，不要推断处理完成。根据用户任务适度间隔查询，遇到终态立即停止，不要高频轮询。
