# Tích hợp Denario vào Deep Agents

Tài liệu này mô tả cách Denario đã được tích hợp vào hệ thống Deep Agents như một sub-agent.

## Tổng quan

Denario đã được tích hợp như một `CompiledSubAgent` trong hệ thống Deep Agents. Điều này cho phép orchestrator agent gọi Denario workflow thông qua tool `task()` như các sub-agent khác.

## Cấu trúc tích hợp

### 1. Denario Adapter (`backend/agents/denario_adapter.py`)

Adapter này chuyển đổi format gọi sub-agent (HumanMessage với task description) sang format Denario workflow state, chạy workflow, và trả về kết quả.

**Cách hoạt động:**
- Nhận input từ sub-agent system (messages với HumanMessage chứa task description)
- Chuyển đổi sang `DenarioWorkflowState` format
- Chạy Denario workflow (idea → method → results → paper)
- Trả về kết quả dưới dạng messages

### 2. Sub-Agent Definition (`backend/agents/sub_agents.py`)

Denario được định nghĩa như một `CompiledSubAgent`:

```python
denario_agent = {
    "name": "denario-research-agent",
    "description": "Complete end-to-end research workflow using Denario...",
    "runnable": DenarioSubAgentAdapter(),
}
```

### 3. Orchestrator Instructions

Orchestrator đã được cập nhật để biết về Denario agent và khi nào nên sử dụng nó.

## Cách sử dụng

### Từ Orchestrator Agent

Orchestrator có thể gọi Denario agent như sau:

```python
# Orchestrator sẽ tự động quyết định khi nào cần dùng Denario
# Ví dụ khi user yêu cầu một research project hoàn chỉnh

task(
    description="Conduct a complete research project on [topic]. Available data: [description]. Tools: [list]. Generate idea, methodology, run experiments, and write a paper.",
    subagent_type="denario-research-agent"
)
```

### Trực tiếp từ code

```python
from backend.agents.denario_adapter import DenarioSubAgentAdapter

# Tạo adapter
adapter = DenarioSubAgentAdapter()

# Gọi với input format của sub-agent
result = adapter.invoke({
    "messages": [
        HumanMessage(content="Research project description with data and tools...")
    ]
})

# Kết quả chứa messages từ Denario workflow
print(result["messages"])
```

## Workflow của Denario

Khi được gọi, Denario sẽ thực hiện các bước sau:

1. **Initialize**: Khởi tạo project directory và KeyManager
2. **Generate Idea**: Tạo research idea từ data description
3. **Generate Method**: Tạo methodology dựa trên idea
4. **Generate Results**: Chạy experiments và tạo results
5. **Generate Paper**: Viết LaTeX paper từ tất cả outputs

Tất cả outputs được lưu trong project directory (mặc định: `denario_project/`).

## Lưu ý

1. **Data Description**: Denario cần một data description chi tiết bao gồm:
   - Mô tả dữ liệu có sẵn
   - Tools/công cụ có thể sử dụng
   - Mục tiêu nghiên cứu

2. **Autonomous Workflow**: Denario workflow là autonomous - nó sẽ chạy toàn bộ pipeline mà không cần human approval (khác với planning-agent).

3. **Project Directory**: Mỗi lần gọi Denario sẽ tạo một project directory riêng. Có thể chỉ định project_dir trong state nếu cần.

4. **Error Handling**: Adapter xử lý errors và trả về error messages dưới dạng AIMessage.

## So sánh với các sub-agent khác

| Feature | Denario Agent | Other Sub-Agents |
|---------|---------------|------------------|
| Scope | End-to-end research | Specific tasks |
| Output | Complete paper | Intermediate files |
| Workflow | Fixed 4-step | Flexible |
| Use Case | Full research project | Phase-specific tasks |

## Ví dụ use cases

### Use Case 1: User yêu cầu research project hoàn chỉnh
```
User: "I want to research [topic] using [data]. Generate a complete paper."
Orchestrator: → Calls denario-research-agent
```

### Use Case 2: User có data description chi tiết
```
User: "Here's my data description: [detailed description]. Run the full Denario pipeline."
Orchestrator: → Calls denario-research-agent
```

### Use Case 3: Kết hợp với workflow hiện tại
Orchestrator có thể:
- Dùng Denario cho một research project riêng
- Dùng các sub-agent khác cho các phases cụ thể của workflow chính

## Testing

Để test tích hợp:

```python
from backend.main import create_agent

# Tạo agent với Denario integrated
agent = create_agent()

# Test với một research request
result = agent.invoke({
    "messages": [
        HumanMessage(content="Research [topic] with [data description]")
    ]
})
```

## Troubleshooting

1. **Import errors**: Đảm bảo `denario` package có thể import được từ `backend/`
2. **KeyManager errors**: Đảm bảo API keys được set trong environment variables
3. **State errors**: Adapter tự động xử lý state conversion, nhưng nếu có lỗi, check DenarioWorkflowState format

