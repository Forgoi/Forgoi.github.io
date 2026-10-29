## 这一课解决什么问题

上一课用 `state.Dependency` 串起组件读写。这一课再往前一步：Job 要创建实体、删除实体、添加或移除组件时，如何把结构变化安排到合适的时机？

核心流程是：**先记录命令，等记录者完成，再 Playback，把命令应用到 World。** EntityCommandBuffer（ECB）保存命令；ECB System 可以负责统一等待、回放和释放缓冲区。

本课已完成概念学习、手动与自动回放两个实验。两次运行都由学习者确认符合预期：实验产物数量 `0 → 0 → 1`，最终组件值 `42`。这是正确性观察，不是并行效率或性能基准；ParallelWriter 与 sortKey 只做了理论学习。

## 记录、Complete、Playback 是三件事

假设 Job 执行 `ecb.DestroyEntity(entity)`，这时它把删除命令写进 ECB，实体不会因为“已经记录”而立刻消失。即使随后调用生产者的 `Complete()`，也只是确保记录工作及其依赖完成，不会顺便执行 `ecb.Playback()`。

| 时点 | 发生的事情 | 这条删除命令是否已改变 World |
| --- | --- | --- |
| Job 正在记录 | 命令写入缓冲区 | 否 |
| 生产者 Complete 返回 | 记录者已完成，缓冲区可以安全交接 | 否 |
| Playback 执行命令 | 真正修改实体与组件 | 是 |

学习时的两次判断，都确认了这个边界：记录了删除命令但尚未回放，实体仍在；Complete 之后但尚未回放，也不能把它当作已经删除。

普通组件数值更新通常可以像上一课那样直接写入；创建、销毁实体或增删组件涉及结构变化，需要考虑 Chunk 布局与同步。ECB 把操作推迟到约定的处理点，但不会消除结构变化的成本，也不是提交后马上生效的接口。

## 手动实验：完成记录以后，数量仍然是零

[下载 EcbPlaybackExperiment.cs](/downloads/EcbPlaybackExperiment.cs)

文件使用独立命名空间 `EcbPlaybackLesson`，目标环境为 Unity 6000.3.25f1、Entities 1.5.0、Burst 1.8.30。保持文件名，放在 `Assets` 下而非 `Editor` 目录，在空场景的普通空 GameObject 上挂载 `EcbPlaybackExperiment`，进入 Play。无需 SubScene、Baker 或挂载 ISystem。

它只统计 `ExperimentMarker` 标记的实验产物，不是整个 World 的实体总数。下面是完整脚本中的核心顺序，省略了初始化与异常清理，不能单独作为完整脚本运行：

```csharp
producer = new RecordCommandsJob
{
    Ecb = ecb,
    MarkerArchetype = markerArchetype
}.Schedule();

producer.Complete();
int afterComplete = query.CalculateEntityCount();

ecb.Playback(em);
int afterPlayback = query.CalculateEntityCount();
```

记录 Job 内部先记录创建，再记录添加数值组件：

```csharp
Entity temporary = Ecb.CreateEntity(MarkerArchetype);
Ecb.AddComponent(temporary, new ExperimentValue { Value = 42 });
```

学习者确认 Console 与以下预期一致，而非另外粘贴了一份完整日志：

```text
[ECB] 记录前 count = 0
[ECB] Complete 后 count = 0
[ECB] Playback 后 count = 1, value = 42
[ECB] PASS：Complete 只等记录；Playback 才改变 World。
```

第二个零很关键：这里确实已经显式 Complete，记录完成仍不等于实体创建完成。`Start()` 在主线程调用 Playback 后，才查到带数值 42 的产物。

## temporary 只是同一个 ECB 内的占位符

`ecb.CreateEntity()` 返回的 `temporary` 看起来也是 Entity，但此时还没有对应的真实 World 实体。它用于让**同一个 ECB** 内后续命令指向“稍后要创建的那个实体”。回放时，ECB 会把这些引用映射到实际创建的实体。

