"""演示数据（运联科技 Iceberg 湖仓 240 张表中的 36 张核心表 + 8 个真实变更申请）。

设计原则：
- 全部确定性（无随机、无时间依赖的差异），seed 幂等后两次 SEED_SUMMARY 逐字一致；
- 表结构按「族」定义：订单 / 支付 / 用户 / 门店 / 商品 / 履约 / 退款 / 埋点 / 库存；
- 版本历史 = 该族字段列表的确定性前缀 + decimal 扩容（v1 的 amount 是 decimal(10,2)，v2 起放宽到 decimal(12,2)）；
- 变更申请只声明「操作」（drop / add / retype / rename），target_fields 由操作推导，
  真正的 diff / 兼容判定 / 影响面 / 迁移单全部由后端算法现算，seed 不写死任何判定结果。
"""

DEMO_PASSWORD = "Demo@2026"

DEMO_USERS = [
    ("admin@schemagate.io", "林可 · 平台管理员", "admin"),
    ("analyst@schemagate.io", "周棠 · 数据开发", "analyst"),
    ("viewer@schemagate.io", "陈默 · 下游只读", "viewer"),
]

ORG = "运联科技 · 数据平台组"

# ---------------------------------------------------------------- 字段族
# (字段名, 类型, 是否可空, 默认值, 注释)
FAMILIES: dict[str, list[tuple[str, str, bool, object, str]]] = {
    "order": [
        ("order_id", "bigint", False, None, "订单主键"),
        ("buyer_id", "bigint", True, None, "买家 ID"),
        ("shop_id", "bigint", True, None, "店铺 ID"),
        ("pay_channel", "string", True, None, "支付渠道"),
        ("amount", "decimal(12,2)", True, "0", "实付金额"),
        ("order_status", "string", True, None, "订单状态"),
        ("created_at", "timestamp", False, None, "下单时间"),
        ("updated_at", "timestamp", True, None, "更新时间"),
    ],
    "payment": [
        ("pay_id", "bigint", False, None, "支付流水主键"),
        ("order_id", "bigint", False, None, "订单 ID"),
        ("pay_channel", "string", True, None, "支付渠道"),
        ("pay_status", "string", True, None, "支付状态"),
        ("amount", "decimal(12,2)", True, "0", "支付金额"),
        ("trade_no", "string", True, None, "渠道交易号"),
        ("paid_at", "timestamp", True, None, "支付时间"),
        ("created_at", "timestamp", False, None, "落库时间"),
    ],
    "user": [
        ("user_id", "bigint", False, None, "用户主键"),
        ("user_name", "string", True, None, "昵称"),
        ("mobile", "string", True, None, "手机号（脱敏前）"),
        ("city", "string", True, None, "常驻城市"),
        ("balance", "decimal(12,2)", True, "0", "账户余额"),
        ("register_source", "string", True, None, "注册来源"),
        ("register_at", "timestamp", True, None, "注册时间"),
        ("last_login_at", "timestamp", True, None, "最近登录"),
    ],
    "shop": [
        ("shop_id", "bigint", False, None, "店铺主键"),
        ("shop_name", "string", True, None, "店铺名称"),
        ("shop_level", "string", True, None, "店铺等级"),
        ("city", "string", True, None, "所在城市"),
        ("monthly_gmv", "decimal(12,2)", True, "0", "月度 GMV"),
        ("business_status", "string", True, None, "营业状态"),
        ("open_at", "timestamp", True, None, "开店时间"),
        ("updated_at", "timestamp", True, None, "更新时间"),
    ],
    "item": [
        ("item_id", "bigint", False, None, "商品主键"),
        ("item_name", "string", True, None, "商品名称"),
        ("category_id", "bigint", True, None, "类目 ID"),
        ("brand", "string", True, None, "品牌"),
        ("list_price", "decimal(12,2)", True, "0", "标价"),
        ("sale_status", "string", True, None, "在售状态"),
        ("created_at", "timestamp", True, None, "创建时间"),
        ("updated_at", "timestamp", True, None, "更新时间"),
    ],
    "delivery": [
        ("waybill_no", "string", False, None, "运单号"),
        ("order_id", "bigint", False, None, "订单 ID"),
        ("carrier", "string", True, None, "承运商"),
        ("delivery_status", "string", True, None, "履约状态"),
        ("freight_amount", "decimal(12,2)", True, "0", "运费"),
        ("shipped_at", "timestamp", True, None, "发货时间"),
        ("delivered_at", "timestamp", True, None, "签收时间"),
        ("created_at", "timestamp", False, None, "创建时间"),
    ],
    "refund": [
        ("refund_id", "bigint", False, None, "退款单主键"),
        ("order_id", "bigint", False, None, "订单 ID"),
        ("refund_reason", "string", True, None, "退款原因"),
        ("refund_status", "string", True, None, "退款状态"),
        ("refund_amount", "decimal(12,2)", True, "0", "退款金额"),
        ("applied_at", "timestamp", True, None, "申请时间"),
        ("finished_at", "timestamp", True, None, "结案时间"),
        ("created_at", "timestamp", False, None, "创建时间"),
    ],
    "log": [
        ("event_id", "bigint", False, None, "事件主键"),
        ("user_id", "bigint", True, None, "用户 ID"),
        ("event_code", "string", True, None, "事件编码"),
        ("campaign_id", "bigint", True, None, "活动 ID"),
        ("cost_amount", "decimal(12,2)", True, "0", "投放成本"),
        ("event_at", "timestamp", True, None, "事件时间"),
        ("dt", "date", True, None, "分区日期"),
        ("created_at", "timestamp", False, None, "写入时间"),
    ],
    "inventory": [
        ("sku_id", "bigint", False, None, "SKU 主键"),
        ("shop_id", "bigint", True, None, "店铺 ID"),
        ("stock_qty", "bigint", True, None, "在库数量"),
        ("safety_qty", "bigint", True, None, "安全库存"),
        ("stock_value", "decimal(12,2)", True, "0", "库存金额"),
        ("snapshot_at", "timestamp", True, None, "快照时间"),
        ("dt", "date", True, None, "分区日期"),
        ("created_at", "timestamp", False, None, "写入时间"),
    ],
}

