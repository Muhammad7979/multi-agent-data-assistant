"""Translate graph results without exposing prompts, tool calls, or raw state."""
from langchain_core.messages import AIMessage

from data_agent.api_models import AssistantResponse, ETLOutput
from data_agent.agents.policy import PolicyAnswer
from pydantic import ValidationError


class InvalidAssistantResult(ValueError):
    def __init__(self, route=None):
        super().__init__("The graph did not return a usable answer")
        self.route = route


def assistant_response(result: dict) -> AssistantResponse:
    route = result.get("route_response") if isinstance(result, dict) else None
    if route not in ("sql", "etl", "policy"):
        raise InvalidAssistantResult()
    messages = result.get("messages")
    if not isinstance(messages, list) or not messages or not isinstance(messages[-1], dict):
        raise InvalidAssistantResult(route)
    child = messages[-1]
    if route == 'etl' and child.get('etl_outcomes'):
        files, lines, failures = [], [], 0
        errors = {
            'extraction_failed': 'API extraction failed.',
            'transformation_failed': 'Transformation failed.',
            'storage_failed': 'File writing or metadata publication failed. No saved output is confirmed for this operation.',
            'unsupported_format': 'The requested output format is unsupported.',
        }
        try:
            for outcome in child['etl_outcomes']:
                if outcome['status'] == 'failed':
                    failures += 1
                    lines.append(errors[outcome['error_code']])
                    continue
                if outcome['status'] != 'saved' or outcome['operation'] not in ('extraction', 'transformation'):
                    raise ValueError('Invalid outcome')
                file = ETLOutput.model_validate(outcome['file'])
                files.append(file)
                count = f' ({file.row_count} records)' if file.row_count is not None else ''
                lines.append(f"{outcome['operation'].capitalize()} completed{count}; output saved successfully.\n\n"
                             f"File: `{file.filename}`\n\nFormat: {file.format.upper()}  \n"
                             f"Created: {file.created_at}  \nFile ID: `{file.id}`")
        except (KeyError, TypeError, ValueError):
            raise InvalidAssistantResult(route) from None
        etl_status = 'partial' if failures and files else 'failed' if failures else 'completed'
        if child.get('response_generation_failed'):
            lines.append('The later response-generation step failed. Saved files are preserved; any further requested operations are not confirmed. Do not repeat extraction merely to obtain a summary.')
            if not failures:
                etl_status = 'response_failed'
        return AssistantResponse(answer='\n\n'.join(lines), route=route, status='answered',
                                 files=files, etl_status=etl_status)
    if route == "policy":
        try:
            policy = PolicyAnswer.model_validate(child)
        except ValidationError:
            raise InvalidAssistantResult(route) from None
        if not policy.answer.strip() or (policy.status == 'answered' and not policy.sources):
            raise InvalidAssistantResult(route)
        if policy.status == 'insufficient_evidence' and policy.sources:
            raise InvalidAssistantResult(route)
        return AssistantResponse(answer=policy.answer, route=route, status=policy.status,
                                 sources=policy.sources)
    status = "answered"
    if route == "sql":
        decision = child.get("is_safe")
        if decision not in ("Yes", "No"):
            raise InvalidAssistantResult(route)
        if decision == "No":
            status = "declined"
        elif (not isinstance(child.get("sql_query_execution_result"), str)
              or not child["sql_query_execution_result"].strip()):
            # None or the initial blank field is not evidence of an execution result.
            raise InvalidAssistantResult(route)
        answer = child.get("final_answer")
    else:
        history = child.get("messages")
        if not isinstance(history, list) or not history:
            raise InvalidAssistantResult(route)
        terminal = history[-1]
        if not isinstance(terminal, AIMessage) or terminal.tool_calls or terminal.invalid_tool_calls:
            raise InvalidAssistantResult(route)
        answer = terminal.content
        if isinstance(answer, list):
            # Provider content blocks may include non-user-facing reasoning/tool content.
            answer = "\n".join(
                block if isinstance(block, str) else block["text"]
                for block in answer
                if isinstance(block, str) or (
                    isinstance(block, dict) and block.get("type") == "text"
                    and isinstance(block.get("text"), str)
                )
            )
    if not isinstance(answer, str) or not answer.strip():
        raise InvalidAssistantResult(route)
    return AssistantResponse(answer=answer, route=route, status=status)
