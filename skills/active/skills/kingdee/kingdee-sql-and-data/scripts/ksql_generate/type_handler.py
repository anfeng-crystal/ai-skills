"""类型处理器 - 根据 type 参数分发到对应的业务脚本生成逻辑"""

import logging
import sys
from pathlib import Path

# 获取当前脚本所在目录（如 skills/your_skill/scripts/）
SCRIPT_DIR = Path(__file__).parent
# 将根目录加入搜索路径
sys.path.append(str(SCRIPT_DIR))
sys.path.append(str(SCRIPT_DIR.parent)) # 通常需3级返回：scripts → skill_dir → skills → root

from db_connector import get_connection
from models import DBConfig
from script_generator import ScriptGenerator

logger = logging.getLogger(__name__)

# 支持的业务类型列表
SUPPORTED_TYPES = ["coderule", "import", "event", "perm", "schdule", "basedata", "openapi"]


class TypeHandler:
    """业务类型处理器"""

    def __init__(self, generator: ScriptGenerator, db_configs: dict):
        """
        Args:
            generator: ScriptGenerator 实例
            db_configs: {'meta': DBConfig, 'sys': DBConfig, 'workflow': DBConfig}
        """
        self.generator = generator
        self.db_configs = db_configs

    def dispatch(self, type_name: str, params: dict) -> str:
        """根据 type 分发到对应处理方法"""
        type_name = type_name.strip().lower()
        if type_name == "coderule":
            return self.handle_coderule(params.get("entity", ""))
        elif type_name == "import":
            return self.handle_import(params.get("entity", ""))
        elif type_name == "event":
            return self.handle_event(params.get("entity", ""))
        elif type_name == "perm":
            return self.handle_perm(params.get("number", ""))
        elif type_name == "schdule":
            return self.handle_schdule(params.get("number", ""))
        elif type_name == "basedata":
            return self.handle_basedata(
                params.get("entity", ""),
                params.get("filter", ""),
            )
        elif type_name == "openapi":
            return self.handle_openapi(params.get("number", ""))
        else:
            supported = ", ".join(SUPPORTED_TYPES)
            raise ValueError(f"不支持的类型: {type_name}，支持的类型: {supported}")

    @staticmethod
    def supported_types() -> list:
        return list(SUPPORTED_TYPES)

    def _lookup_fids(self, db_config: DBConfig, sql: str) -> list:
        """执行主查询，返回结果行列表。"""
        try:
            conn = get_connection(db_config)
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.error("主查询失败: %s, 错误: %s", sql, e)
            raise

    def _generate_for_table(self, db_key: str, table: str,
                            fields: str, where: str,
                            pk_field: str = "FID") -> str:
        """为单张表生成逐行 DELETE + INSERT 交替脚本。

        Args:
            db_key: 数据库标识 ('meta'/'sys'/'workflow')
            table: 表名
            fields: 查询字段列表
            where: SELECT 的 WHERE 条件
            pk_field: 主键字段名，用于 DELETE 语句（默认 FID）
                      多语言表（_L 后缀）DELETE 自动追加 FID 条件
        """
        db_config = self.db_configs[db_key]
        # 多语言表：DELETE WHERE 用 FPKID=xx AND FID=xx
        extra_delete = ["FID"] if table.upper().endswith("_L") and pk_field.upper() != "FID" else None
        try:
            script = self.generator.generate(
                db_config, table, fields, where,
                pk_field=pk_field, extra_delete_fields=extra_delete
            )
            if script:
                return f"-- {table}\n{script}"
            else:
                return f"-- {table}: 无数据\n"
        except Exception as e:
            return f"-- {table}: 查询失败 - {e}\n"

    def _build_fid_in_clause(self, fids: list) -> str:
        """将 FID 列表构建为 IN 子句值"""
        return ", ".join(f"'{fid}'" for fid in fids)

    def _table_exists(self, db_config: DBConfig, table_name: str) -> bool:
        """检查数据库中是否存在指定表"""
        try:
            conn = get_connection(db_config)
            cursor = conn.cursor()
            # 用 SELECT 1 探测，表不存在会抛异常
            cursor.execute(f"SELECT 1 FROM {table_name} WHERE 1=0")
            conn.close()
            return True
        except Exception:
            return False

    # ========== 编码规则 (coderule) ==========

    def handle_coderule(self, entity: str) -> str:
        if not entity:
            return "-- 错误：entity 参数不能为空\n"

        sys_config = self.db_configs["sys"]
        sql = f"SELECT FID FROM T_CR_CODERULE WHERE FBIZOBJECTID = '{entity}' AND FENABLE = '1'"
        rows = self._lookup_fids(sys_config, sql)

        if not rows:
            return f"-- 提示：实体编码 '{entity}' 不存在启用的编码规则\n"

        fids = [row[0] for row in rows]
        fid_clause = self._build_fid_in_clause(fids)
        results = []

        results.append(self._generate_for_table(
            "sys", "T_CR_CODERULE",
            "FEXAMPLE,FAPPMODE,FISADDVIEW,FISAPPCONDITION,FMASTERID,FISUNIQUE,FRULETYPE,FISMODIFIABLE,"
            "FCREATETIME,FBIZOBJECTID,FENABLE,FISUPDATERECOVER,FISAPPORG,FISSERIALNUMBER,FDISABLERID,"
            "FISCHECKCODE,FID,FSPLITSIGN,FCTRLMODE,FDISABLEDATE,FISLOG,FSTATUS,FNUMBER,FEXAMPLELENGTH,"
            "FISFAST,FMODIFIERID,FISNONBREAK,FMODIFYTIME,FCREATORID",
            f"FID IN ({fid_clause})"
        ))
        results.append(self._generate_for_table(
            "sys", "T_CR_CODERULE_L",
            "FID,FPKID,FLOCALEID,FNAME",
            f"FID IN ({fid_clause}) AND FLOCALEID = 'zh_CN'",
            pk_field="FPKID"
        ))
        results.append(self._generate_for_table(
            "sys", "T_CR_CODERULEENTRY",
            "FID,FINITIAL,FATTRIBUTETYPE,FSPLITSIGN,FISSORTITEM,FENTRYID,FSTEP,FCUTSTYLE,"
            "FATTUSINGMODE,FSEQ,FLENGTH,FISVISABLE,FFORMAT,FSETTINGVALUE,FADDSTYLE,FVALUEATRIBUTE,"
            "FISSPLITSIGN,FADDCHAR",
            f"FID IN ({fid_clause})",
            pk_field="FENTRYID"
        ))
        return "\n".join(results)

    # ========== 导入导出模板 (import) ==========

    def handle_import(self, entity: str) -> str:
        if not entity:
            return "-- 错误：entity 参数不能为空\n"

        sys_config = self.db_configs["sys"]
        sql = f"SELECT FID FROM T_BAS_IMPORTTEMPLATE WHERE FBIZOBJECT = '{entity}' AND FENABLE = '1'"
        rows = self._lookup_fids(sys_config, sql)

        if not rows:
            return f"-- 提示：实体编码 '{entity}' 不存在启用的导入导出模板\n"

        fids = [row[0] for row in rows]
        fid_clause = self._build_fid_in_clause(fids)
        results = []

        results.append(self._generate_for_table(
            "sys", "T_BAS_IMPORTTEMPLATE",
            "FID,FENABLEIMPORT,FMASTERID,FSTATUS,FNUMBER,FNAME,FTEMPLATETYPE,FCREATETIME,"
            "FMODIFIERID,FENABLE,FMODIFYTIME,FCOMMENT,FCREATORID,FBIZOBJECT",
            f"FID IN ({fid_clause})"
        ))
        results.append(self._generate_for_table(
            "sys", "T_BAS_IMPORTTEMPLATE_L",
            "FID,FPKID,FLOCALEID,FNAME",
            f"FID IN ({fid_clause}) AND FLOCALEID = 'zh_CN'",
            pk_field="FPKID"
        ))
        results.append(self._generate_for_table(
            "sys", "T_BAS_IMPORTTEMPLATEENTRY",
            "FID,FISIMPORT,FISFIELD,FIMPORTPROP,FPARENTENTRYID,FENTRYID,FFIELDKEY,FSEQ,"
            "FMUSTINPUT,FDESCRIPTION,FEXPORTPROP,FFIELDNAME",
            f"FID IN ({fid_clause})",
            pk_field="FENTRYID"
        ))
        return "\n".join(results)

    # ========== 订阅事件 (event) ==========

    def handle_event(self, entity: str) -> str:
        if not entity:
            return "-- 错误：entity 参数不能为空\n"

        wf_config = self.db_configs["workflow"]
        sql = f"SELECT FID FROM T_EVT_EVENT WHERE FENTITY = '{entity}' AND FSTATUS = '1'"
        rows = self._lookup_fids(wf_config, sql)

        if not rows:
            return f"-- 提示：实体编码 '{entity}' 不存在启用的订阅事件\n"

        event_fids = [row[0] for row in rows]
        event_fid_clause = self._build_fid_in_clause(event_fids)
        results = []

        results.append(self._generate_for_table(
            "workflow", "T_EVT_EVENT",
            "FID,FMODIFYDATE,FTYPE,FISPREINSDATA,FSCENE,FCREATEDATE,FOPERATION,FDESCRIPTION,"
            "FENTITY,FOPERNUMBER,FSTATUS,FNUMBER,FNAME,FMODIFIER,FSOURCE,FNUMBERVIEW,FISMODIFIED,FCREATER",
            f"FID IN ({event_fid_clause})"
        ))
        results.append(self._generate_for_table(
            "workflow", "T_EVT_EVENT_L",
            "FID,FPKID,FLOCALEID,FNAME",
            f"FID IN ({event_fid_clause}) AND FLOCALEID = 'zh_CN'",
            pk_field="FPKID"
        ))

        for event_fid in event_fids:
            sub_sql = f"SELECT FID FROM T_EVT_SUBSCRIPTION WHERE FEVENT = '{event_fid}' AND FSTATUS = '1'"
            sub_rows = self._lookup_fids(wf_config, sub_sql)

            if not sub_rows:
                results.append(f"-- T_EVT_SUBSCRIPTION: 事件 {event_fid} 无关联的启用订阅\n")
                continue

            sub_fids = [r[0] for r in sub_rows]
            sub_fid_clause = self._build_fid_in_clause(sub_fids)

            results.append(self._generate_for_table(
                "workflow", "T_EVT_SUBSCRIPTION",
                "FMODIFYDATE,FSERVICENUMBER,FSEQUENCE,FEXECUTORVALUE,FSERVICECONFIG,FEVENT,"
                "FERRORNOTIFY,FEVENTNUMBER,FISMODIFIED,FTIMINGSTRATEGY,FID,FISPREINSDATA,FCONDITION,"
                "FCREATEDATE,FISCONCURRENT,FSTATUS,FNOTIFYTEXT,FSERVICE,FNUMBER,FNAME,FEXPRESSION,"
                "FMODIFIER,FEXECUTOR,FERRORSTRATEGY,FCREATER",
                f"FID IN ({sub_fid_clause})"
            ))
            results.append(self._generate_for_table(
                "workflow", "T_EVT_SUBSCRIPTION_L",
                "FID,FPKID,FLOCALEID,FNAME",
                f"FID IN ({sub_fid_clause}) AND FLOCALEID = 'zh_CN'",
                pk_field="FPKID"
            ))

        return "\n".join(results)

    # ========== 权限项 (perm) ==========

    def handle_perm(self, numbers: str) -> str:
        if not numbers:
            return "-- 错误：number 参数不能为空\n"

        sys_config = self.db_configs["sys"]
        number_list = [n.strip().strip("'\"") for n in numbers.split(",") if n.strip()]
        in_clause = ", ".join(f"'{n}'" for n in number_list)

        sql = f"SELECT FID FROM T_PERM_PERMITEM WHERE FNUMBER IN ({in_clause})"
        rows = self._lookup_fids(sys_config, sql)

        if not rows:
            return f"-- 提示：权限编码 {numbers} 不存在对应的权限项\n"

        fids = [row[0] for row in rows]
        fid_clause = self._build_fid_in_clause(fids)
        results = []

        results.append(self._generate_for_table(
            "sys", "T_PERM_PERMITEM",
            "FID,FNUMBER,FINHERITMODE,FGROUP,FPREPERMITEMID,FDESCRIPTION,FBIZAPPID",
            f"FID IN ({fid_clause})"
        ))
        results.append(self._generate_for_table(
            "sys", "T_PERM_PERMITEM_L",
            "FID,FPKID,FLOCALEID,FNAME",
            f"FID IN ({fid_clause}) AND FLOCALEID = 'zh_CN'",
            pk_field="FPKID"
        ))
        return "\n".join(results)

    # ========== 调度计划 (schdule) ==========

    def handle_schdule(self, numbers: str) -> str:
        if not numbers:
            return "-- 错误：number 参数不能为空\n"

        sys_config = self.db_configs["sys"]
        number_list = [n.strip().strip("'\"") for n in numbers.split(",") if n.strip()]
        in_clause = ", ".join(f"'{n}'" for n in number_list)

        sql = f"SELECT FID,FJOBID FROM T_SCH_SCHEDULE WHERE FNUMBER IN ({in_clause}) AND FSTATUS = '1'"
        rows = self._lookup_fids(sys_config, sql)

        if not rows:
            return f"-- 提示：调度编码 {numbers} 不存在启用的调度计划\n"

        fids = [row[0] for row in rows]
        job_ids = [row[1] for row in rows if row[1]]
        fid_clause = self._build_fid_in_clause(fids)
        results = []

        results.append(self._generate_for_table(
            "sys", "T_SCH_SCHEDULE",
            "FTWENTY,FFIVE,FELEVEN,FNINE,FNO,FSUN,FTWO,FEIGHT,FNOV,FPLAN,FWED,FHOST,"
            "FTWENTYTWO,FFOUR,FMAR,FSEP,FENDTIME,FSIX,FMAY,FREPEATMODE,FTHIRTYONE,"
            "FBYDAYORWEEK,FTWENTYSEVEN,FTWENTYSIX,FTHIRTEEN,FAUG,FDESC,FFIFTEEN,"
            "FTWENTYONE,FBYWEEK,FTUES,FSEVENTEEN,FSEVEN,FTWENTYFOUR,FMON,FTHIRTY,"
            "FTHREE,FFOURTEEN,FJAN,FNINETEEN,FTHUR,FTEN,FFRI,FJOBID,FSTARTTIME,"
            "FOCT,FAPR,FSIXTEEN,FID,FSAT,FONE,FTWENTYEIGHT,FTWENTYTHREE,FTWELVE,"
            "FNOWEEK,FSTATUS,FNUMBER,FTWENTYFIVE,FEIGHTEEN,FCYCLENUM,FTWENTYNINE,"
            "FJUL,FDEC,FJUN,FFEB",
            f"FID IN ({fid_clause})"
        ))
        results.append(self._generate_for_table(
            "sys", "T_SCH_SCHEDULE_L",
            "FID,FPKID,FLOCALEID,FNAME",
            f"FID IN ({fid_clause}) AND FLOCALEID = 'zh_CN'",
            pk_field="FPKID"
        ))
        results.append(self._generate_for_table(
            "sys", "T_SCH_SCHEDULE_N",
            "FID,FSCHPRINCIPAL,FMSGRECEIVER,FSFAILNOTIFY,FSSUCCESSNOTIFY,FSMSGCONTENT,FSNOTIFYTYPE,FSTIMEOUT",
            f"FID IN ({fid_clause})"
        ))

        for job_id in job_ids:
            job_sql = f"SELECT FID,FTASKDEFINEID FROM T_SCH_JOB WHERE FID = '{job_id}' AND FSTATUS = '1'"
            job_rows = self._lookup_fids(sys_config, job_sql)

            if not job_rows:
                results.append(f"-- T_SCH_JOB: FJOBID={job_id} 无对应的启用作业\n")
                continue

            job_fids = [r[0] for r in job_rows]
            task_define_ids = [r[1] for r in job_rows if r[1]]
            job_fid_clause = self._build_fid_in_clause(job_fids)

            results.append(self._generate_for_table(
                "sys", "T_SCH_JOB",
                "FID,FTASKCLASSNAME,FTASKDEFINEID,FRUNMODE,FRUNBYUSERID,FJOBTYPE,FSTATUS,"
                "FNUMBER,FCONCURRENT,FSTRATEGY,FTIMEOUT,FRETRYTIME,FRUNBYLANG,FCANSTOP,FPARAMS,FRUNBYORGID",
                f"FID IN ({job_fid_clause})"
            ))
            results.append(self._generate_for_table(
                "sys", "T_SCH_JOB_L",
                "FID,FPKID,FLOCALEID,FNAME",
                f"FID IN ({job_fid_clause}) AND FLOCALEID = 'zh_CN'",
                pk_field="FPKID"
            ))

            if task_define_ids:
                td_clause = self._build_fid_in_clause(task_define_ids)
                results.append(self._generate_for_table(
                    "sys", "T_SCH_TASKDEFINE",
                    "FID,FCLASSNAME,FAPPID,FNUMBER",
                    f"FID IN ({td_clause})"
                ))

        return "\n".join(results)

    # ========== 开放API服务 (openapi) ==========

    def handle_openapi(self, numbers: str) -> str:
        if not numbers:
            return "-- 错误：number 参数不能为空\n"

        sys_config = self.db_configs["sys"]
        number_list = [n.strip().strip("'\"") for n in numbers.split(",") if n.strip()]
        in_clause = ", ".join(f"'{n}'" for n in number_list)

        sql = f"SELECT FID FROM T_OPEN_APISERVICE WHERE FNUMBER IN ({in_clause})"
        rows = self._lookup_fids(sys_config, sql)

        if not rows:
            return f"-- 提示：API编码 {numbers} 不存在对应的开放API服务\n"

        fids = [row[0] for row in rows]
        fid_clause = self._build_fid_in_clause(fids)
        results = []

        results.append(self._generate_for_table(
            "sys", "T_OPEN_APISERVICE",
            "FAPISERVICETYPE,FADDEDINFO,FAPIDEFTYPE,FORG_AUTHOR_FILTER,FOPERATION,FORDER_BY_HIDE,"
            "FMASTERID,FMUSTPARAM,FDISCRIPTION,FSTDMODIFYTIME,FCREATETIME,FPRESCRIPT,ISFAILCONTINUE,"
            "FREQTYPE,FISVID,FALLOWGUEST,FBIZOBJECT,FDISABLERID,FOUTPUTPARAM,FCU_LIMIT_TAC,"
            "FFILTERPARAM,FIS_ONLY_THIRDAPP_AUTH,FISOUTPARAWITHOUTSTATUS,FNAME,FREPTYPE,FPRESCRIPT_TAG,"
            "FISDYOBJRESULT,FCOSMICVER,FMODIFIERID,FPLUGIN,FWSMETHODNAME,FURLFORMAT,FCHECK_REPEAT_REQ,"
            "FCUSTOMMETHOD,FISFAILCONTINUE,FINPUTPARAM,FISKSQL,FSELECTPARAM,FCONTENTTYPE,FMETHODNAME,"
            "FENABLE,FISDESENSITIZE,FVERSION,FID,FIS_SYS_API,FNAMESPACE,FADDEDINFO_TAG,FURL,"
            "FDISABLEDATE,FSAVEOPERATION,FSTATUS,FCUSTOMSORT,FNUMBER,FMESSAGETYPE,FMODIFYTIME,"
            "FCLASSNAME,FAPPID,FHTTPMETHOD,FCREATORID",
            f"FID IN ({fid_clause})"
        ))
        results.append(self._generate_for_table(
            "sys", "T_OPEN_APISERVICE_L",
            "FID,FDISCRIPTION,FNAME,FLOCALEID,FPKID",
            f"FID IN ({fid_clause}) AND FLOCALEID = 'zh_CN'",
            pk_field="FPKID"
        ))
        results.append(self._generate_for_table(
            "sys", "T_OPEN_APIQUERYFILTER",
            "FID,FFILTERLINK,FFILTERCOMPARE,FFILTER_TYPE,FFILTERVALUE,FFILTERCOLUMN,"
            "FFILTERLEFTBRACKET,FENTRYID,FFILTER_CONSTANT,FSEQ,FFILTERRIGHTBRACKET,FFILTERLABEL",
            f"FID IN ({fid_clause})",
            pk_field="FENTRYID"
        ))
        results.append(self._generate_for_table(
            "sys", "T_OPENAPI_EXT",
            "FID,FENTRYID,FSEQ,FEXT_VALUE,FEXT_KEY",
            f"FID IN ({fid_clause})",
            pk_field="FENTRYID"
        ))
        results.append(self._generate_for_table(
            "sys", "T_OPEN_APIBODYENTRY",
            "FID,FISPATHVARIABLE,FEXAMPLE,FBODY_DATA_MODEL,FENTRYID,FIS_UNIQUE_KEY,FOBJPROPNAME,"
            "FIS_MUL_VALUE,FIS_BODY_CUSTOM,FBODY_LEVEL,FMUST,FPARAMTYPE,FPARENTENTRYID,"
            "FBODYPARAMDES,FSEQ,FDEFAULTVALUE,FPARAMNAME",
            f"FID IN ({fid_clause})",
            pk_field="FENTRYID"
        ))
        results.append(self._generate_for_table(
            "sys", "T_OPEN_APIRESPENTRY",
            "FID,FRESPPARAMTYPE,FENTRYID,FIS_RESP_CUSTOM,FRESPEXAMPLE,FRESPPARAMNAME,"
            "FRESPPARAMMUST,FIS_RESP_MUL_VALUE,FPARENTENTRYID,FSEQ,FRESP_DATA_MODEL,"
            "FRESP_LEVEL,FRESPDES,FRESPOBJPROPNAME",
            f"FID IN ({fid_clause})",
            pk_field="FENTRYID"
        ))
        results.append(self._generate_for_table(
            "sys", "T_OPEN_APIHEADERENTRY",
            "FID,FHEADERNAME,FENTRYID,FSEQ,FHEADERDES,FHEADERVALUE",
            f"FID IN ({fid_clause})",
            pk_field="FENTRYID"
        ))
        return "\n".join(results)

    # ========== 预置基础资料数据 (basedata) ==========

    def handle_basedata(self, entity: str, filter_cond: str = "") -> str:
        """预置基础资料数据脚本生成。

        根据实体编码从元数据库获取元数据信息，解析字段列表，
        按表分组后从业务库查询数据并生成 DELETE + INSERT 脚本。
        """
        if not entity:
            return "-- 错误：entity 参数不能为空\n"
        if not filter_cond:
            return "-- 错误：filter 过滤条件不能为空\n"

        from metadata_parser import (
            query_entity_meta, query_parent_fdata, parse_fields_from_xml,
            merge_fields, resolve_table_names, group_fields_by_table,
        )

        meta_config = self.db_configs["meta"]
        biz_config = self.db_configs.get("biz")
        if not biz_config:
            return "-- 错误：未配置业务库(biz)数据库连接\n"

        # 1. 查询实体元数据基本信息
        meta_result = query_entity_meta(meta_config, entity)
        if not meta_result:
            return f"-- 提示：实体编码 '{entity}' 在元数据库中不存在\n"

        inherit_path, fdata_xml, main_table = meta_result
        results = []
        results.append(f"-- 预置基础资料数据: {entity}")
        results.append(f"-- 主表: {main_table}")

        # 2. 获取父实体 fdata 列表
        parent_fdata_list = query_parent_fdata(meta_config, inherit_path)

        # 3. 解析所有字段（父实体 + 当前实体）
        all_fields_list = []
        for pdata in parent_fdata_list:
            all_fields_list.append(parse_fields_from_xml(pdata))
        all_fields_list.append(parse_fields_from_xml(fdata_xml))
        # logger.info("解析字段列表: %s", all_fields_list)

        # 4. 合并去重
        merged = merge_fields(all_fields_list)
        # logger.info("合并去重后的字段列表: %s", merged)

        # 5. 解析表名
        resolved = resolve_table_names(merged, main_table)

        # 6. 按表分组
        table_groups = group_fields_by_table(resolved)
        # logger.info("按表分组的字段列表: %s", table_groups)
        if not table_groups:
            return f"-- 提示：实体 '{entity}' 未解析到有效字段\n"

        # 7. 从业务库查询主表 FID
        fid_sql = f"SELECT FID FROM {main_table} WHERE {filter_cond}"
        fid_rows = self._lookup_fids(biz_config, fid_sql)

        if not fid_rows:
            return f"-- 提示：主表 {main_table} 中未查询到满足条件的数据 (条件: {filter_cond})\n"

        fids = [row[0] for row in fid_rows]
        fid_clause = self._build_fid_in_clause(fids)

        # 8. 按表生成脚本，主表优先
        if main_table in table_groups:
            fields_str = ",".join(table_groups[main_table])
            # 确保 FID 在字段列表中
            if "FID" not in [f.upper() for f in table_groups[main_table]]:
                fields_str = "FID," + fields_str
            results.append(self._generate_for_table(
                "biz", main_table, fields_str,
                f"FID IN ({fid_clause})", pk_field="FID"
            ))

        # 其他表
        for table, field_list in table_groups.items():
            if table == main_table:
                continue
            fields_str = ",".join(field_list)
            if "FID" not in [f.upper() for f in field_list]:
                fields_str = "FID," + fields_str

            # 判断主键：_L 后缀用 FPKID，其他用 FID
            if table.upper().endswith("_L"):
                pk = "FPKID"
                if "FPKID" not in [f.upper() for f in field_list]:
                    fields_str = "FPKID," + fields_str
            else:
                pk = "FID"

            results.append(self._generate_for_table(
                "biz", table, fields_str,
                f"FID IN ({fid_clause})", pk_field=pk
            ))

        # 9. 检查主表的多语言表是否存在，存在则获取全部字段生成脚本
        l_table = f"{main_table}_L"
        if l_table not in table_groups and self._table_exists(biz_config, l_table):
            results.append(self._generate_for_table(
                "biz", l_table, "*",
                f"FID IN ({fid_clause}) AND FLOCALEID = 'zh_CN'", pk_field="FPKID"
            ))

        return "\n".join(results)
