import json
import logging
import re
import traceback
from typing import Dict

from dbgpt._private.config import Config
from dbgpt.agent.util.api_call import ApiCall
from dbgpt.app.scene import BaseChat, ChatScene
from dbgpt.app.scene.chat_db.auto_execute.critic_prompt import (
    _DEFAULT_TEMPLATE_FOR_CRITIC_ZH,
    API_KEY_ZHIPU,
)
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import root_tracer, trace

logger = logging.getLogger(__name__)
CFG = Config()

from openai import OpenAI

client = OpenAI(api_key=API_KEY_ZHIPU, base_url="https://open.bigmodel.cn/api/paas/v4/")


class ChatWithDbAutoExecute(BaseChat):
    chat_scene: str = ChatScene.ChatWithDbExecute.value()

    keep_start_rounds = 0  # 从对话开始到keep_start_rounds轮对话保留
    keep_end_rounds = 5  # 最近的keep_end_rounds轮对话保留

    """Number of results to return from the query"""

    def __init__(self, chat_param: Dict):
        """Chat Data Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) dbname
        """
        chat_mode = ChatScene.ChatWithDbExecute
        self.db_name = chat_param["select_param"]
        chat_param["chat_mode"] = chat_mode
        """ """
        super().__init__(
            chat_param=chat_param,
        )
        if not self.db_name:
            raise ValueError(
                f"{ChatScene.ChatWithDbExecute.value} mode should chose db!"
            )
        with root_tracer.start_span(
            "ChatWithDbAutoExecute.get_connect", metadata={"db_name": self.db_name}
        ):
            self.database = CFG.local_db_manager.get_connector(self.db_name)

        self.top_k: int = 50
        self.api_call = ApiCall()

    @trace()
    async def generate_input_values(self) -> Dict:
        """
        generate input values
        """
        try:
            from dbgpt.rag.summary.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")
        client = DBSummaryClient(system_app=CFG.SYSTEM_APP)
        table_infos = None
        try:
            with root_tracer.start_span("ChatWithDbAutoExecute.get_db_summary"):
                table_infos = await blocking_func_to_async(
                    self._executor,
                    client.get_db_summary,
                    self.db_name,
                    self.current_user_input,
                    CFG.KNOWLEDGE_SEARCH_TOP_SIZE,
                )
        except Exception as e:
            print("db summary find error!" + str(e))
        if not table_infos:
            table_infos = await blocking_func_to_async(
                self._executor, self.database.table_simple_info
            )

        input_values = {
            "db_name": self.db_name,
            "user_input": self.current_user_input,
            "top_k": str(self.top_k),
            "dialect": self.database.dialect,
            "table_info": table_infos,
            "display_type": self._generate_numbered_list(),
        }
        return input_values

    def stream_plugin_call(self, text):
        text = text.replace("\n", " ")
        # print(f"stream_plugin_call:{text}")
        return self.api_call.display_sql_llmvis(text, self.database.run_to_df)

    def do_action(self, prompt_response):
        print(f"do_action:{prompt_response}")
        return self.database.run_to_df

    def get_data_by_re(self, raw_string: str) -> dict:
        # 初始化json数据，key为thoughts, sql, display_type
        data_json = {
            "thoughts": "no thoughts",
            "sql": "no sql",
            "display_type": "no display_type",
        }
        # 使用正则表达式匹配并提取 fields
        thoughts_match = re.search(r'"thoughts":\s*"([^"]+)"', raw_string)
        # 提取并打印结果
        data_json["thoughts"] = (
            thoughts_match.group(1) if thoughts_match else "no thoughts"
        )

        sql_match = re.search(r'"sql":\s*"([^"]+)"', raw_string)
        data_json["sql"] = sql_match.group(1) if sql_match else "no sql"

        display_type_match = re.search(r'"display_type":\s*"([^"]+)"', raw_string)
        data_json["display_type"] = (
            display_type_match.group(1) if display_type_match else "no display_type"
        )
        return data_json

    def parse_data_model_msg(self, data_model_msg):
        """
        解析数据模型的回复, 提取thoughts, sql, data, type
        """
        # 提取thoughts
        thoughts_content = data_model_msg.split("\n")[0]

        # 提取 sql
        sql_match = re.search(r"&quot;sql&quot;: &quot;(.*?)&quot;", data_model_msg)
        sql_data = sql_match.group(1) if sql_match else None

        # 提取 data
        data_match = re.search(r"&quot;data&quot;: (\[.*?\])", data_model_msg)
        data_data = data_match.group(1) if data_match else None

        # 提取 type
        type_match = re.search(r"&quot;type&quot;: &quot;(.*?)&quot;", data_model_msg)
        type_data = type_match.group(1) if type_match else None

        # 存储到字典中
        parse_datas = {
            "thoughts": thoughts_content,
            "sql": sql_data,
            "db_data": data_data,
            "display_type": type_data,
        }
        return parse_datas

    def get_openai_client(self, model_input, role_system):
        # QA
        completion = client.chat.completions.create(
            model="glm-4",
            messages=[
                {"role": "system", "content": role_system},
                {"role": "user", "content": model_input},
            ],
            top_p=0.7,
            temperature=0.9,
        )
        return completion.choices[0].message.content

    async def aget_openai_client(self, model_input, role_system):
        completion = client.chat.completions.create(
            model="glm-4",
            messages=[
                {"role": "system", "content": role_system},
                {"role": "user", "content": model_input},
            ],
            top_p=0.7,
            temperature=0.9,
        )
        return completion.choices[0].message.content

    async def aget_openai_client_stream(self, model_input, role_system):
        completion = client.chat.completions.create(
            model="glm-4",
            messages=[
                {"role": "system", "content": role_system},
                {"role": "user", "content": model_input},
            ],
            top_p=0.7,
            temperature=0.9,
            stream=True,
        )
        for chunk in completion:
            try:
                yield chunk.choices[0].delta.content
            except:
                pass


    async def _no_streaming_sql_chart(self, payload, model_output):
        # with root_tracer.start_span("BaseChat.invoke_worker_manager.generate"):
        #     model_output = await self.call_llm_operator(payload)  # 终端流式输出结果

        ai_response_text = self.prompt_template.output_parser.parse_model_nostream_resp(
            model_output, self.prompt_template.sep
        )
        prompt_define_response = (
            self.prompt_template.output_parser.parse_prompt_response(ai_response_text)
        )
        metadata = {
            "model_output": model_output.to_dict(),
            "ai_response_text": ai_response_text,
            "prompt_define_response": self._parse_prompt_define_response(
                prompt_define_response
            ),
        }
        with root_tracer.start_span("BaseChat.do_action", metadata=metadata):
            result = await blocking_func_to_async(
                self._executor, self.do_action, prompt_define_response
            )

        speak_to_user = self.get_llm_speak(prompt_define_response)
        print(f"speak_to_user: {speak_to_user}")

        view_message = await blocking_func_to_async(
            self._executor,
            self.prompt_template.output_parser.parse_view_response,  # 执行sql语句获取数据
            speak_to_user,  # 文字回复内容
            result,
            prompt_define_response,
        )
        return ai_response_text, view_message.replace("\n", "\\n")

    # def get_value_from_output(self, model_input:str, role_system:str, key:str, key_index:int):
    #     """
    #     在流式输出中，从模型输出的内容（JSON格式）中，实时提取key对应的值
    #     key: str, 需要提取的key
    #     key_index: int, key在模型输出中的第几个key索引位置
    #     output: str, 模型输出的内容（JSON格式的字符串）

    #     return: str, key对应的值
    #     """
    #     current_chunks = "" # 当前已经接收到的模型输出内容
    #     flag_key = 1 # 标记是key对应的值是否已经完全提取到
    #     async for chunk in self.aget_openai_client_stream(model_input, role_system):
    #         current_chunks = current_chunks + chunk
    #         if key in current_chunks and flag_key:
    #             if current_chunks.count("\n") == key_index:
    #             # 输出suggestions_of_query之后的字符
    #                 print(current_chunks[current_chunks.find(key) + len(key):])
    #             elif current_chunks.count("\n") == key_index + 1:
    #                 print(current_chunks[current_chunks.find(key) + len(key):current_chunks.find("\",", current_chunks.find(key) + len(key))])
    #                 flag_key = 0

    async def stream_call(self):
        """
        bug:
            2. 异常处理
            3.
        理想情况：
            1. 流式输出数据模型的["thoughts"]，等待["sql"]和["display_type"]的输出，
            2. 组合成为view_message的格式，然后调用评判家模型，流式输出评判家模型的结果
            3. 返回view_message + 评判家模型的结果
        """

        # 获取数据模型输出，并流式返回
        db_model_output = None
        view_msg_current = ""
        flag_thoughts, flag_sql, flag_display_type = 0, 0, 0
        # async for db_model_output in super().stream_call():
        #     msg = self.get_data_by_re(db_model_output)
        #     if msg["thoughts"] != "no thoughts" and flag_thoughts == 0:
        #         view_msg_current = view_msg_current + msg["thoughts"]
        #         flag_thoughts = 1
        #         yield f"data:{view_msg_current}\n\n"
        #     if msg["sql"] != "no sql" and flag_sql == 0:
        #         view_msg_current = view_msg_current + msg["sql"]
        #         flag_sql = 1
        #         yield f"data:{view_msg_current}\n\n"
        #     if msg["display_type"] != "no display_type" and flag_display_type == 0:
        #         view_msg_current = view_msg_current + msg["display_type"]
        #         flag_display_type = 1
        #         yield f"data:{view_msg_current}\n\n"
        #     yield view_msg_current
        # print(f"db_model_output:{db_model_output}")

        payload = await self._build_model_request()
        logger.info(f"payload request: \n{payload}")
        ai_response_text = ""
        span = root_tracer.start_span(
            "BaseChat.stream_call", metadata=payload.to_dict()
        )
        payload.span_id = span.span_id
        try:
            async for output in self.call_streaming_operator(payload):
                # Plugin research in result generation
                msg = self.prompt_template.output_parser.parse_model_stream_resp_ex(
                    output, 0
                )
                """
                非流式输出数据模型的["thoughts"]
                """
                # msg = self.get_data_by_re(db_model_output)
                # if msg["thoughts"] != "no thoughts" and flag_thoughts == 0:
                #     view_msg_current = view_msg_current + msg["thoughts"]
                #     flag_thoughts = 1
                #     yield f"data:{view_msg_current}\n\n"
                # view_message = view_message.replace("\n", "\\n")
                """
                流式输出数据模型的["thoughts"]
                """
                key = '"thoughts": "'
                key_index = 1
                current_chunks = msg  # 当前已经接收到的模型输出内容
                flag_key = 1  # 标记是key对应的值是否已经完全提取到
                if key in current_chunks and flag_key:
                    if current_chunks.count("\n") == key_index:
                        # 输出suggestions_of_query之后的字符
                        # print(current_chunks[current_chunks.find(key) + len(key):])
                        user_sug = current_chunks[current_chunks.find(key) + len(key) :]
                    elif current_chunks.count("\n") == key_index + 1:
                        # print(current_chunks[current_chunks.find(key) + len(key):current_chunks.find("\",", current_chunks.find(key) + len(key))])
                        user_sug = current_chunks[
                            current_chunks.find(key)
                            + len(key) : current_chunks.find(
                                '",', current_chunks.find(key) + len(key)
                            )
                        ]
                        flag_key = 0
                    else:
                        continue
                else:
                    continue

                view_msg_current = user_sug
                yield f"{view_msg_current}\n\n"
            # 模型完全输出之后，统一处理输出的所有内容
            # view_message = self.stream_plugin_call(output)
            ai_response_text, view_message = await self._no_streaming_sql_chart(
                    payload, output
                )
            yield f"{view_message}\n\n"
            span.end()
        except Exception as e:
            print(traceback.format_exc())
            logger.error("model response parse failed！" + str(e))
            self.current_message.add_view_message(
                f"""<span style=\"color:red\">ERROR!</span>{str(e)}\n  {ai_response_text} """
            )
            view_message = f"""<span style=\"color:red\">ERROR!</span>{str(e)}\n  {ai_response_text} \n\n"""
            span.end(metadata={"error": str(e)})

        # # 数据模型--非流式输出
        # payload = await self._build_model_request()
        # ai_response_text, view_message = await self._no_streaming_call_with_retry(
        #         payload
        #     )
        # yield f"{view_message}\n\n"

        print(f"db_model_text:{ai_response_text}")
        db_model_output = view_message

        # 使用评判家模型，给出用户建议
        db_name = self.db_name
        # TODO: table_info
        table_info = "table_info"
        current_user_input = self.current_user_input
        model_out_content = self.parse_data_model_msg(db_model_output)
        critic_model_input = (
            _DEFAULT_TEMPLATE_FOR_CRITIC_ZH.replace("{db_name}", db_name)
            .replace("{table_info}", table_info)
            .replace("{user_input}", current_user_input)
            .replace("{model_output}", str(model_out_content))
        )
        role_system = "你是一个数据模型输出内容的评审员"
        print(f"critic_model_outputing....")

        # critic_model_output
        user_sug = ""
        """非流式输出评判模型内容"""
        # critic_model_output = await self.aget_openai_client(critic_model_input, role_system)
        # try:
        #     critic_model_output_json = json.loads(critic_model_output)
        #     # user_sug = critic_model_output_json["thoughts_of_query"] + critic_model_output_json["suggestions_of_query"]
        #     user_sug = critic_model_output_json["suggestions_of_query"]
        # except:
        #     user_sug = critic_model_output
        """流式输出评判模型的全部内容"""
        # async for chunk in self.aget_openai_client_stream(critic_model_input, role_system):
        #     print(f"chunk:{chunk}")
        #     user_sug += chunk
        #     yield f"{view_message}{user_sug}\n\n"
        """流式输出评判模型指定key的内容"""
        key = '"suggestions_of_query": "'
        key_index = 3
        current_chunks = ""  # 当前已经接收到的模型输出内容
        flag_key = 1  # 标记是key对应的值是否已经完全提取到
        async for chunk in self.aget_openai_client_stream(
            critic_model_input, role_system
        ):
            current_chunks = current_chunks + chunk
            current_chunks = current_chunks.replace("\n    \n    ", "\n    ").replace("\n\n", "\n")
            if key in current_chunks and flag_key:
                if current_chunks.count("\n    ") == key_index:
                    # 输出suggestions_of_query之后的字符
                    # print(current_chunks[current_chunks.find(key) + len(key):])
                    user_sug = current_chunks[current_chunks.find(key) + len(key) :]
                elif current_chunks.count("\n    ") == key_index + 1:
                    # print(current_chunks[current_chunks.find(key) + len(key):current_chunks.find("\",", current_chunks.find(key) + len(key))])
                    user_sug = current_chunks[
                        current_chunks.find(key)
                        + len(key) : current_chunks.find(
                            '",', current_chunks.find(key) + len(key)
                        )
                    ]
                    flag_key = 0
                else:
                    continue
            else:
                continue
            yield f"{view_message}{user_sug}\n\n"

        print(f"critic_model_output:{[current_chunks]}")
        # save current_message
        # self.current_message.add_ai_message(ai_response_text + "\ncritic_model_output："+user_sug)
        # view_msg = self.stream_call_reinforce_fn(ai_response_text + "\ncritic_model_output："+user_sug)

        self.current_message.add_ai_message(view_message + user_sug)
        view_msg = self.stream_call_reinforce_fn(view_message + user_sug)
        self.current_message.add_view_message(view_msg)
        await blocking_func_to_async(
            self._executor, self.current_message.end_current_round
        )
