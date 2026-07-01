# Deprecated API Blacklist

> Migrated from `kingdee-unit-test/deprecated-api-blacklist.md`.

## Base Data / Data Access

| Deprecated API | Replacement | Version | Note |
|---|---|---|---|
| `KingdeeBaseDataServiceHelper.loadSingle(pk, entity)` | `BaseDataServiceHelper.loadFromCache(pk, entity)` | 5.0 | Old version has no cache |
| `KingdeeBaseDataServiceHelper.loadSingleFromCache(...)` | `BaseDataServiceHelper.loadFromCache(...)` | 5.0 | Same replacement |
| `DynamicObjectUtils.copy(src)` | `OrmUtils.clone(src)` | 5.2 | Old deep copy has performance risk |
| `DataEntityUtils.toJson(obj)` | `SerializationUtils.toJsonString(obj)` | 5.0 | Old version has nested base-data limitations |

## Query / Save

| Deprecated API | Replacement | Version | Note |
|---|---|---|---|
| `QueryServiceHelper.query(entity, fields, filter, orderBy, limit)` | `QueryServiceHelper.query(entity, fields, filter, orderBy, top)` or `ORM.create().query(...)` | 5.0 | Old five-argument semantics are inconsistent |
| `BusinessDataServiceHelper.loadFromCache(pk, entity)` | `BusinessDataServiceHelper.loadFromCache(pks, entity)` | 5.0 | Prefer map-returning batch API |
| `SaveServiceHelper.update(obj)` | `SaveServiceHelper.update(new DynamicObject[]{obj})` | - | Batch form is safer for bulk work |

## Cache

| Deprecated API | Replacement | Version | Note |
|---|---|---|---|
| `CacheFactory.getMVCCache().getOrCreate(...)` | `CacheFactory.getCommonCacheFactory().getOrCreate(...)` | 5.0 | MVCCache is server-side only |

## Message / Notification

| Deprecated API | Replacement | Version | Note |
|---|---|---|---|
| `MessageInfo.setMessageContent(String)` | `MessageInfo.setContent(String)` | 5.0 | Normalized naming |

## Operation / BOTP

| Deprecated API | Replacement | Version | Note |
|---|---|---|---|
| `OperationServiceHelper.executeOperate(opKey, entity, ids)` | `OperationServiceHelper.executeOperate(opKey, entity, objs, OperateOption.create())` | 5.0 | Pass `OperateOption` explicitly |
| `ConvertServiceHelper.push(args)` old single-result return | `ConvertServiceHelper.push(args)` returning `PushResult` | 5.0 | Result API changed |

## User / Permission

| Deprecated API | Replacement | Version | Note |
|---|---|---|---|
| `RequestContext.get().getUserId()` | `RequestContext.get().getCurrUserId()` | - | New name is explicit |

## String / Utility

| Deprecated API | Replacement | Version | Note |
|---|---|---|---|
| `StringUtils.isEmpty(s)` from old `kd.bos.dataentity.utils` | `StringUtils.isBlank(s)` or `kd.bos.util.StringUtils.isEmpty(s)` | 5.0 | Check package path |

## Date

| Deprecated API | Replacement | Version | Note |
|---|---|---|---|
| `DateUtils.format(date)` default pattern | `DateFormatUtils.format(date, pattern)` | 5.0 | Default format mismatch risk |
