from app.schemas.models import AgentTrace


class BaseAgent:
    name = "BaseAgent"

    def trace(self, input_summary: str, output_summary: str) -> AgentTrace:
        return AgentTrace(
            agent_name=self.name,
            input_summary=input_summary,
            output_summary=output_summary,
        )
