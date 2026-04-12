# 事故编号命名规范

为便于快速定位事故，统一使用结构化编号：

`INC-YYYYMMDD-SYSTEM-ISSUE`

## 字段说明

- `INC`：固定前缀，表示事故（Incident）。
- `YYYYMMDD`：事故发生日期，必须与“发生时间”一致。
- `SYSTEM`：系统或组件标识（示例：`DEVICE`、`PAY`、`MQ`）。
- `ISSUE`：故障类型标识（示例：`STATUS`、`DELAY`、`TIMEOUT`）。

说明：地区信息不放在文件命名里，统一通过独立字段 `地区/region` 在汇总表展示。

## 命名要求

- 仅允许大写字母、数字和连字符 `-`。
- 建议至少包含 `SYSTEM-ISSUE` 两段业务信息。
- 事故编号中的日期必须与 `发生时间` 字段一致。

## 命名示例

- `INC-20260305-DEVICE-STATUS`
- `INC-20260327-MQ-DATA-DELAY`
- `INC-20260329-PAY-CALLBACK-DELAY`
