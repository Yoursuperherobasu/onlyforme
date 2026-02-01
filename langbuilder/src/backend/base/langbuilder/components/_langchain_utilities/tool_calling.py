from langchain.agents import create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

from langbuilder.base.agents.agent import LCToolsAgentComponent
from langbuilder.inputs.inputs import (
    DataInput,
    HandleInput,
    MessageTextInput,
)
from langbuilder.schema.data import Data


def message_formatter(intermediate_steps):
    """Format intermediate steps for the agent scratchpad."""
    from langchain_core.messages import AIMessage, ToolMessage
    messages = []
    for action, observation in intermediate_steps:
        if hasattr(action, 'tool_calls') and action.tool_calls:
            messages.append(AIMessage(content="", tool_calls=action.tool_calls))
            for tool_call in action.tool_calls:
                messages.append(ToolMessage(content=str(observation), tool_call_id=tool_call["id"]))
        elif hasattr(action, 'tool'):
            messages.append(AIMessage(content=f"Calling tool: {action.tool}"))
            messages.append(ToolMessage(content=str(observation), tool_call_id=action.tool))
    return messages


class ToolCallingAgentComponent(LCToolsAgentComponent):
    display_name: str = "Tool Calling Agent"
    description: str = "An agent designed to utilize various tools seamlessly within workflows."
    icon = "LangChain"
    name = "ToolCallingAgent"

    inputs = [
        *LCToolsAgentComponent._base_inputs,
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
            info="Language model that the agent utilizes to perform tasks effectively.",
        ),
        MessageTextInput(
            name="system_prompt",
            display_name="System Prompt",
            info="System prompt to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
        ),
        DataInput(
            name="chat_history",
            display_name="Chat Memory",
            is_list=True,
            advanced=True,
            info="This input stores the chat history, allowing the agent to remember previous conversations.",
        ),
    ]

    def get_chat_history_data(self) -> list[Data] | None:
        return self.chat_history

    def create_agent_runnable(self):
        # Check if we have actual tools to use
        has_tools = self.tools and len(self.tools) > 0
        
        if has_tools:
            # Use tool-calling agent when tools are available
            messages = [
                ("system", "{system_prompt}"),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
            prompt = ChatPromptTemplate.from_messages(messages)
            self.validate_tool_names()
            try:
                return create_tool_calling_agent(self.llm, self.tools, prompt)
            except NotImplementedError as e:
                message = f"{self.display_name} does not support tool calling. Please try using a compatible model."
                raise NotImplementedError(message) from e
        else:
            # No tools - create a simple chain that doesn't bind tools to the LLM
            # This prevents the "Tool choice is none, but model called a tool" error
            from langchain.agents.output_parsers.tools import ToolsAgentOutputParser
            from langchain_core.agents import AgentFinish
            from langchain_core.runnables import RunnableLambda
            
            messages = [
                ("system", "{system_prompt}"),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
            ]
            prompt = ChatPromptTemplate.from_messages(messages)
            
            # Create a simple chain that returns an AgentFinish directly
            def wrap_as_agent_finish(response):
                """Wrap LLM response as AgentFinish for compatibility with AgentExecutor."""
                if hasattr(response, 'content'):
                    content = response.content
                else:
                    content = str(response)
                return AgentFinish(
                    return_values={"output": content},
                    log=content,
                )
            
            # Simple chain: prompt | llm | wrap as AgentFinish
            # Pass through agent_scratchpad but don't use it (for compatibility)
            chain = (
                RunnablePassthrough.assign(agent_scratchpad=lambda x: [])
                | prompt 
                | self.llm 
                | RunnableLambda(wrap_as_agent_finish)
            )
            return chain