因此，不能把 temporary 当作真实实体交给 EntityManager 查询，也不能拿到另一个 ECB 中随意使用。要获取回放后的真实产物，本实验通过专属标记 Query 找到它，而不是把临时句柄当成稳定 ID 留下来。

## 释放缓冲区，不等于删除产物

手动脚本的 `finally` 依次做三件事：

```csharp
producer.Complete();
ecb.Dispose();
em.DestroyEntity(query);
```

再次 Complete 用于异常路径：释放 ECB 前仍要确保没有 Job 在写它。Dispose 释放命令缓冲区占用的资源；`DestroyEntity(query)` 才是独立的实体清理操作。Query 本身由 `using` 释放。

所以手动实验日志里虽然出现了 `count = 1`，本次 `Start()` 结束后产物会被主动删除，不会保留下来等待查看。若启动前已经存在同标记实体，脚本会跳过运行，不接管或删除那些已有产物。

## 自动回放：把管理交给 ECB System

[下载 AutomaticEcbExperiment.cs](/downloads/AutomaticEcbExperiment.cs)

这份脚本使用独立命名空间 `AutomaticEcbLesson`，不覆盖手动版本。保持文件名，在新的空场景中只挂一个 `AutomaticEcbExperiment` MonoBehaviour；两个 ISystem 自动创建，不是 GameObject 组件。使用默认 Play Mode 重载设置、正常客户端的默认 World 与 PlayerLoop，并保留 Presentation 阶段；它不是面向纯服务器 World 的实验。

生产者位于 Simulation 组，在 `EndSimulationEntityCommandBufferSystem` 之前更新。关键代码是：

```csharp
var singleton = SystemAPI.GetSingleton<EndSimulationEntityCommandBufferSystem.Singleton>();
EntityCommandBuffer ecb = singleton.CreateCommandBuffer(state.WorldUnmanaged);

state.Dependency = new RecordCommandsJob
{
    Ecb = ecb,
    ResultArchetype = _resultArchetype
}.Schedule(state.Dependency);
```

这三个步骤各有职责：

1. `GetSingleton` 取得现有 ECB System 的访问入口，并在这一写法中参与依赖登记；没有创建一个新 System。
2. `CreateCommandBuffer` 申请由该 ECB System 管理的 ECB。缓冲区的回放和释放归它负责。
3. 普通 IJob 的 `Schedule` 返回句柄，必须显式写回 `state.Dependency`。输入依赖与返回句柄的登记，配合 singleton 访问，使 ECB System 能等待这个记录者。

仅仅拿到 ECB，不代表任何地方调度的 Job 都会自动被追踪。不能漏掉依赖登记，也不能把其他 API 路径与这里的 singleton 用法混为一谈。

