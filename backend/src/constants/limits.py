"""限额常量。"""

RATE_WINDOW_SECONDS = 60
MAX_PAGE_SIZE = 200
# 一次 diff 最多比较的字段数（防止超大 target_fields 拖垮同步接口）
MAX_FIELDS_PER_REQUEST = 300
MAX_EXPORT_ROWS = 20000
