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
CREATE TABLE IF NOT EXISTS Basic_Information (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_editor TEXT,       -- 供应商编辑人
    email TEXT,                 -- 电子邮件
    telephone TEXT,             -- 电话号码
    quotation_date DATE,        -- 报价日期
    vendor_supplier TEXT,       -- BMW供应商名称
    bmw_supplier_number TEXT,   -- BMW供应商编号
    bmw_project TEXT,           -- BMW项目
    bmw_part_number TEXT,       -- BMW零件编号
    parts_designation TEXT,     -- 零件名称或零件的详细说明
    change_index_ai TEXT,       -- 变更索引，零件设计或规格的变更信息
    request_number_version TEXT,-- 请求编号版本
    variant TEXT                -- 变体，所报价零件的具体版本或型号
);

CREATE TABLE IF NOT EXISTS Cost_Analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bmw_part_number TEXT,                             -- BMW零件编号
    quotation_date DATE,                              -- 报价日期
    material_costs DECIMAL(10, 2),                    -- 材料成本
    manufacturing_costs DECIMAL(10, 2),               -- 制造成本
    total_production_costs DECIMAL(10, 2),            -- 总生产成本
    included_packaging_transportation BOOLEAN,        -- 包含包装运输
    included_duties BOOLEAN,                          -- 包含关税
    devices_and_subsequent_dies DECIMAL(10, 2),       -- 设备和后续模具
    scrap_costs DECIMAL(10, 2),                       -- 废料成本
    total_costs_9_0_X DECIMAL(10, 2),                 -- 总成本9.0.X
    other_surcharges DECIMAL(10, 2),                  -- 其他附加费（管理费等）
    scrap_costs_material DECIMAL(10, 2),              -- 材料废料成本
    scrap_costs_manufacturing DECIMAL(10, 2),         -- 制造废料成本
    quotation_basis_price_2 DECIMAL(10, 2),           -- 报价基础价格2
    raw_material_cost_adjustment_clause_material DECIMAL(10, 2),  -- 原材料成本调整条款（材料）
    raw_material_cost_adjustment_clause_energie DECIMAL(10, 2),   -- 原材料成本调整条款（能源）
    duties_supplier_bmw DECIMAL(10, 2),               -- 供应商-BMW关税
    transport_costs_supplier_bmw DECIMAL(10, 2),      -- 供应商-BMW运输成本
    quotation_price_2 DECIMAL(10, 2),                 -- 报价价格2
    one_time_payments DECIMAL(10, 2),                 -- 一次性付款
    development_costs_one_time DECIMAL(10, 2),        -- 一次性开发成本
    special_tools DECIMAL(10, 2),                     -- 特殊工具
    total_one_time_payments DECIMAL(10, 2),           -- 总一次性付款
    application_costs_per_part DECIMAL(10, 2),        -- 每个零件的应用成本
    distribution_administrative_overhead_costs DECIMAL(10, 2),  -- 分销管理间接成本
    imported_material_costs DECIMAL(10, 2),           -- 进口材料成本
    local_material_costs DECIMAL(10, 2),              -- 本地材料成本
    one_time_and_instalment_payments DECIMAL(10, 2),  -- 一次性和分期付款
    other_costs DECIMAL(10, 2),                       -- 其他成本
    other_process_costs DECIMAL(10, 2),               -- 其他工艺成本
    price_indication_order_currency_aw1 DECIMAL(10, 2),  -- 订单货币价格指示 (AW1)
    profit DECIMAL(10, 2),                            -- 利润
    raw_material_imported_and_local DECIMAL(10, 2),   -- 原材料（进口和本地）
    special_direct_costs_other_manufacturing_sekof_and_subsequent_dies DECIMAL(10, 2),  -- 其他制造特殊直接成本（SEKOF和后续模具）
    special_direct_costs_substantial_process_manufacturing_sekof_and_subsequent_dies DECIMAL(10, 2),  -- 实质性工艺制造特殊直接成本（SEKOF和后续模具）
    special_tools_other_process_manufacturing DECIMAL(10, 2),  -- 其他工艺制造特殊工具
    special_tools_substantial_process_manufacturing DECIMAL(10, 2),  -- 实质性工艺制造特殊工具
    substantial_process_costs DECIMAL(10, 2),         -- 实质性工艺成本
    total_import_value_cif DECIMAL(10, 2),            -- 总进口价值（CIF）
    total_lc_manufacturing_costs DECIMAL(10, 2),      -- 总本地制造成本
    lc_rate_calculation DECIMAL(10, 2),               -- 本地成本率计算
    lc_rate_percentage DECIMAL(5, 2),                 -- 本地成本率百分比
    development_costs DECIMAL(10, 2)                  -- 开发成本
);

CREATE TABLE IF NOT EXISTS Part_Assumption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bmw_part_number TEXT,                             -- BMW零件编号
    production_run_time_years DECIMAL(5, 2),          -- 生产运行时间（年）
    total_volume_inquiry_parts INTEGER,               -- 零件总询价量
    peak_volume_year_parts_per_year INTEGER,          -- 每年峰值产量（件/年）
    plan_capacity_parts_per_year INTEGER,             -- 计划产能（件/年）
    manufacturing_lot_size_parts INTEGER,             -- 生产批量大小（件）
    production_start_sop_mm_yyyy DATE,                -- 生产开始日期（月/年）
    drawing_index_z1 TEXT                             -- 图纸索引Z1
);

CREATE TABLE IF NOT EXISTS Supplier_Assumption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bmw_supplier_number TEXT,                         -- BMW供应商编号
    manufacturing_site_country_location TEXT,         -- 生产地点所在国家
    country_of_distribution_location TEXT,            -- 分销国家/位置
    hours_worked_per_year_h DECIMAL(7, 2),            -- 每年工作小时数
    shifts_per_week INTEGER,                          -- 每周轮班次数
    order_currency_1_aw1 TEXT,                        -- 订单货币1 (AW1)
    quotation_currency_2_aw2_opt TEXT,                -- 报价货币2 (AW2，可选)
    quotation_currency_3_aw3_opt TEXT,                -- 报价货币3 (AW3，可选)
    lta_long_term_agreement TEXT                      -- 长期协议 (LTA)
);

CREATE TABLE IF NOT EXISTS Other_Data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bmw_part_number TEXT,                             -- BMW零件编号
    hts_code_component TEXT,                          -- HTS编码组件
    part_dimensions_l_w_h_mm TEXT,                    -- 零件尺寸（长x宽x高，毫米）
    unpacked_parts_weight_kg DECIMAL(10, 3),          -- 未包装零件重量（千克）
    total_weight_kg DECIMAL(10, 3),                   -- 总重量（千克）
    terms_of_delivery TEXT,                           -- 交付条款
    supply_type_kovp_call_up_status TEXT              -- 供应类型KOVP调用状态
);

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
请一步步思考并按照以下JSON格式回复（严格按照以下格式输出中文内容）：
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


PROMPT_NEED_STREAM_OUT = True

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