# v1 的金额字段是 decimal(10,2)，v2 起放宽为 decimal(12,2)：这是真实发生过的安全提升
AMOUNT_V1_TYPE = "decimal(10,2)"
AMOUNT_FIELD = "amount"


def fields_for_version(family: str, version: int, total_versions: int) -> list[dict]:
    """第 version 版的字段列表：确定性前缀 + 金额列的历史类型。"""
    spec = FAMILIES[family]
    keep = len(spec) - (total_versions - version)
    keep = max(2, keep)
    payload: list[dict] = []
    for index, (name, type_, nullable, default, comment) in enumerate(spec[:keep]):
        type_final = type_
        if name in {AMOUNT_FIELD, "monthly_gmv", "refund_amount", "freight_amount", "stock_value"} and version == 1:
            type_final = AMOUNT_V1_TYPE
        payload.append(
            {
                "name": name,
                "type": type_final,
                "nullable": nullable,
                "default": default,
                "comment": comment,
                "position": index,
            }
        )
    return payload


# ---------------------------------------------------------------- 36 张表
# (db_name, table_name, family, versions, partition_key, row_count, owner, description)
DATASETS: list[tuple[str, str, str, int, str | None, int, str, str]] = [
    ("ods", "ods_order_raw", "order", 4, "dt", 412_800_000, "周棠", "订单贴源表，按 dt 分区，Flink 实时入湖"),
    ("ods", "ods_pay_transaction", "payment", 2, "dt", 128_400_000, "王戈", "支付流水贴源表，与渠道对账口径一致"),
    ("ods", "ods_user_profile", "user", 3, None, 26_400_000, "刘越", "用户注册资料贴源表，含脱敏前手机号"),
    ("ods", "ods_shop_info", "shop", 2, None, 128_000, "何川", "门店主数据贴源表，日更"),
    ("ods", "ods_item_snapshot", "item", 2, "dt", 8_600_000, "何川", "商品快照，每天全量落一份"),
    ("ods", "ods_delivery_track", "delivery", 2, "dt", 96_200_000, "周驰", "运单轨迹贴源表"),
    ("ods", "ods_refund_apply", "refund", 2, "dt", 12_800_000, "孙倩", "售后退款申请贴源表"),
    ("ods", "ods_campaign_click", "log", 2, "dt", 320_400_000, "李蔓", "广告点击埋点贴源表"),
    ("ods", "ods_inventory_snapshot", "inventory", 2, "dt", 64_300_000, "吴桐", "库存快照贴源表"),
    ("ods", "ods_app_event", "log", 2, "dt", 1_280_000_000, "林可", "App 埋点事件贴源表"),
    ("dwd", "dwd_order_detail", "order", 4, "dt", 402_600_000, "周棠", "订单明细事实表，下游 12 个团队在用"),
    ("dwd", "dwd_pay_detail", "payment", 4, "dt", 126_900_000, "王戈", "支付明细事实表"),
    ("dwd", "dwd_user_base", "user", 3, None, 25_800_000, "刘越", "用户基础宽表，SCD2 拉链"),
    ("dwd", "dwd_shop_base", "shop", 2, None, 126_400, "何川", "门店基础宽表"),
    ("dwd", "dwd_item_base", "item", 2, "dt", 8_400_000, "何川", "商品基础宽表"),
    ("dwd", "dwd_delivery_detail", "delivery", 2, "dt", 94_800_000, "周驰", "履约明细事实表"),
    ("dwd", "dwd_refund_detail", "refund", 3, "dt", 12_600_000, "孙倩", "退款明细事实表"),
    ("dwd", "dwd_campaign_touch", "log", 2, "dt", 302_800_000, "李蔓", "营销触点事实表"),
    ("dwd", "dwd_inventory_daily", "inventory", 2, "dt", 62_800_000, "吴桐", "库存日快照事实表"),
    ("dwd", "dwd_traffic_session", "log", 2, "dt", 640_200_000, "林可", "会话流量事实表"),
    ("dws", "dws_shop_sales_1d", "shop", 3, "dt", 3_840_000, "李蔓", "门店日销汇总表"),
    ("dws", "dws_user_active_1d", "user", 2, "dt", 25_800_000, "李蔓", "用户日活汇总表"),
    ("dws", "dws_item_sales_1d", "item", 2, "dt", 8_400_000, "陈昊", "商品日销汇总表"),
    ("dws", "dws_delivery_sla_1d", "delivery", 2, "dt", 2_180_000, "周驰", "履约时效日汇总表"),
    ("dws", "dws_refund_rate_1d", "refund", 2, "dt", 1_260_000, "孙倩", "退款率日汇总表"),
    ("dws", "dws_campaign_roi_1d", "log", 2, "dt", 486_000, "王戈", "投放 ROI 日汇总表"),
    ("dim", "dim_shop", "shop", 3, None, 128_000, "何川", "门店维表，广播到所有下游"),
    ("dim", "dim_user", "user", 2, None, 25_800_000, "何川", "用户维表"),
    ("dim", "dim_item", "item", 2, None, 8_400_000, "何川", "商品维表"),
    ("dim", "dim_channel", "payment", 2, None, 1_200, "何川", "支付渠道字典维表"),
    ("dim", "dim_date", "log", 2, None, 10_958, "林可", "日期维表"),
    ("ads", "ads_gmv_daily", "shop", 4, "dt", 128_000, "陈昊", "管理驾驶舱 GMV 日报"),
    ("ads", "ads_delivery_sla", "delivery", 3, "dt", 1_280, "周驰", "履约时效月报"),
    ("ads", "ads_refund_daily", "refund", 2, "dt", 96_000, "孙倩", "售后日报"),
    ("ads", "ads_user_growth", "user", 2, "dt", 460_800, "李蔓", "增长月报"),
    ("ads", "ads_inventory_alert", "inventory", 2, "dt", 84_000, "吴桐", "缺货预警清单"),
]


