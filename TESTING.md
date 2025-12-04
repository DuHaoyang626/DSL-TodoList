# Manual Testing Guide

本文档描述 API 部分与 Copilot Assistant 部分的独立测试方式、测试桩以及测试驱动。

## 目录
- [API 测试](#api-测试)
  - [单次测试驱动](#单次测试驱动)
  - [批量测试驱动](#批量测试驱动)
  - [测试桩说明](#测试桩说明)
- [Assistant 测试](#assistant-测试)
  - [单次测试驱动](#assistant-单次测试驱动)
  - [批量测试驱动](#assistant-批量测试驱动)
  - [测试桩说明](#assistant-测试桩说明)

## API 测试
所有 API 驱动都直接调用 `dsl_todolist.api.handle_json_request`，因此会访问真实数据库（与现有 `tests.test_api_suite` 一致）。

### 单次测试驱动
- 文件：`tests/manual/api_single_test.py`
- 用法：
  ```powershell
  python tests/manual/api_single_test.py
  ```
- 流程：脚本要求从终端输入一个完整的 JSON 请求（如 `{ "action": "list", "data": {} }`），解析后将原始字符串传给 `handle_json_request`，并把返回 JSON 打印到终端。

### 批量测试驱动
- 文件：`tests/manual/api_batch_test.py`
- 用法：
  ```powershell
  python tests/manual/api_batch_test.py --cases tests/manual/api_cases.txt
  ```
- 测试数据：`tests/manual/api_cases.txt`。每行格式：`<JSON 请求>|||<期望响应中需包含的子串>`。
- 行为：脚本逐行读取用例，调用 `handle_json_request`，若响应中包含期望子串则打印 `CASE <n>: 正确`，否则输出错误信息。

### 测试桩说明
- API 测试不需要额外桩；驱动直接调用真实 API，实现真正的端到端验证。
- 由于数据库是共享的，请在批量测试前确认用例不会破坏生产数据；示例用例仅包含 `list`、非法 action、无效 create 等安全输入。

## Assistant 测试
Assistant 测试驱动现在直接调用真实的 `TodoAssistant`，也就是会向当前配置的 LLM（Ollama/Deepseek 等）发起请求，并根据 `apply_changes` 决定是否调用真实 API。

### Assistant 单次测试驱动
- 文件：`tests/manual/assistant_single_test.py`
- 用法：
  ```powershell
  # 交互输入（脚本会提示 NL> ）
  python tests/manual/assistant_single_test.py

  # 或直接传入指令
  python tests/manual/assistant_single_test.py --text "帮我添加一个叫写日报的待办"
  ```
- 选项：`--no-apply` 可关闭 API 落盘，仅观察 LLM 生成的 JSON。
- 行为：脚本创建 `TodoAssistant` 实例、真实调用 LLM，将 `operation`、`summary` 以及（若启用）API 响应打印到终端。

### Assistant 批量测试驱动
- 文件：`tests/manual/assistant_batch_test.py`
- 用法：
  ```powershell
  python tests/manual/assistant_batch_test.py --cases tests/manual/assistant_cases.txt
  ```
- 测试数据：`tests/manual/assistant_cases.txt`。每行格式：`<自然语言指令>|||<期望 action>|||<期望 summary>`。
- 行为：脚本顺序执行文件中的每一行，对真实 LLM 运行 `run_instruction`。当返回的 `action` 与 `summary` 同期望一致时输出 `CASE <n>: 正确`，否则详细打印差异。使用 `--no-apply` 可避免修改数据库。

### Assistant 测试说明
- 不再存在 `ScenarioAssistant` 或桩响应，所有结果均来自真实 LLM。
- 若需要稳定的断言，请在 `assistant_cases.txt` 中编写具有确定性的期望（包括 summary）。不同模型/温度设置可能导致 summary 文字略有不同，请根据实际情况调整。

## 运行提示
- 所有脚本都可以在项目根目录下执行，示例命令使用 PowerShell。
- Assistant 脚本默认启用 `apply_changes=True`，因此会调用真实 API 并修改数据库；若仅需校验 JSON，请添加 `--no-apply`。
