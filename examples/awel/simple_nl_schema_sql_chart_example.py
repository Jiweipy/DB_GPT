import os
import re
from typing import Any, Dict, Optional

from pandas import DataFrame
import sqlparse

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.configs.model_config import MODEL_PATH, PILOT_PATH
from dbgpt.core import LLMClient, ModelMessage, ModelMessageRoleType, ModelRequest
from dbgpt.core.awel import DAG, HttpTrigger, JoinOperator, MapOperator
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnector
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.rag.embedding import DefaultEmbeddingFactory
from dbgpt.rag.operators.schema_linking import SchemaLinkingOperator
from dbgpt.storage.vector_store.chroma_store import ChromaStore, ChromaVectorConfig
from dbgpt.util.chat_util import run_async_tasks

"""AWEL: Simple nl-schemalinking-sql-chart operator example

    pre-requirements:
        1. install openai python sdk
        ```
            pip install "db-gpt[openai]"
        ```
        2. set openai key and base
        ```
            export OPENAI_API_KEY={your_openai_key}
            export OPENAI_API_BASE={your_openai_base}
        ```
        or
        ```
            import os
            os.environ["OPENAI_API_KEY"] = {your_openai_key}
            os.environ["OPENAI_API_BASE"] = {your_openai_base}
        ```
        python examples/awel/simple_nl_schema_sql_chart_example.py
    Examples:
        ..code-block:: shell
        curl --location 'http://127.0.0.1:5555/api/v1/awel/trigger/examples/rag/schema_linking' \
--header 'Content-Type: application/json' \
--data '{"query": "How old is the user Tom and what does he name?"}'
"""

INSTRUCTION = (
    "I want you to act as a SQL terminal in front of an example database, you need only to return the sql "
    "command to me.Below is an instruction that describes a task, Write a response that appropriately "
    "completes the request.\n###Instruction:\n{}"
)
INPUT_PROMPT = "\n###Input:\n{}\n###Response:"


def _create_vector_connector():
    """Create vector connector."""
    config = ChromaVectorConfig(
        persist_path=PILOT_PATH,
        name="embedding_rag_test",
        embedding_fn=DefaultEmbeddingFactory(
            default_model_name=os.path.join(MODEL_PATH, "text2vec-large-chinese"),
        ).create(),
    )

    return ChromaStore(config)


def _create_temporary_connection():
    """Create a temporary database connection for testing."""
    connect = SQLiteTempConnector.create_temporary_db()
    connect.create_temp_tables(
        {
            "user": {
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "age": "INTEGER",
                },
                "data": [
                    (1, "Tom", 8),
                    (2, "Jerry", 16),
                    (3, "Jack", 18),
                    (4, "Alice", 20),
                    (5, "Bob", 22),
                ],
            }
        }
    )
    connect.create_temp_tables(
        {
            "job": {
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "age": "INTEGER",
                },
                "data": [
                    (1, "student", 8),
                    (2, "student", 16),
                    (3, "student", 18),
                    (4, "teacher", 20),
                    (5, "teacher", 22),
                ],
            }
        }
    )
    connect.create_temp_tables(
        {
            "student": {
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "age": "INTEGER",
                    "info": "TEXT",
                },
                "data": [
                    (1, "Andy", 8, "good"),
                    (2, "Jerry", 16, "bad"),
                    (3, "Wendy", 18, "good"),
                    (4, "Spider", 20, "bad"),
                    (5, "David", 22, "bad"),
                ],
            }
        }
    )
    return connect


def _prompt_join_fn(query: str, chunks: str) -> str:
    prompt = INSTRUCTION.format(chunks + INPUT_PROMPT.format(query))
    return prompt


class TriggerReqBody(BaseModel):
    query: str = Field(..., description="User query")