def version_total() -> int:
    return sum(item[3] for item in DATASETS)


# 已提交版本的时间：以 2026-06-01 为基准，逐版本 +3 天，确定性
VERSION_BASE_DAY = "2026-06-01"


def version_committed_offsets(total_versions: int) -> list[int]:
    return [index * 3 for index in range(total_versions)]


# ---------------------------------------------------------------- 42 个下游消费方
# (表, 名称, 团队, 负责人, 引用列, 任务, 报表)
CONSUMERS: list[tuple[str, str, str, str, list[str], list[str], list[str]]] = [
    ("dwd.dwd_order_detail", "订单实时大屏", "实时数仓", "张岩", ["order_id", "amount"], ["t_order_realtime_agg"], []),
    ("dwd.dwd_order_detail", "经营日报 · GMV", "经营分析", "李蔓", ["amount", "pay_channel"], ["t_daily_gmv"], ["r_gmv_daily"]),
    ("dwd.dwd_order_detail", "渠道对账", "财务对账", "王戈", ["pay_channel"], ["t_channel_recon"], ["r_channel_diff"]),
    ("dwd.dwd_order_detail", "商家结算", "商家侧", "赵晗", ["amount", "shop_id"], ["t_settlement_calc"], []),
    ("dwd.dwd_order_detail", "退款率监控", "风控", "孙倩", ["order_id", "amount"], ["t_refund_watch"], []),
    ("dwd.dwd_order_detail", "订单明细导出", "BI 报表", "陈昊", ["order_id", "created_at"], ["t_order_export"], ["r_order_detail_dump"]),
    ("dwd.dwd_order_detail", "履约时效分析", "物流运营", "周驰", ["order_id", "shop_id"], ["t_delivery_eta"], []),
    ("dwd.dwd_pay_detail", "支付成功率看板", "实时数仓", "张岩", ["pay_status"], ["t_pay_success"], []),
    ("dwd.dwd_user_base", "用户画像特征", "算法特征", "刘越", ["user_id", "city"], ["t_user_feature"], []),
    ("dwd.dwd_shop_base", "商家分层", "商家侧", "赵晗", ["shop_id", "shop_level"], ["t_shop_tier"], []),
    ("dwd.dwd_shop_base", "门店热力图", "BI 报表", "陈昊", ["shop_id", "city"], ["t_shop_heatmap"], ["r_shop_heat"]),
    ("dwd.dwd_item_base", "商品在架同步", "数据服务", "何川", ["item_id", "sale_status"], ["t_item_sync"], []),
    ("dwd.dwd_item_base", "价格带分析", "经营分析", "李蔓", ["item_id", "list_price"], ["t_price_band"], ["r_price_band"]),
    ("dwd.dwd_delivery_detail", "承运商月度结算", "财务对账", "王戈", ["waybill_no", "freight_amount"], ["t_carrier_settle"], []),
    ("dwd.dwd_refund_detail", "退款原因归因", "风控", "孙倩", ["refund_id", "refund_reason"], ["t_refund_reason"], ["r_refund_reason"]),
    ("dwd.dwd_campaign_touch", "投放 ROI", "经营分析", "李蔓", ["campaign_id", "cost_amount"], ["t_campaign_roi"], []),
    ("dwd.dwd_inventory_daily", "库存预警", "供应链", "吴桐", ["sku_id", "stock_qty"], ["t_stock_alert"], ["r_stock_alert"]),
    ("dwd.dwd_traffic_session", "流量漏斗", "经营分析", "李蔓", ["event_id", "user_id"], ["t_funnel"], ["r_funnel"]),
    ("ods.ods_order_raw", "贴源校验", "数据平台", "林可", ["order_id"], ["t_ods_check"], []),
    ("ods.ods_pay_transaction", "支付源表对账", "财务对账", "王戈", ["pay_id", "amount"], ["t_pay_ods_recon"], []),
    ("ods.ods_user_profile", "画像回灌", "算法特征", "刘越", ["user_id", "mobile"], ["t_profile_backfill"], []),
    ("ods.ods_shop_info", "门店主数据同步", "数据服务", "何川", ["shop_id", "shop_name"], ["t_shop_master_sync"], []),
    ("ods.ods_item_snapshot", "商品快照归档", "数据服务", "何川", ["item_id"], ["t_item_archive"], ["r_item_archive"]),
    ("ods.ods_delivery_track", "轨迹补齐", "物流运营", "周驰", ["waybill_no"], ["t_track_fix"], []),
    ("ods.ods_refund_apply", "售后工单", "风控", "孙倩", ["refund_id", "refund_status"], ["t_after_sale"], []),
    ("ods.ods_campaign_click", "点击归因", "经营分析", "李蔓", ["campaign_id", "user_id"], ["t_click_attr"], []),
    ("ods.ods_inventory_snapshot", "库存快照校验", "供应链", "吴桐", ["sku_id", "stock_qty"], ["t_stock_check"], []),
    ("ods.ods_app_event", "埋点清洗", "数据平台", "林可", ["event_id", "event_code"], ["t_event_clean"], []),
    ("dws.dws_shop_sales_1d", "门店日报", "经营分析", "李蔓", ["shop_id", "monthly_gmv"], ["t_shop_daily"], ["r_shop_daily"]),
    ("dws.dws_user_active_1d", "沉默召回名单", "算法特征", "刘越", ["user_id", "mobile"], ["t_recall_list"], []),
    ("dws.dws_item_sales_1d", "商品销量榜", "BI 报表", "陈昊", ["item_id", "list_price"], ["t_item_rank"], ["r_item_rank"]),
    ("dws.dws_delivery_sla_1d", "时效达成看板", "物流运营", "周驰", ["carrier", "delivery_status"], ["t_sla_achieve"], ["r_sla_daily"]),
    ("dws.dws_refund_rate_1d", "退款率看板", "风控", "孙倩", ["refund_id", "refund_amount"], ["t_refund_rate"], []),
    ("dws.dws_campaign_roi_1d", "渠道成本归集", "财务对账", "王戈", ["campaign_id", "cost_amount"], ["t_channel_cost"], []),
    ("dim.dim_shop", "维表广播", "数据服务", "何川", ["shop_id", "shop_name"], ["t_dim_shop_broadcast"], []),
    ("dim.dim_user", "用户维表同步", "数据服务", "何川", ["user_id", "user_name"], ["t_dim_user_broadcast"], []),
    ("dim.dim_item", "商品维表同步", "数据服务", "何川", ["item_id", "item_name"], ["t_dim_item_broadcast"], []),
    ("dim.dim_channel", "渠道字典下发", "数据服务", "何川", ["pay_channel"], ["t_channel_dict"], ["r_channel_dict"]),
    ("ads.ads_gmv_daily", "管理驾驶舱", "BI 报表", "陈昊", ["dt", "monthly_gmv"], ["t_exec_dashboard"], ["r_exec_gmv"]),
    ("ads.ads_delivery_sla", "履约月报", "物流运营", "周驰", ["carrier", "freight_amount"], ["t_sla_monthly"], ["r_sla_monthly"]),
    ("ads.ads_refund_daily", "售后月报", "风控", "孙倩", ["refund_amount", "refund_status"], ["t_refund_monthly"], []),
    ("ads.ads_user_growth", "增长月报", "经营分析", "李蔓", ["user_id", "register_at"], ["t_growth_monthly"], ["r_growth"]),
]


