"""AWEL: Simple chat dag example

    DB-GPT will automatically load and execute the current file after startup.

    Example:

    .. code-block:: shell

        DBGPT_SERVER="http://127.0.0.1:5555"
        MODEL="gpt-3.5-turbo"
        curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_chat \
        -H "Content-Type: application/json" -d '{
            "model": "'"$MODEL"'",
            "user_input": "hello"
        }'
"""

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core import ModelMessage, ModelRequest
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator
from dbgpt.model.operators import LLMOperator
import os


class TriggerReqBody(BaseModel):
    model: str = Field(..., description="Model name")
    user_input: str = Field(..., description="User input")


class RequestHandleOperator(MapOperator[TriggerReqBody, ModelRequest]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> ModelRequest:
        messages = [ModelMessage.build_human_message(input_value.user_input)]
        print(f"Receive input value: {input_value}")
        return ModelRequest.build_request(input_value.model, messages)


with DAG("dbgpt_awel_simple_dag_example", tags={"label": "example"}) as dag:
    # Receive http request and trigger dag to run.
    trigger = HttpTrigger(
        "/examples/simple_chat", methods="POST", request_body=TriggerReqBody
    )

    from dbgpt.model.proxy import ZhipuLLMClient
    llm_client = ZhipuLLMClient(
        model_alias="GLM-4-Plus",
        api_base=os.getenv("OPENAI_API_BASE", "https://open.bigmodel.cn/api/paas/v4/"),
        api_key=os.getenv("OPENAI_API_KEY", "f90aefe316464dee080c545e6cca1c79.Vgr7uQds7Qobna0e"),
    )

    # from dbgpt.model.proxy import DeepseekLLMClient
    # model_name = "deepseek-chat"
    # llm_client = DeepseekLLMClient(
    #     model_alias=model_name,
    #     api_base=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
    #     api_key=os.getenv("OPENAI_API_KEY", "sk-453833a108dd4572b7efb8a120f09e7d"),
    # )



    request_handle_task = RequestHandleOperator()
    llm_task = LLMOperator(task_name="llm_task", llm_client=llm_client)
    # llm_task = LLMOperator(task_name="llm_task")
    model_parse_task = MapOperator(lambda out: out.to_dict())
    trigger >> request_handle_task >> llm_task >> model_parse_task


if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag], port=5555)
    else:
        # Production mode, DB-GPT will automatically load and execute the current file after startup.
        pass
