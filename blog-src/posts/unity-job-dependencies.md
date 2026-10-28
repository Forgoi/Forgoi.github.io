## 从单个 Job 到一组有先后关系的工作

[上一课](/2026/10/24/unity-burst-simd-jobs/) 跑通了 Run、Schedule 和 ScheduleParallel。这次继续解决一个实际问题：后一个任务需要前一个任务的结果时，怎样安排它们，又不让主线程在每个中间步骤都等待？

本课在独立空场景中运行 JobDependencyProbe，使用普通 Job 与数组，不创建 ECS 实体。10 月 27 日得到实际 Console 的 PASS 8/8，并完成依赖概念的理解检查。**这是正确性实验，不是性能基准。** 下文代码是突出依赖关系的核心片段，省略 Job 定义、数组初始化和释放，不能单独作为完整脚本运行。

## 链式依赖：把完成条件交给后一个任务

假设 A 把原始速度乘以 2，B 读取新速度来更新位置。B 必须等 A 完成。提交 A 后先调用 Complete，再提交 B，虽然能保证顺序，却让主线程在中间等待。

可以把 A 返回的 JobHandle 交给 B：

```csharp
JobHandle handleA = jobA.Schedule(); // 提交 A，取得代表这项工作的句柄。
JobHandle handleB = jobB.Schedule(handleA); // 提交 B，并要求它等 A 完成后才执行。
handleB.Complete(); // 主线程需要结果时，确保 B 及其前置 A 都完成。
```

第二行执行时，A 不必已经完成。B 可以先被提交，由 Job System 根据依赖安排开始时间。仅仅把两次 Schedule 写成先后两行，并没有表达数据依赖；传入的 handleA 才是这里的关键。[Unity 6.3：Job dependencies](https://docs.unity3d.com/6000.3/Documentation/Manual/job-system-job-dependencies.html)

## 独立任务不必陪着等待

如果 C 处理完全独立的数据，不读取 A 的结果，也不与 A 发生冲突读写，就不需要为了正确性而等待 A。额外添加依赖会限制它们重叠执行的机会。

另一个容易忽略的范围问题是：在 A → B 这条链之外，独立提交的 C 不属于 B 的依赖。调用 handleB.Complete() 后，C 可能完成，也可能没完成，不能从这个调用推出 C 已经结束。

课堂中先后确认了两点：独立 C 不需要等待 A；完成 B 不能保证独立 C 完成。这些是概念判断，不能替代执行时间线测量。

## 多个前置条件：A 和 C 都完成，D 才能开始

这次实验采用两条独立分支再汇合的关系：A 计算速度，C 生成方向，D 同时读取两者计算位移。

```text
A：速度翻倍 ──┐
              ├── D：速度 × 方向 × 时间
C：生成方向 ──┘
```

调用 CombineDependencies，将两个句柄合成一个完成条件，再传给 D：

```csharp
JobHandle handleA = jobA.Schedule(); // A 没有本例中的前置任务。
JobHandle handleC = jobC.Schedule(); // C 独立提交，不要求先完成 A。
JobHandle ready = JobHandle.CombineDependencies(handleA, handleC); // 同时包含 A、C 的完成条件。
JobHandle handleD = jobD.Schedule(ready); // D 只有在 A、C 都完成后才可以执行。
handleD.Complete(); // 主线程准备读取结果，确保整条依赖关系已经完成。
```

CombineDependencies 本身不让主线程等待，不把 A、C 的计算合成一个 Job，也不强制它们按 A 后 C 的顺序执行。它让 D 的一个依赖参数表达多个前置条件。即使 A 已完成，只要 C 未完成，D 就不能开始。[Unity 6.3：CombineDependencies API](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Unity.Jobs.JobHandle.CombineDependencies.html)

## 八项位移实验与实际输出

JobDependencyProbe.cs 挂载在新建空场景的空 GameObject 上，不修改上一课的脚本。数据量只有 8 项，方便逐项核对。

| 阶段 | 输入或计算 | 结果 |
| --- | --- | --- |
| 初始数据 | 原始速度 1～8 | 1, 2, 3, 4, 5, 6, 7, 8 |
| A | 原始速度乘以 2 | 2, 4, 6, 8, 10, 12, 14, 16 |
| C | 独立生成交替方向 | +1, −1, +1, −1, +1, −1, +1, −1 |
| D | 速度 × 方向 × 时间，时间为 1 | 2, −4, 6, −8, 10, −12, 14, −16 |

主线程在最终任务完成后读取并检查结果。10 月 27 日实际运行输出如下：

```text
[JobDependencyProbe] PASS: 8/8; displacement = 2, -4, 6, -8, 10, -12, 14, -16
```

8 项数值全部符合预期。这说明本次运行的位移结果正确；依赖写法通过 API 语义和代码结构来理解。单次 PASS 本身不能证明所有调度时序下都没有竞争，也不能代替对读写关系的检查。

## Complete 的位置与证据边界

这里没有在 A 与 C 之间插入 Complete，而是在主线程需要 D 的结果时完成最终句柄。D 的前置条件覆盖了 A、C，因此最终完成会同时满足它们的完成要求。调用 Complete 的线程还可能参与执行工作，不能把它简单理解为只在原地等待。[Unity 6.3：Complete API](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Unity.Jobs.JobHandle.Complete.html)

| 本次证据 | 可以说明 | 不能说明 |
| --- | --- | --- |
| 核心调度关系 | A、C 独立，D 依赖两者 | A、C 在这次运行中一定同时执行 |
| PASS 8/8 | 八项结果与预期一致 | 更快、使用了几个线程、固定加速倍数 |
| 最终句柄完成后读数 | 本例的读取位置与依赖范围相匹配 | 所有其他独立任务也已完成 |

本次没有 Profiler 时间线，也没有耗时对照。8 项数据是为理解关系而选的，不适合凭一次运行评价调度收益。最终立即 Complete 也没有为主线程安排额外的独立工作。

## 这一课留下的三个抓手

- Schedule(前置句柄)：提交任务，并声明开始前需要满足什么条件。
- CombineDependencies：把多个完成条件汇成一个，供后续任务使用。
- Complete：需要结果时确保相关任务与依赖完成，再访问数据。

接下来计划回到 ECS，学习 System 怎样通过 Dependency 衔接组件读写任务。这部分尚未完成，不计入本课实验结论。