# ---------------------------------------------------------------- 8 个变更申请
# ops: ("drop", name) / ("add", {name,type,nullable,default,comment}) / ("retype", name, type) / ("rename", old, new)
CHANGE_REQUEST_SPECS: list[dict] = [
    {
        "code": "CR-20260601-0001",
        "table": "ads.ads_gmv_daily",
        "summary": "驾驶舱 GMV 日报新增币种与渠道编码，支持跨境口径",
        "ops": [
            ("add", {"name": "currency", "type": "string", "nullable": True, "default": "CNY", "comment": "币种"}),
            ("add", {"name": "channel_code", "type": "string", "nullable": True, "default": None, "comment": "渠道编码"}),
        ],
        "status": "approved",
        "decided_by": "admin@schemagate.io",
        "decision_note": "仅新增可空字段，随下次调度自动生效",
    },
    {
        "code": "CR-20260601-0002",
        "table": "dwd.dwd_order_detail",
        "summary": "dwd_order_detail 删除 pay_channel，并把 amount decimal(12,2) 改 bigint",
        "ops": [
            ("drop", "pay_channel"),
            ("retype", "amount", "bigint"),
            ("add", {"name": "discount_rate", "type": "decimal(6,4)", "nullable": True, "default": None, "comment": "折扣率"}),
            ("add", {"name": "ext_json", "type": "string", "nullable": True, "default": None, "comment": "扩展属性"}),
            ("add", {"name": "settlement_no", "type": "string", "nullable": True, "default": None, "comment": "结算单号"}),
            ("add", {"name": "refund_flag", "type": "boolean", "nullable": True, "default": "false", "comment": "是否含退款"}),
            ("add", {"name": "channel_code", "type": "string", "nullable": True, "default": None, "comment": "渠道编码"}),
            ("add", {"name": "currency", "type": "string", "nullable": True, "default": "CNY", "comment": "币种"}),
        ],
        "status": "checked",
        "decided_by": None,
        "decision_note": None,
        "detect": True,
    },
    {
        "code": "CR-20260601-0003",
        "table": "dws.dws_shop_sales_1d",
        "summary": "门店日销汇总下线店铺等级，月 GMV 改为整数分",
        "ops": [
            ("drop", "shop_level"),
            ("retype", "monthly_gmv", "bigint"),
        ],
        "status": "checked",
        "decided_by": None,
        "decision_note": None,
    },
    {
        "code": "CR-20260601-0004",
        "table": "ods.ods_user_profile",
        "summary": "用户贴源表补充昵称与扩展 JSON",
        "ops": [
            ("add", {"name": "nickname", "type": "string", "nullable": True, "default": None, "comment": "展示昵称"}),
            ("add", {"name": "ext_json", "type": "string", "nullable": True, "default": None, "comment": "扩展属性"}),
        ],
        "status": "approved",
        "decided_by": "admin@schemagate.io",
        "decision_note": "纯新增，下游无感知",
    },
    {
        "code": "CR-20260601-0005",
        "table": "dws.dws_user_active_1d",
        "summary": "用户日活汇总删除手机号列（合规要求）",
        "ops": [("drop", "mobile")],
        "status": "rejected",
        "decided_by": "admin@schemagate.io",
        "decision_note": "沉默召回名单仍依赖 mobile，先做脱敏视图再下线",
    },
    {
        "code": "CR-20260601-0006",
        "table": "ods.ods_pay_transaction",
        "summary": "支付流水金额放宽到 decimal(18,2)，新增结算批次",
        "ops": [
            ("retype", "amount", "decimal(18,2)"),
            ("add", {"name": "settle_batch", "type": "string", "nullable": True, "default": None, "comment": "结算批次"}),
        ],
        "status": "submitted",
        "decided_by": None,
        "decision_note": None,
    },
    {
        "code": "CR-20260601-0007",
        "table": "ads.ads_delivery_sla",
        "summary": "履约月报运费扩容并补充 SLA 分钟数与超时标记",
        "ops": [
            ("retype", "freight_amount", "decimal(14,2)"),
            ("add", {"name": "sla_minutes", "type": "bigint", "nullable": True, "default": None, "comment": "SLA 承诺分钟"}),
            ("add", {"name": "breach_flag", "type": "boolean", "nullable": True, "default": "false", "comment": "是否超时"}),
        ],
        "status": "submitted",
        "decided_by": None,
        "decision_note": None,
    },
    {
        "code": "CR-20260601-0008",
        "table": "dwd.dwd_refund_detail",
        "summary": "退款明细补审计备注与扩展列，退款金额扩容",
        "ops": [
            ("add", {"name": "audit_note", "type": "string", "nullable": True, "default": None, "comment": "审计备注"}),
            ("add", {"name": "ext_json", "type": "string", "nullable": True, "default": None, "comment": "扩展属性"}),
            ("retype", "refund_amount", "decimal(14,2)"),
        ],
        "status": "submitted",
        "decided_by": None,
        "decision_note": None,
    },
]