到 ECB System 更新时，它在主线程等待已登记的生产者，再 Playback，最后 Dispose 自己管理的缓冲区。业务 System 不应再手动回放或释放同一个 ECB。**自动管理只是把等待放到统一的位置，不是取消等待，也不是让 Playback 在工作线程并行执行。** 这与 Unity 的[自动回放与释放说明（Entities 1.4 在线补充）](https://docs.unity3d.com/Packages/com.unity.entities@1.4/manual/systems-entity-command-buffer-automatic-playback.html)一致；本课具体 API 另按 1.5.0 包源码核对。

## 自动实验的三个观察点

学习者确认下面三条观察结果符合预期；自动版本没有单独的 PASS 日志，不应补写一条：

```text
[Auto ECB] ① 记录前 count = 0
[Auto ECB] ② Schedule 后、自动 Playback 前 count = 0
[Auto ECB] ③ 自动 Playback 后 count = 1, value = 42
```

这里统计的是 `AutoEcbMarker` 产物，不包括控制运行的 `AutoEcbRun` 实体。第二条只说明尚未 Playback，**不能证明 Job 已完成记录**：它可能还未开始、正在执行，或者已经完成。这与手动实验明确 Complete 后再计数不同。

本例的观察系统放在 Presentation 组。在默认 PlayerLoop 中，Simulation 及其 EndSimulation ECB System 完成后，才轮到 Presentation，所以第三条能观察到回放后的结果。不要简单把普通 Simulation System 用 `UpdateAfter` 排在 EndSimulation 后面：EndSimulation 的 `OrderLast` 排序约束还需要一起考虑。

也不要把自动管理理解成“任何时候提交，都保证本帧回放”。是否赶上本轮处理，取决于提交与对应 ECB System 更新的先后；如果更新点已经过去，就要等它下一次处理。

## 自动版本怎样只运行一次、怎样清理

`AutoEcbRun.Stage` 依次经过 0、1、2：尚未调度、已调度、已观察（或中止）。后续更新不会重复记录和打印。

与手动版本不同，自动版本会保留创建的实体。ECB System 已经 Dispose 缓冲区，但产物仍然存在，可以在 Entities Hierarchy 中查看。销毁实验组件时，`OnDestroy` 只提出 `CleanupRequested`，由随后安全的 Presentation 更新删除实验标记产物及运行开关，避免抢在待执行的 Playback 前清理、之后又被创建回来。若 World 先销毁，其实体随 World 一起销毁。

这些清理路径来自脚本设计与源码检查。本次运行确认的是三条主路径日志，**没有另行验证销毁组件、重复挂载、卸载场景等清理与异常路径**。

## ParallelWriter 与 sortKey：理解过，但没有跑实验

两个实验各只有一个普通 IJob 写 ECB，因此都不需要 `ParallelWriter` 或 sortKey。

多线程并行记录时，使用适合并行写入的 `EntityCommandBuffer.ParallelWriter`。各线程实际抵达的时间不稳定；sortKey 给回放提供排序依据，较小的键先处理。它不是线程编号，也不决定 Job 的实际执行先后。设计时应使用与调度时序无关的键，并避免依赖不同线程同键命令的偶然到达顺序。

这里的“并行”指记录命令；正常 ECB System 仍在主线程执行回放。本课没有 ParallelWriter 运行结果、线程数、Profiler 重叠时间线或速度提升数据。

## 本课完成到哪里

已理清记录、等待、回放的边界，同 ECB 临时实体引用，缓冲区与实体的独立生命周期，以及自动 ECB System 的所有权和生产者依赖登记。手动和自动实验的预期观察均得到学习者确认，随后确认没有剩余疑问。

助手侧做的是 Entities 1.5.0 API/源码与静态检查，没有在 Unity 中编译或进入 Play；运行证据来自学习者反馈。两份下载保留实际交付版本的原始字节与命名空间。

下一步回到 ECS 为什么快的底层问题：缓存里有多少数据真正被用到、预取怎样工作、内存带宽怎样限制计算，再联系 SIMD 与并行瓶颈。这部分开始探索，尚未完成；Enableable Component 的深入用法暂留后续。

## 官方资料与版本边界

本课以 Unity 官方发布的 [Entities 1.5.0 包](https://download.packages.unity.com/com.unity.entities/-/com.unity.entities-1.5.0.tgz)为 API/源码核对依据，版本元数据见 [Unity 包注册表](https://packages.unity.com/com.unity.entities)。重点文件为 `Unity.Entities/EntityCommandBuffer.cs`、`EntityCommandBufferSystem.cs` 及默认系统组实现。

在线补充阅读使用明确标注版本的 [ECB 概览（Entities 1.4）](https://docs.unity3d.com/Packages/com.unity.entities@1.4/manual/systems-entity-command-buffers.html)。阅读时区分包源码版本与网页版本，不把源码检查、学习者运行确认和性能测量混在一起。
