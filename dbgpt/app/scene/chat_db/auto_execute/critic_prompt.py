_DEFAULT_TEMPLATE_FOR_CRITIC_ZH = """
你是一个数据模型输出内容的评审员。请根据用户的问题，结合已有的数据表信息，对数据模型的输出结果进行分析评判，并针对用户问题给出修改建议。

数据库名:
    {db_name}
数据表结构信息:
    {table_info}
数据表字段描述:
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

用户问题:
    {user_input}

数据模型的输出结果：
    {model_output}

理想的用户问题应具备以下特点：
    1. 清晰的逻辑表达，避免模糊的问题描述，从而造成歧义。
    2. 明确的查询意图，输入的问题需要明确表达用户想要获取的信息。
    3. 尽量包含关键信息，以便模型能够更好地理解用户的需求。
    4. 如果用户对结果有排序、行数有要求，应在问题中明确指出。
    5. 如果用户有特定的数据展示要求，应在问题中说明。

理想的数据模型输出应具备以下特点：
    1. 结果准确，回答的问题应该与用户的问题匹配，不应该偏离主题。
    2. thoughts、sql、display_type部分应该完整，不应该缺失。
    3. thoughts内容逻辑清晰，回答问题的同时，应该给出解释，以便用户理解。
    4. sql部分的内容不能为空，且生成的sql语法、格式正确。
    5. display_type部分应该根据数据的特点选择合适的展示方式，以便用户更好地理解数据。
    6. db_data部分如果有数据输出，应该与sql查询结果匹配，不应该有数据缺失或重复。

分析评价内容的输出约束：
    1. 请注意思考评判内容时，应该综合考虑用户问题、数据表信息、数据模型输出的sql等多方面因素。
    2. thoughts_of_query应结合数据表信息、用户问题、数据模型的输出进行评判，给出评价。
    3. thoughts_of_sql应结合数据表信息、用户问题、数据模型输出的sql进行评判，给出评价。
    4. suggestions_of_query为直接返回给用户的query修改建议。
    5. suggestions_of_sql为针对sql的修改建议。

请一步步思考并按照以下JSON格式回复（严格按照以下格式输出内容）：
{
    "thoughts_of_query": "根据给出的信息对用户的问题进行评判",
    "thoughts_of_sql": "根据给出的信息对模型输出的sql进行评判",
    "suggestions_of_query": "根据thoughts_of_query给出针对query的修改建议",
    "suggestions_of_sql": "根据thoughts_of_sql给出针对sql的修改建议",
}
确保返回正确的json并且可以被Python json.loads方法解析.

"""

RESPONSE_FORMAT_SIMPLE = {
    "thoughts_of_query": "根据给出的信息以对用户的问题进行评判",
    "thoughts_of_sql": "根据给出的信息以对模型输出sql进行评判",
    "suggestions_of_query": "根据thoughts_of_query给出针对query的修改建议",
    "suggestions_of_sql": "根据thoughts_of_sql给出针对sql的修改建议",
}


PROMPT_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.01


API_KEY_ZHIPU = "f90aefe316464dee080c545e6cca1c79.Vgr7uQds7Qobna0e"