- # s-series-skill
  
  | name           | description                | license                       |
  | -------------- | -------------------------- | ----------------------------- |
  | s-series-skill | Go HTTP 服务重构与整合规范 | Complete terms in LICENSE.txt |
  
  ---
  
  ## 说明
  
  ### 角色
  
  你是一名**资深 Go 工程师**，熟悉大型 Go 项目结构与最佳实践，能够在现有项目基础上进行结构优化、模块整合与规范化重构。
  
  ---
  
  ### 目标
  
  根据用户需求，执行对应的操作，并**严格遵守本项目的架构规范与约束条件**。
  
  ---
  
  ### 项目架构
  
  当前项目使用的主要技术栈如下：
  
  - Gin
  - Gorm
  - Logrus
  - sqlx（后续废弃）
  - goframe 的 gdb（后续废弃）
  
  目前该服务**额外引入了以下外部服务**：
  
  - `variable-scheduler`
  - `variable-history`
  
  现阶段需要逐步将上述能力**整合进当前服务中**，以减少对外部服务的依赖。
  
  ---
  
  ### 项目背景
  
  该项目是一个 **HTTP 服务项目**，目前处于开发阶段，主要功能包括：
  
  - 设备管理
  - 用户管理
  - 摄像头管理
  - 脚本服务
  - 历史存储
  - 变量调度
  
  ---
  
  ### 功能需求
  
  - 优化项目整体结构
  - 逐步将当前服务所依赖的其他服务整合进来
  - 减少跨服务依赖关系
  - 按项目规划的分层结构梳理并放置代码
  
  ---
  
  ### 项目结构
  
  项目采用分层架构，各层职责如下：
  
  #### internal/biz
  
  - 逻辑层，存放主要业务逻辑
  - 结构体命名规则：`DeviceUsecase`
  - 方法约定：
    - 接收 `internal/model/defind` 中定义的请求结构体
    - 返回 `internal/model/defind` 中定义的响应结构体
  - 不直接处理传输协议相关逻辑
  
  ---
  
  #### internal/handler
  
  - 接口层，用于对接传输协议（如 HTTP）
  - 结构体命名规则：`DeviceHandler`
  - 主要职责：
    - 参数解析与校验
    - 调用 biz 层
    - 返回响应结果
  - 不包含业务逻辑
  
  ---
  
  #### internal/conf
  
  - 配置层
  - 定义配置文件对应的结构体
  - 不包含业务逻辑
  
  ---
  
  #### internal/model
  
  用于存放项目中的各类数据类型定义，按用途划分如下：
  
  ##### internal/model/entity
  
  - 数据库对象
  - 与数据库表结构一一对应
  
  ##### internal/model/domain
  
  - 逻辑层中使用的额外数据类型
  - 用于业务逻辑处理，不直接用于传输
  
  ##### internal/model/defind
  
  - 传输层使用的请求和响应结构体
  - 作为 Handler 与 Biz 层之间的数据契约
  
  ---
  
  #### internal/server
  
  - 项目的服务层
  - 用于定义需要**长期监听或运行**的模块
  
  包含以下子模块：
  
  - `internal/server/deviceRunner`  
    与采集端保持通讯
  
  - `internal/server/http`  
    HTTP 服务
  
  - `internal/server/lifecycle`  
    项目的生命周期管理
  
  - `internal/server/script`  
    脚本服务
  
  - `internal/server/engine.go`  
    Gin 引擎（由于需要被其他服务依赖，因此保留）
  
  - `internal/server/history.go`  
    引入变量历史存储服务
  
  - `internal/server/scheduler.go`  
    引入变量调度服务
  
  - `internal/server/virtual_variable_subscriber.go`  
    监听变量调度服务所传输的变量数据
  
  ---
  
  ### 约束
  
  在实现用户需求时，必须遵守以下约束条件：
  
  - 使用 **Go 1.23**
  - 遵循 Go 官方代码规范（`gofmt`）
  - 使用清晰、语义化的命名
  - 模块职责单一
  - 必要时返回 `error`，而不是使用 `panic`
  - 尽量不引入第三方依赖，除非明确说明原因
  - 所有导出对象（类型、函数、方法）必须有注释
  
  ---
  
  ### 输出格式
  
  - 如果实现涉及多个文件，必须使用注释标明文件路径，例如：
  
  ```go
  // file: internal/service/user/service.go
  ```