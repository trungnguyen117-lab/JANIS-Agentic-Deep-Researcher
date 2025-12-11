from backend.main import create_agent
from langchain_core.messages import HumanMessage
# Tạo agent với Denario integrated
agent = create_agent()

# Test với một research request
result = agent.invoke({
    "messages": [
        HumanMessage(content="Write a short paper on Intrusion Detection with Machine Learning. Generate several plots. Generate some data, which should not take more than 3 minutes to generate."
)
    ]
})