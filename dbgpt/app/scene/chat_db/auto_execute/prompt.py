import json

from dbgpt._private.config import Config
from dbgpt.app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.chat_db.auto_execute.out_parser import DbChatOutputParser
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)

CFG = Config()


_PROMPT_SCENE_DEFINE_EN = "You are a database expert. "
_PROMPT_SCENE_DEFINE_ZH = "你是一个数据库专家. "

_DEFAULT_TEMPLATE_EN = """
Please answer the user's question based on the database selected by the user and some of the available table structure definitions of the database.
Database name:
     {db_name}
Table structure definition:
     {table_info}

Constraint:
    1.Please understand the user's intention based on the user's question, and use the given table structure definition to create a grammatically correct {dialect} sql. If sql is not required, answer the user's question directly.. 
    2.Always limit the query to a maximum of {top_k} results unless the user specifies in the question the specific number of rows of data he wishes to obtain.
    3.You can only use the tables provided in the table structure information to generate sql. If you cannot generate sql based on the provided table structure, please say: "The table structure information provided is not enough to generate sql queries." It is prohibited to fabricate information at will.
    4.Please be careful not to mistake the relationship between tables and columns when generating SQL.
    5.Please check the correctness of the SQL and ensure that the query performance is optimized under correct conditions.
    6.Please choose the best one from the display methods given below for data rendering, and put the type name into the name parameter value that returns the required format. If you cannot find the most suitable one, use 'Table' as the display method. , the available data display methods are as follows: {display_type}
    
User Question:
    {user_input}
Please think step by step and respond according to the following JSON format:
    {response}
Ensure the response is correct json and can be parsed by Python json.loads.

"""

_DEFAULT_TEMPLATE_ZH = """
请根据用户选择的数据库和该库的部分可用表结构定义来回答用户问题.
数据库名:
    {db_name}
表结构定义:
    {table_info}

表信息说明:
    '''
CREATE TABLE IF NOT EXISTS table_ICL (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- ID primary key
    ICL_ID TEXT, -- ICL ID
    ICL_Name TEXT NOT NULL, -- ICL 信息名称
    Description TEXT, -- 信息描述
    Category TEXT, -- 信息所属类别
    Information_Owner TEXT, -- 信息所有者
    Record_Creator TEXT, -- 信息记录创建者
    Status TEXT, -- 信息状态，可选值包括Approved和Rejected
    ICL_Security_Class TEXT, -- ICL 信息分类安全等级，可选值包括Special Protection (SP)和Basic Protection (BP)
    ICL_Classification_Result_Confidentiality TEXT, -- ICL 分类结果（机密性），可选值包括Strictly Confidential、Confidential、Non Public
    ICL_Classification_Result_Integrity TEXT, -- ICL 分类结果（完整性），可选值包括High Integrity、Medium Integrity、Low Integrity
    ICL_Classification_Result_Availability TEXT, -- ICL 分类结果（可用性），可选值包括High Availability、Medium Availability、Low Availability
    Submit_Date TEXT, -- 提交日期
    Approval_Date TEXT -- 批准日期
)
'''

'''
CREATE TABLE IF NOT EXISTS table_IOB (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- ID primary key
    IOB_ID TEXT, -- IOB ID
    IOB_Name TEXT NOT NULL, -- IOB 名称
    Level_1 TEXT, -- IOB 一级分类
    Level_2 TEXT, -- IOB 二级分类
    Level_3 TEXT, -- IOB 三级分类
    Method_of_Classification TEXT, -- IOB 分类方法，包括General Questionnaire和Personal Information Questionnaire
    IOB_Security_Class TEXT, -- IOB 分类安全等级，包括Basic Protection (BP)和Special Protection (SP)
    IOB_Classification_Result_Confidentiality TEXT, -- IOB 分类结果（机密性），可选值包括Strictly Confidential、Confidential、Non Public
    IOB_Classification_Result_Integrity TEXT, -- IOB 分类结果（完整性），可选值包括High Integrity、Medium Integrity、Low Integrity
    IOB_Classification_Result_Availability TEXT, -- IOB 分类结果（可用性），可选值包括High Availability、Medium Availability、Low Availability
    ICL_ID TEXT, -- ICL ID（外键）
    FOREIGN KEY (ICL_ID) REFERENCES table_ICL(ICL_ID) -- 外键约束，关联 ICL ID
)
'''

约束:
    1. 请根据用户问题理解用户意图，使用给出表结构定义创建一个语法正确的 {dialect} sql，如果不需要sql，则直接回答用户问题。
    2. 除非用户在问题中指定了他希望获得的具体数据行数，否则始终将查询限制为最多 {top_k} 个结果。
    3. 只能使用表结构信息中提供的表来生成 sql，如果无法根据提供的表结构中生成 sql ，请说：“提供的表结构信息不足以生成 sql 查询。” 禁止随意捏造信息。
    4. 请注意生成SQL时不要弄错表和列的关系
    5. 请检查SQL的正确性，并保证正确的情况下优化查询性能
    6.请从如下给出的展示方式种选择最优的一种用以进行数据渲染，将类型名称放入返回要求格式的name参数值种，如果找不到最合适的则使用'Table'作为展示方式，可用数据展示方式如下: {display_type}
用户问题:
    {user_input}
请一步步思考并按照以下JSON格式回复（严格按照以下格式输出内容）：
      {response}
确保返回正确的json并且可以被Python json.loads方法解析.

"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

PROMPT_SCENE_DEFINE = (
    _PROMPT_SCENE_DEFINE_EN if CFG.LANGUAGE == "en" else _PROMPT_SCENE_DEFINE_ZH
)

RESPONSE_FORMAT_SIMPLE = {
    "thoughts": "thoughts summary to say to user",
    "sql": "SQL Query to run",
    "display_type": "Data display method",
}


PROMPT_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.01

prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(
            _DEFAULT_TEMPLATE,
            response_format=json.dumps(
                RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4
            ),
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanPromptTemplate.from_template("{user_input}"),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ChatWithDbExecute.value(),
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=DbChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    temperature=PROMPT_TEMPERATURE,
    need_historical_messages=True,
)
CFG.prompt_template_registry.register(prompt_adapter, is_default=True)