class RequestHandleOperator(MapOperator[TriggerReqBody, Dict]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> Dict:
        params = {
            "query": input_value.query,
        }
        print(f"Receive input value: {input_value.query}")
        return params


class SqlGenOperator(MapOperator[Any, Any]):
    """The Sql Generation Operator."""

    def __init__(self, llm: Optional[LLMClient], model_name: str, **kwargs):
        """Init the sql generation operator
        Args:
           llm (Optional[LLMClient]): base llm
        """
        super().__init__(**kwargs)
        self._llm = llm
        self._model_name = model_name

    async def map(self, prompt_with_query_and_schema: str) -> str:
        """generate sql by llm.
        Args:
            prompt_with_query_and_schema (str): prompt
        Return:
            str: sql
        """

        messages = [
            ModelMessage(
                role=ModelMessageRoleType.SYSTEM, content=prompt_with_query_and_schema
            )
        ]
        request = ModelRequest(model=self._model_name, messages=messages)
        tasks = [self._llm.generate(request)]
        output = await run_async_tasks(tasks=tasks, concurrency_limit=1)
        sql = output[0].text
        return sql


class SqlExecOperator(MapOperator[Any, Any]):
    """The Sql Execution Operator."""

    def __init__(self, connector: Optional[RDBMSConnector] = None, **kwargs):
        """
        Args:
            connection (Optional[RDBMSConnector]): RDBMSConnector connection
        """
        super().__init__(**kwargs)
        self._connector = connector

    def map(self, sql: str) -> DataFrame:
        """retrieve table schemas.
        Args:
            sql (str): query.
        Return:
            str: sql execution
        """
        parsed_sql = self.sql_extract(sql)
        dataframe = self._connector.run_to_df(command=parsed_sql, fetch="all")
        print(f"sql data is \n{dataframe}")
        return dataframe
    
    def sql_extract(self, llm_sql: str) -> str:
        """Extract SQL from content.
        Args:
            content (str): content.
        Return:
            str: sql
        """
        pattern = re.compile(
            r"```\s*?(sql)?\n?SELECT([\s\S]*?)```", re.RegexFlag.IGNORECASE
        )
        result = re.search(pattern, llm_sql)
        sql = result.group(0) if result else llm_sql
        sql = sql.strip("```").strip().strip("sql").strip("\n").strip().strip(";")
        try:
            sql = sqlparse.format(sql, reindent=True, keyname_case="upper")
            print(f"sql: {sql}")
        except Exception as e:
            print(f"Failed to format sql: {e}")
        return sql



class ChartDrawOperator(MapOperator[Any, Any]):
    """The Chart Draw Operator."""

    def __init__(self, **kwargs):
        """
        Args:
        connection (RDBMSConnector): The connection.
        """
        super().__init__(**kwargs)

    def map(self, df: DataFrame) -> str:
        """get sql result in db and draw.
        Args:
            sql (str): str.
        """
        import matplotlib.pyplot as plt

        category_column = df.columns[0]
        count_column = df.columns[1]
        plt.figure(figsize=(8, 4))
        plt.bar(df[category_column], df[count_column])
        plt.xlabel(category_column)
        plt.ylabel(count_column)
        plt.show()
        return str(df)
    

class PrintResultOperator(MapOperator[Any, Any]):
    """The Print Result Operator."""

    def __init__(self, **kwargs):
        """
        Args:
        connection (RDBMSConnector): The connection.
        """
        super().__init__(**kwargs)

    def map(self, df: DataFrame) -> str:
        """get sql result in db and draw.
        Args:
            sql (str): str.
        """
        print(df)
        return str(df)


with DAG("simple_nl_schema_sql_chart_example") as dag:
    trigger = HttpTrigger(
        "/examples/rag/schema_linking", methods="POST", request_body=TriggerReqBody
    )
    request_handle_task = RequestHandleOperator()
    query_operator = MapOperator(lambda request: request["query"])

    # llm = OpenAILLMClient()
    # model_name = "gpt-3.5-turbo"

    # TODO:debug ValueError: Current model not support system role
    # from dbgpt.model.proxy import ZhipuLLMClient
    # model_name = "GLM-4-Plus"
    # llm = ZhipuLLMClient(
    #     model_alias="GLM-4-Plus",
    #     api_base=os.getenv("OPENAI_API_BASE", "https://open.bigmodel.cn/api/paas/v4/"),
    #     api_key=os.getenv("OPENAI_API_KEY", "f90aefe316464dee080c545e6cca1c79.Vgr7uQds7Qobna0e"),
    # )

    from dbgpt.model.proxy import DeepseekLLMClient
    model_name = "deepseek-chat"
    llm = DeepseekLLMClient(
        model_alias=model_name,
        api_base=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
        api_key=os.getenv("OPENAI_API_KEY", "sk-453833a108dd4572b7efb8a120f09e7d"),
    )

    retriever_task = SchemaLinkingOperator(
        connector=_create_temporary_connection(), llm=llm, model_name=model_name
    )
    prompt_join_operator = JoinOperator(combine_function=_prompt_join_fn)
    sql_gen_operator = SqlGenOperator(llm=llm, model_name=model_name)
    sql_exec_operator = SqlExecOperator(connector=_create_temporary_connection())
    # draw_chart_operator = ChartDrawOperator(connector=_create_temporary_connection())
    print_result_operator = PrintResultOperator()

    trigger >> request_handle_task >> query_operator >> prompt_join_operator
    (
        trigger
        >> request_handle_task
        >> query_operator
        >> retriever_task
        >> prompt_join_operator
    )
    prompt_join_operator >> sql_gen_operator >> sql_exec_operator >> print_result_operator
    # prompt_join_operator >> sql_gen_operator >> sql_exec_operator >> draw_chart_operator

if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment

        setup_dev_environment([dag], port=5555)
    else:
        pass