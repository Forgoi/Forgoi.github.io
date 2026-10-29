## 这次把依赖放进 ECS

[上一课](/2026/10/27/unity-job-dependencies/) 用 JobHandle 手动连接普通 Job。本课把相同问题放进 ECS：加速系统先修改 Velocity，移动系统再读取新速度更新 Position，最后由主线程核对结果。

本次使用独立实验脚本，目标环境为 Unity 6000.3.25f1、Entities 1.5.0、Burst 1.8.30。**实验只有一个实体，并且只运行一轮；验证的是依赖与数值正确性，不是多线程加速。** 10 月 29 日运行后，确认输出与预期的 START、PASS 两行一致，随后完成代码讲解和更新频率的澄清。

## 先分清 SystemState、state 和 Dependency

```csharp
public void OnUpdate(ref SystemState state)
```

- SystemState 是类型，承载当前非托管 System 的状态及相关访问入口。
- state 是这个参数的名字；ECS 调用 OnUpdate 时传入对应 System 的状态，不需要自己 new 一个来替代。
- ref 表示通过引用访问传入的状态，而不是只处理一个普通副本。
- state.Dependency 是状态上的 JobHandle 属性，用来衔接该 System 的 ECS 相关工作依赖。

state 不是线程，Dependency 也不是整个 System。可以通过 state.EntityManager 访问实体管理器，用 state.RequireForUpdate 设置更新条件；Dependency 只是其中负责 Job 依赖的一部分。不同 System 各有自己的状态，不能把两个系统的 state.Dependency 理解成同一个全局变量。

## 一行代码里的输入与输出

加速系统使用的核心语句如下：

```csharp
state.Dependency = new AccelerateJob { DeltaTime = 1f }
    .ScheduleParallel(state.Dependency);
```

按操作顺序拆开看：右侧读取当前相关的前置依赖，把它传入调度；ScheduleParallel 提交当前工作并返回新的 JobHandle；左侧赋值把新句柄登记回当前 System，供后续相关工作衔接。

这里使用的是**显式传入依赖、返回句柄的重载**。这一类调用需要正确保存并登记输出依赖，不能据此断言所有隐式调度重载都要求写同样的赋值。

学习中曾把丢弃返回值理解成句柄失效。更准确的理解是：Job 已经提交，不会因为没有保存返回值就取消；输入依赖也仍然约束它。问题在于 System 的 Dependency 没有被更新为这次新工作，后续 System 无法通过这个旧值正确衔接它，可能出现依赖检查错误或冲突读写。只把返回值放进局部变量，也不等于自动登记到了 System。

