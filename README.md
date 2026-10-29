# Scientific Keyword Expansion

面向学术文献检索的 Agent Skill。宿主 Agent 负责理解研究问题、生成并审阅候选术语；本项目的 Python 程序负责校验、去重、检索式生成、可选的文献元数据验证和报告导出。仅输入主题不会自动生成关键词，需先按 [`references/candidate-contract.md`](references/candidate-contract.md) 准备候选 JSON。

## 安装

需要 Python 3.11 或更新版本。克隆本仓库后，在仓库根目录运行：

```powershell
python -m pip install -e .
```

仓库还保留一份最终安装包，可直接运行 `python -m pip install dist/scientific_keyword_expansion-1.0.0-py3-none-any.whl`。若不想安装，可在仓库根目录设置 `$env:PYTHONPATH='src'`，然后使用 `python -m scientific_keyword_expansion.cli` 替代下文的 `scientific-keywords`。把本仓库作为 Agent Skill 使用时，入口是 [`SKILL.md`](SKILL.md)；`references/` 是其必要的分析与验证规则。

## 使用

按 [`SKILL.md`](SKILL.md) 和[候选输入契约](references/candidate-contract.md)准备 `input.json`。Quick Mode 不联网；Research Mode 检索 OpenAlex、Semantic Scholar、Crossref 和 arXiv 的文献元数据。默认导出 `report.md`，需要 JSON 和 CSV 时指定全部格式：

```powershell
scientific-keywords --input input.json --out output --formats markdown json csv
scientific-keywords --input input.json --out output --formats markdown json csv --providers openalex crossref
```

第二条命令要求输入 JSON 的 `mode` 为 `research`。`--providers` 可限制调用的数据源。报告的 JSON 结构见 [`schemas/keyword-report.schema.json`](schemas/keyword-report.schema.json)。旧输入和旧报告字段继续兼容；`term_found` 仅表示采样标题或摘要有术语词面命中，不代表目标研究语境已经人工核实。

## API 连通性诊断

在 Research Mode 使用的同一个终端环境中运行：

```powershell
scientific-keywords doctor --timeout 10 --retries 0
```

`doctor` 每次都发起新的 DNS 和 HTTPS 请求，从 OpenAlex、Crossref 各获取一条真实文献元数据；两个 HTTPS 请求都成功时退出码为 0。诊断 JSON 分别显示 DNS、HTTPS、进程代理环境、`urllib` 检测到的代理和 Windows Internet Settings。若 Codex 沙箱内 DNS 失败，请在本机终端运行同一命令比较；只在沙箱失败属于当前执行环境的网络限制，不应判定为 Provider 程序故障。

HTTP 客户端默认使用 Python `urllib` 的 `HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY` 和适用的系统代理设置。也可单独给本程序配置 HTTP 代理；把示例中的端口替换为代理软件实际监听的 HTTP 或 mixed 端口：

```powershell
scientific-keywords doctor --proxy-url 'http://127.0.0.1:<实际HTTP端口>'
scientific-keywords --input input.json --out output --providers openalex crossref --proxy-url 'http://127.0.0.1:<实际HTTP端口>'
```

相同配置也可通过 `SKE_PROXY_URL`、`SKE_HTTP_TIMEOUT`、`SKE_HTTP_RETRIES` 环境变量设置，CLI 参数优先。HTTPS API 通过普通 HTTP 代理访问时，代理 URL 通常以 `http://` 开头，客户端使用 HTTP CONNECT 建立加密通道。此标准库实现不支持 `socks5://` 代理。SSL 证书验证始终开启。`doctor` 区分 DNS、代理连接、超时、证书、HTTP 状态和响应解析错误。

## 项目文件

- `SKILL.md` 与 `references/`：Agent 的工作说明和规则。
- `src/scientific_keyword_expansion/`：可安装的 Python 程序。
- `schemas/`：报告 Schema。
- `pyproject.toml`：Python 安装配置。

许可证见 [`LICENSE`](LICENSE)。
