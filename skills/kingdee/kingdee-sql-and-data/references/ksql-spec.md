# KSQL 语法规范参考

> 基于《KSQL使用说明》整理，适用于苍穹KSQL引擎（SQL Server / MySQL / Oracle / PostgreSQL / DM / KingBase / TDSQL / Vastbase / GaussDB / GBase / YashanDB / OceanBase）

## 1. 概述

KSQL是SQL92的子集，抽取了SQL92的部分语法来满足金蝶ERP产品的最大功能集合。苍穹系统的SQL最终经过KSQL引擎解析翻译为不同数据库的方言SQL。

## 2. 支持的语句类型

### 2.1 DML（数据操作语言）

#### 2.1.1 SELECT

```
sel_sta ::= SELECT [mod_sta] sel_lis tab_exp | sel_sta UNION sel_sta
mod_sta ::= {ALL | DISTINCT} | [{ALL | DISTINCT}] TOP UINT1[,UINT2] | [{ALL | DISTINCT}] TOP UINT [PERCENT] [WITH TIES]
sel_lis ::= * | {db_nam . [tab_nam . ]* | val_exp [[AS] col_als]} [,…n]
tab_exp ::= FROM tab_src [WHERE sc_sta]
           [GROUP BY gb_exp [HAVING sc_sta]]
           [ORDER BY gb_exp]
gb_exp ::= {val_exp [ASC | DESC]} [,…n]
tab_src ::= {tab_ref} [,…n] | jon_tab
tab_ref ::= db_nam[ . tab_nam] [[AS] tab_als] | (sel_sta) [AS] tab_als [col_lis]
jon_tab ::= {tab_ref
             {
               {LEFT | RIGHT | FULL} [OUTER] | INNER
             } JOIN tab_ref ON sc_sta
            }
            {
              {
                {LEFT | RIGHT | FULL} [OUTER] | INNER
              } JOIN tab_ref ON sc_sta
            }
            […n]
```

**关键限制：**
- 不能使用多个 `*` 指定多个表的所有列：`SELECT *, * FROM A, B` 非法；`SELECT A.*, B.* FROM A, B` 合法
- `TOP ... WITH TIES` 仅在 SQL Server 中支持
- `TOP UINT1[,UINT2]` 中，UINT1 指定返回行数，UINT2 指定跳过记录数
- modifier statement 后只允许接受符合一般标识符和引号标识符命名规则的列定义：`SELECT TOP 10 NOW() FROM publishers` 非法
- **不允许在 FROM 关键字后同时使用引用表（逗号分隔）和联接表组成表资源**：`SELECT * FROM A, B LEFT JOIN C ON B.id = C.id` 非法

#### 2.1.2 DELETE

```
del_sta ::= DELETE [FROM] db_nam[ . tab_nam][WHERE sc_sta]
```

**关键限制：**
- 只支持单表删除
- 不支持多表 DELETE / DELETE ... FROM ... JOIN 语法

#### 2.1.3 INSERT

```
ins_sta ::= INSERT INTO db_nam[ . tab_nam][(col_lis)]{ VALUES (in_lis) | sel_sta}
```

#### 2.1.4 UPDATE

```
upd_sta ::= UPDATE db_nam[ . tab_nam] SET set_lis [ WHERE sc_sta]
set_lis ::= db_nam[[ . tab_nam] . col_nam] = upd_src
upd_src ::= NULL | val_exp
```

**关键限制：**
- **不支持 FROM 子句**
- **不支持多表 JOIN**
- **不支持表别名**（语法定义为 `db_nam[.tab_nam]`，无别名支持）
- `val_exp` 支持 `CASE WHEN` 表达式，因此 `SET col = CASE WHEN ... END` 是合法的

### 2.2 DDL（数据定义语言）

#### 2.2.1 CREATE

```
cre_sta ::= CREATE TABLE db_nam [ . tab_nam](tab_lis)
          | CREATE VIEW viw_nam [(col_lis)] AS sel_sta
          | CREATE [ UNIQUE ] INDEX indx_nam ON db_nam [ . tab_nam ](ind_lis)
```

#### 2.2.2 DROP

```
drp_sta ::= DROP TABLE db_nam [ . tab_nam]
          | DROP VIEW viw_nam
          | DROP INDEX tab_nam . indx_nam
```

#### 2.2.3 ALTER

```
alt_sta ::= ALTER TABLE db_nam [ . tab_nam]
            {
              {ADD | DROP | ALTER} col_def
              | ADD tab_cstr
              | DROP {cons_nam | PRIMARY KEY | CONSTRAINT cons_nam}
            }
```

## 3. 表达式

### 3.1 值表达式

```
val_exp ::= nval_exp | sval_exp | dtval_exp
```

### 3.2 数值表达式