def apply_ops(base_fields: list[dict], ops: list[tuple]) -> list[dict]:
    """按显式操作把基线字段改造成目标字段集（diff 由后端算法重新算，不在此断言）。"""
    fields = [
        {
            "name": item["name"],
            "type": item["type"],
            "nullable": bool(item.get("nullable", True)),
            "default": item.get("default"),
            "comment": item.get("comment") or "",
        }
        for item in base_fields
    ]
    for op in ops:
        kind = op[0]
        if kind == "drop":
            fields = [item for item in fields if item["name"] != op[1]]
        elif kind == "add":
            spec = dict(op[1])
            spec.setdefault("nullable", True)
            spec.setdefault("default", None)
            spec.setdefault("comment", "")
            fields.append(spec)
        elif kind == "retype":
            for item in fields:
                if item["name"] == op[1]:
                    item["type"] = op[2]
        elif kind == "rename":
            for item in fields:
                if item["name"] == op[1]:
                    item["name"] = op[2]
    return fields


SEED_AUDIT = [
    ("seed-audit-1", "admin@schemagate.io", "admin", "dataset.create", "dataset", {"table": "dwd.dwd_order_detail"}),
    ("seed-audit-2", "analyst@schemagate.io", "analyst", "change.create", "change_request", {"code": "CR-20260601-0002"}),
    ("seed-audit-3", "admin@schemagate.io", "admin", "change.approve", "change_request", {"code": "CR-20260601-0001"}),
]