以上机制已结合官方 Entities 1.5.0 包中的 SystemState.cs 与 IJobEntity.cs 核对。文末列出包来源；在线的 [Entities 1.4 依赖文档](https://docs.unity3d.com/Packages/com.unity.entities@1.4/manual/scheduling-jobs-dependencies.html) 可作概念补充，但不冒充 1.5 的实跑验证。

## ref 与 in：先声明读写，再建立依赖

两个 Job 的 Execute 参数分别为：

```csharp
private void Execute(ref Velocity velocity)
```

```csharp
private void Execute(ref Position position, in Velocity velocity)
```

前者声明对 Velocity 的读写访问；后者声明对 Position 读写、对 Velocity 只读。在这份 IJobEntity 代码中，这些声明会参与查询和组件访问注册，使 ECS 能结合 System 更新顺序与已登记的句柄管理依赖。

因此，ref/in 直接提供的是**访问模式**，不是手写的一条依赖边。即便某次 Execute 恰好没有修改数值，ref 声明仍是读写访问，不能按那次结果临时当成只读。

本例 A 写 Velocity，后面的 B 读 Velocity，需要 B 等 A。两个任务若都只读同一组件且没有其他冲突，仅仅共享读取不会造成这种写入冲突。这里的组件依赖管理也不自动覆盖任意共享 NativeArray；那类数据关系仍需正确管理。

## System 的调用顺序，不等于 Job 已完成

三个系统都属于 SimulationSystemGroup。MovementSystem 使用 UpdateAfter 指定在 AccelerationSystem 之后更新，VerifySystem 则在 MovementSystem 之后。

它们控制同一组里的调用顺序：先运行加速系统的 OnUpdate，提交 A；再运行移动系统的 OnUpdate，提交 B。加速系统返回时，A 可能仍在执行。**真正让 B 的计算等待 A 的，是正确传入的依赖句柄。**

这解释了为何不必在每个 System 的 OnUpdate 末尾立刻 Complete：主线程可以继续提交后续工作，而 Job 按依赖条件执行。它也解释了另一个边界：后一个 System 开始更新，不足以证明前一个 Job 已结束。

## 一个实体、两个 Job、一次核对

下载完整的 [DependencyExperimentBootstrap.cs](/downloads/DependencyExperimentBootstrap.cs)。保留文件名，放在 Assets 下而非 Editor 文件夹；新建空场景，在一个空 GameObject 上只挂载 DependencyExperimentBootstrap。三个 ISystem 会由 ECS 发现，不挂到 GameObject；不需要 SubScene。使用默认 Play Mode 重载设置，并且只保留一个 Bootstrap。

此下载保持课堂交付原文件的字节内容。文件顶部的未实跑说明记录的是交付前的助手验证状态；后来学习者确认运行成功，记录在本文中，不改写成助手曾执行 Unity。

| 阶段 | 行为 | 本例数值 |
| --- | --- | --- |
| Bootstrap | 创建带 Position、Velocity、RunOnce 的实体 | Position=0，Velocity=1 |
| AccelerateJob | 加速度 1，计算步长 dt=1 | Velocity 变为 2 |
| MoveJob | 等待相关依赖，用新速度更新位置 | Position 变为 2 |
| VerifySystem | 完成相关写入后，在主线程读数核对 | Velocity=2，Position=2 |

课堂给出的两行预期如下，运行后学习者确认结果一致，而非另外粘贴了一份完整 Console 转录：

```text
[DependencyExperiment] START | Velocity=1, Position=0 (dt=1)
[DependencyExperiment] PASS | Velocity=2, Position=2 (dt=1)
```

dt=1 是显式计算的模拟步长，不是现实中等待一秒。0、1、2 能被 float 精确表示，所以本例直接比较预期值；这不是所有浮点运算都应直接比较的通用建议。

## 为什么主线程核对前还要完成依赖

VerifySystem 的核心顺序是：

```csharp
em.CompleteDependencyBeforeRO<Position>(); // 为只读 Position 完成相关写入依赖。
em.CompleteDependencyBeforeRO<Velocity>(); // 为只读 Velocity 完成相关写入依赖。
float position = em.GetComponentData<Position>(entity).Value;
float velocity = em.GetComponentData<Velocity>(entity).Value;
```

后续 Job 可以携带依赖后排队，主线程此刻却要立刻读取数值，必须先确保相关写入完成。这个检查系统前面只通过 RunOnce 查询实体，不能假定它自己的 Dependency 已经自动涵盖 A、B 对 Position 和 Velocity 的所有工作。这里按组件类型明确完成只读所需的写入依赖，避免把 UpdateAfter 误当同步屏障。

两次调用用于把本例读数的要求写清楚，并不表示任何程序都应该无条件逐项 Complete。正常系统应按实际访问需要同步，避免无必要地阻断可并行的工作。

## RunOnce 为什么让实验只做一轮

Bootstrap 创建 RunOnce 标签，三个系统都调用 RequireForUpdate<RunOnce>()，两个 Job 也以 WithAll(RunOnce) 筛选实验实体。核对完毕后，VerifySystem 删除这个标签。

下一次更新机会到来时，更新条件不再满足，于是这些系统不再为本实验提交工作。删除的是 RunOnce，而不是实体本身；Position 和 Velocity 的结果仍然保留。最后场景对象销毁时，Bootstrap 只清理自己创建的实体，不销毁共享 World。

这是一套教学用的一轮开关。它不是普通持续移动系统每帧调度的示例，更没有测试大量实体。

## 一帧一次调用，不是只能计算一次

这一部分最容易把四件事混在一起：System 被调用多少次、提交了多少项 Job、一项 Job 处理多少工作、模拟推进了多少时间。

在本例默认 SimulationSystemGroup 设置下，符合更新条件的系统通常每个游戏帧有一次更新机会；组的安排决定调用节奏，OnUpdate 并不是自己永不返回的后台循环。主线程一直停留在无限循环里，后续系统和其他帧工作就无法正常推进。

但 System 并非在所有设置下都严格一帧一次。FixedStepSimulationSystemGroup 会按固定模拟步长追赶时间，一帧中可能更新零次、一次或多次。这属于概念解释，**本课没有额外运行固定组实验**。[FixedStepSimulationSystemGroup 文档（1.4）](https://docs.unity3d.com/Packages/com.unity.entities@1.4/api/Unity.Entities.FixedStepSimulationSystemGroup.html)；对应机制也核对了官方 1.5.0 包的组更新实现。

Job 同样没有每帧只能算一次的限制：一次 ScheduleParallel 可以处理很多符合查询的实体，一个 OnUpdate 也可以提交多个 Job。工作量不等于提交次数；已完成的 Job 不会自动重复执行，需要新的调度。主线程提交速度、过早 Complete 和依赖链仍可能形成瓶颈，多线程并不会让游戏完全摆脱主线程限制。

还有模拟时间的区别：速度 2、dt=0.02 时，一步位移是 0.04。把同一个 0.02 重复计算 100 次，会推进 2 秒模拟时间，位移变成 4；若只是把原来的 0.02 秒细分成 100 个子步，每步应是 0.0002 秒。这只是数值推演，不是新增运行结果。

## 本课证据与下一站

已完成的是单实体一轮实验、预期结果确认，以及 System 状态、组件访问、输入输出依赖、主线程读取和更新节奏的讲解。没有测量线程数量、实际执行重叠、吞吐量或加速倍数。助手侧做了 API/source 检查与静态验证，没有运行 Unity 编译或 Play Mode；学习者的成功运行是另一类证据。

下一课开始探索 EntityCommandBuffer（ECB）与结构变化，只标为正在学习，不提前点亮为完成。

资料核对以 [官方 Entities 注册表](https://packages.unity.com/com.unity.entities) 中的 1.5.0 包为准。相关实现位于 SystemState.cs、IJobEntity.cs、EntityManager.cs、ComponentSystemGroup.cs 和 DefaultWorld.cs；包内也包含 scheduling-jobs-dependencies 文档。结合具体版本阅读，避免把概念说明、源代码检查和实际运行混为一谈。