```
nval_exp ::= term[{ + | -} term]] […n]
term ::= factor[{ * | /}factor] […n]
factor ::= [+ | -] num_pri
num_pri ::= UINT
          | db_nam[[.tab_nam ].col_nam]
          | COUNT(*)
          | AVG(nval_exp)
          | MAX(nval_exp)
          | MIN(nval_exp)
          | SUM(nval_exp)
          | COUNT(nval_exp)
          | COUNT(distinct nval_exp)
          | (sel_sta)
          | NULLIF (val_exp,val_exp)
          | CASE val_exp sim_whn [ELSE [NULL | val_exp]] END
          | CASE sc_whn [ELSE [NULL | val_exp]] END
          | (val_exp)
          | ABS(nval_exp)
          | CEILING(nval_exp)
          | COS(nval_exp)
          | EXP(nval_exp)
          | FLOOR(nval_exp)
          | LOG(nval_exp)
          | PI()
          | SIGN(nval_exp)
          | SIN(nval_exp)
          | SQRT(nval_exp)
          | LOG10(nval_exp)
          | ROUND(nval_exp [ ,UINT])
          | MOD(nval_exp,nval_exp)
          | ASCII(val_exp)
          | LENGTH(val_exp)
```

### 3.3 字符串表达式

```
sval_exp ::= CONSTSTR
           | CHAR(UINT)
           | LCASE(val_exp)
           | UCASE(val_exp)
           | LEFT(val_exp)
           | RIGHT(val_exp)
           | LTRIM(val_exp)
           | RTRIM(val_exp)
           | SUBSTRING(val_exp)
           | CONCAT(val_exp)
```

### 3.4 日期时间表达式

```
dtval_exp ::= DATESTR
            | TIMESTR
            | DATETIMESTR
            | NOW()
            | CURDATE()
            | CURTIME()
            | DAYOFMONTH(val_exp)
            | DAYOFWEEK(val_exp)
            | DAYOFYEAR(val_exp)
            | YEAR(val_exp)
            | MONTH(val_exp)
            | WEEK(val_exp)
            | HOUR(val_exp)
            | MINUTE(val_exp)
            | SECOND(val_exp)
            | MONTHNAME(val_exp)
            | DAYNAME(val_exp)
            | QUARTER(val_exp)
            | DATEADD({YY | MM | DD | HH | MI | SS},UINT,val_exp)
            | DATEDIF({YY | MM | DD | HH | MI | SS},UINT,val_exp)
            | CONVERT(DATETIME,val_exp)
```

### 3.5 搜索条件

```
sc_sta ::= {prd | NOT prd | (sc_sta) | NOT (sc_sta)}
           {{AND | OR} {prd | NOT prd | (sc_sta) | NOT (sc_sta)}} […n]
prd ::= val_exp
        { = | <> | != | < | <= | > | >= }
        {{ALL | SOME | ANY} (sel_sta) | val_exp}
      | val_exp [NOT] BETWEEN val_exp AND val_exp
      | val_exp [NOT] IN {(sel_sta) | in_lis}
      | val_exp [NOT] LIKE sval_exp [ESCAPE sval_exp]
      | IS [NOT] NULL
      | EXISTS (sel_sta)
```

## 4. 数据类型

| 类型 | 说明 |
|------|------|
| CHAR[(n)] | 固定长度字符，1~254 |
| VARCHAR[(n)] | 可变长度字符，1~4000 |
| NCHAR[(n)] | 固定长度UNICODE，1~2000 |
| NVARCHAR[(n)] | 可变长度UNICODE，1~4000 |
| NCLOB | 可变长度Unicode大对象，最大1G |
| SMALLINT | 短整数 [-2^15, 2^15-1] |
| INT / INTEGER | 整数 [-2^31, 2^31-1] |
| BIGINT | 长整数 [-2^63, 2^63-1] |
| DECIMAL[(p[,s])] | 定点数，精度1~31 |
| DATETIME | 日期时间 |
| BLOB | 二进制大对象，最大1G |

## 5. 常见不支持的SQL方言特性

以下特性在KSQL中**不支持**，校验时应标记为错误：

| 不支持特性 | 示例 |
|-----------|------|
| UPDATE ... FROM ... JOIN | `UPDATE T SET ... FROM T JOIN ... WHERE ...` |
| DELETE ... FROM ... JOIN | `DELETE T FROM T JOIN ... WHERE ...` |
| FROM后逗号表与JOIN混用 | `SELECT * FROM A, B LEFT JOIN C ON ...` |
| UPDATE使用表别名 | `UPDATE T t SET t.col = ...` |
| 窗口函数（ROW_NUMBER等） | KSQL规范中未定义 |
| CTE（WITH子句） | KSQL规范中未定义 |
| MERGE语句 | KSQL规范中未定义 |
| TRUNCATE语句 | KSQL规范中未定义 |
| 存储过程/函数定义 | KSQL规范中未定义 |
| LIMIT / OFFSET | KSQL使用TOP代替 |
| 全角引号标识符 | 需使用符合一般标识符和引号标识符命名规则 |
