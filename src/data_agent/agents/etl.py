"""ETL graph construction; clients are created only when explicitly built."""
import json
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END

from data_agent.agents.etl_tools import build_tools
from data_agent.agents.state import ETLAgentSchema
from data_agent.llm import create_llm
from data_agent.services.etl_results import failed_result


def build_etl_graph(*, data_root, llm_factory=create_llm):
    tools = build_tools(data_root=data_root, llm_factory=llm_factory)
    llm_bind = llm_factory("claude").bind_tools(tools)

    def llm_node(state:ETLAgentSchema):

        messages = state.messages

        prompt = f"""
            You are a Python Data Analyst who has access to tools that can extract and load, 
            transform and load data. You will be provided with a user's question 
            and you would need to perform the right ETL operations as per the user's question. 
            If the operation is performed then inform the user and end the coversation.
            Here's the chat history: {messages}\n
    """

        try:
            final_answer = llm_bind.invoke(prompt)
            if not isinstance(final_answer, AIMessage) or final_answer.invalid_tool_calls:
                raise ValueError('Invalid model response')
            if any(call['name'] not in {tool.name for tool in tools} for call in final_answer.tool_calls):
                raise ValueError('Unknown ETL tool')
        except Exception:
            if not state.etl_outcomes:
                raise
            # Tool outcomes survive a later model failure. Never rerun extraction.
            state.response_generation_failed = True
            final_answer = AIMessage(content='The recorded ETL outcomes are available.')

        state.messages = messages + [final_answer]

        return state


    def tool_node(state:ETLAgentSchema):
        """
    This node is responsible for invoking the appropriate tool based on the user's question and the context provided by the LLM.
    """

        tools_results = []

        tools_by_name = {tool.name: tool for tool in tools}

        tool_calls = state.messages[-1].tool_calls

        for tool_call in tool_calls:

            tool = tools_by_name[tool_call['name']]
            args = tool_call['args']
            key = (json.dumps([args.get('url'), args.get('format')])
                   if tool_call['name'] == 'extract_load_tool'
                   else json.dumps([tool_call['name'], args], sort_keys=True))
            if key in state.extraction_results:
                cached = state.extraction_results[key]
                observation = ToolMessage(content=cached['content'], artifact=cached['artifact'], tool_call_id=tool_call['id'])
            else:
                try:
                    observation = tool.invoke({**tool_call, 'type': 'tool_call'})
                except Exception:
                    operation = 'extraction' if tool.name == 'extract_load_tool' else 'transformation'
                    observation = ToolMessage(content=f'{operation.capitalize()} could not be completed.',
                        artifact=failed_result(operation, operation + '_failed'), tool_call_id=tool_call['id'])
                state.extraction_results[key] = {'content': observation.content, 'artifact': observation.artifact}
                state.etl_outcomes.append(observation.artifact)

            tools_results.append(observation)

        state.messages = state.messages + tools_results

        return state   


    # Nodes & Edges
    etl_analyst_graph = StateGraph(ETLAgentSchema)
    etl_analyst_graph.add_node("llm_node", llm_node)
    etl_analyst_graph.add_node("tool_node", tool_node)

    etl_analyst_graph.add_edge(START, "llm_node")

    def is_tool_call(state:ETLAgentSchema):
        tool_calls = state.messages[-1].tool_calls

        if tool_calls:
            return "tool_node"
        else:
            return "end"

    etl_analyst_graph.add_conditional_edges(
        "llm_node",is_tool_call,
        {
            "tool_node": "tool_node",
            "end": END
        }
    )

    etl_analyst_graph.add_edge("tool_node", "llm_node")

    return etl_analyst_graph.compile()
