## 这一课做了什么，没做什么

前面的 [Query 实践](/2026/10/22/unity-ecs-query-practice/) 解决了筛选与读写。本课继续追问：普通循环为什么可能变成 SIMD？Job 是不是天然多线程？怎样安全地等待结果？

环境：Unity 6000.3.25f1、Entities 1.5.0、Burst 1.8.30。同一个学习项目中使用独立实验场景。这个数组实验不创建 ECS World，也不需要 SubScene、Baker 或 Entities Graphics。

**本次完成的是数值正确性实验、生成代码观察和概念理解，不是性能基准。**

| 证据 | 已经确认 | 不能据此推断 |
| --- | --- | --- |
| 原始 IJob + Run 的 Console | 1024 项结果正确 | 一定更快、运行时一定匹配 Inspector 配置 |
| 原始 IJob 的 Inspector 汇编 | 所选配置生成了 SIMD 与循环展开 | 使用多个线程、固定加速倍数、一定是 AVX2 |
| IJob + Schedule + Complete 的 Console | 改动后仍全部正确 | 内部 for 自动多线程、实际执行线程数 |
| IJobFor + ScheduleParallel + Complete 的 Console | 按索引调度后仍全部正确 | 已确认新版本 SIMD、一定比 Run 更快 |

## ECS、Burst、SIMD、Jobs 各自负责什么

- ECS 关注实体、组件、查询和数据组织，连续的数据布局有利于高效访问，但用了 ECS 不等于已经 SIMD 或多线程。
- Burst 把受支持的 C# 编译为优化后的原生 CPU 代码。SIMD 是可能采用的优化之一，不是全部。
- SIMD 是一条指令处理多个数据，单个线程也可以使用。
- Job System 负责安排任务与依赖。任务如何写、如何调度，决定它有没有机会分给多个工作线程。

开启 Burst 后变快，可能来自其他编译优化，不能只凭耗时下降就宣布发生了向量化。反过来，看到 SIMD 指令也不能保证整个程序更快：内存访问、工作量和调度成本都可能影响结果。

## 两段话概括：SIMD 是什么，Burst 为什么可能更快

**SIMD 是什么：** SIMD 是 Single Instruction, Multiple Data，即一条指令对多个数据执行同一种运算。本实验中的 vaddps ymm 一次处理 8 对 float 的加法，这是指令层面的数据并行，一个线程也能做到；它不等于多线程，也不能据此推导出整体快了 8 倍。

**Burst 为什么可能更快：** Burst 针对受支持的 C# 计算代码和目标 CPU 生成高效原生机器码，通过消除冗余计算、优化循环、循环展开，以及在条件允许时使用 SIMD 等方式减少不必要的工作或提升执行效率。它不是自动开启多线程，也不能简化成普通 C# 永远解释执行而 Burst 才是机器码。实际收益取决于代码、数据访问和硬件，需要测量。

## 实验起点：一个线程里的普通 for

下载 [BurstSimdProbe.cs 原始 Run 版本](/downloads/BurstSimdProbe.cs)。文件名保持不变，放进 Assets 中，在一个空场景对象上挂载 BurstSimdProbe，再运行 Play。每个版本是依次修改同一个文件，不要把三个同名类同时放入项目。

脚本创建三个独立的 NativeArray：A、B、Output。长度均为 1024，A[i] = i，B[i] = 2 × i，输出先填为 −1。计算目标是 Output[i] = A[i] + B[i]。

核心 Job 如下，输入只读，输出只写：

```csharp
[BurstCompile(CompileSynchronously = true)]
public struct AddArraysJob : IJob
{
    [ReadOnly] public NativeArray<float> A;
    [ReadOnly] public NativeArray<float> B;
    [WriteOnly] public NativeArray<float> Output;

    public void Execute()
    {
        for (int i = 0; i < Output.Length; i++)
            Output[i] = A[i] + B[i];
    }
}
```

在 MonoBehaviour.Start 中调用 job.Run()。Run 在调用线程同步执行；本例调用者是主线程，所以没有把循环拆给多个工作线程。不要把 Run 随意换成直接调用 Execute，后者只是普通 C# 方法调用，不能当作同一条验证路径。

计算完后，主线程逐项核对 output[i] == 3f × i，最后在 finally 中释放三个数组。这些小整数都能被 float 精确表示，因此本例可直接比较；这不是适用于所有浮点数计算的通用比较规则。

实际 Console 结果：

```text
[BurstSimdProbe] PASS: 1024/1024; first = 0, 3, 6, 9; last = 3069
```

这条日志说明数值正确。单凭它，既看不出 SIMD，也看不出速度提升。

## Inspector：找到真正的向量加法

从 Jobs → Burst → Open Inspector 打开窗口，选择 BurstSimdProbe 下的 AddArraysJob (IJob)，查看 Assembly。本次截图顶部为 **Safety Check Off、Target (Auto)**。以下结论只针对这组 Inspector 配置，不能直接当作 Play 模式采用完全相同设置的证明，也不建议为了追求向量化就关闭项目安全检查。

原始 IJob 的核心循环出现四条使用 ymm0～ymm3 的 vaddps，配合 vmovups 读写数据。四组内存偏移分别是 0、32、64、96 字节，循环每轮前进 128 字节。

为什么这是 SIMD 证据？

- vaddps 表示成组的单精度浮点加法。
- 这里的 ymm 寄存器宽 256 位，一个 float 是 32 位，所以一条这样的指令处理 8 对 float。
- 主体循环连续展开四组，每轮处理 4 × 8 = 32 个元素。
- 128 字节恰好对应 32 个 float。这说明 SIMD 与循环展开同时发生，并不是开启了 32 个线程。

**一条向量加法处理 8 项，不等于程序快了 8 倍；一轮处理 32 项，也不等于快了 32 倍。** vaddps ymm 本身属于 AVX 指令，不能仅凭它声称确认用了 AVX2。

截图中还有两个收尾路径：vaddps xmm 每次处理 4 项，vaddss 每次处理 1 项。它们用于不足主体批量的剩余元素，标量收尾与向量主体可以同时存在。

本次长度 1024 能被 32 整除，按截图代码路径，主体循环执行 32 轮后不需要尾部加法。课堂理解题把长度假设为 1025，最后一项会交给 vaddss；这是根据截图的推演，**没有实际运行 1025 项实验**。

## 什么叫加法指令

C# 的 + 是我们向编译器表达的操作，CPU 并不直接理解整段 C# 文字。编译器把程序转换成机器指令，完成取数、计算和写回等步骤。

加法指令就是其中要求 CPU 做加法的操作。vaddss、vaddps 是方便人阅读的指令名字，不是要在 C# 中调用的函数。二者都处理单精度浮点数，区别是标量与成组计算。

同一段逐项相加的源代码，可以被编译成逐对计算，也可以被改写成成组计算。机器指令不等于一行 C#，一条指令也不保证只花一个 CPU 时钟周期。仅看到 xmm 或 ymm 寄存器名字不够，还要结合具体运算和循环路径判断。

## 从 Run 到 Schedule：先分清调度与拆分

第二次实验只把原来的 job.Run() 替换为：

```csharp
JobHandle handle = job.Schedule();
handle.Complete();
```

其余初始化、核对、释放保持不变。实际 Console 再次得到相同 PASS。

Run 是现在就在调用线程做完；Schedule 是提交任务，由 Job System 安排执行，并返回 JobHandle，用来表达依赖和确保任务完成。提交不意味着立即启动，也不意味着返回时已经完成。

**IJob.Schedule 不会自动把 Execute 内的 for 拆到多个线程。** Execute 仍是一整项工作，在一个执行它的线程上调用一次。它可以与主线程上的其他独立工作重叠，但不能只凭 Schedule 认定本次必定由某个工作线程执行。

Complete 不是取消任务，也不是只把完成标志设为真。它确保该 Job 及其依赖完成，并完成必要的安全状态处理，之后主线程才能安全访问相关数据；尚未完成时需要等待，调用线程也可能参与执行相关工作。

正确顺序是：提交任务，做不依赖结果且不冲突访问数组的其他工作，需要结果时 Complete，然后读取结果，最后释放数组。安全检查开启时，过早冲突访问通常会被检测并报错，而不是任由读取不完整结果。即使观察到 IsCompleted 为真，也不能用它替代 Complete 的安全处理。

本实验故意紧接着 Complete，目的是练习正确顺序，不是提速。主线程中间没有安排其他工作，就几乎没有利用重叠执行的机会。

## 从 IJob 到 IJobFor：改变工作单位

第三次实验才开始把循环迭代交给系统调度。将 AddArraysJob 的接口由 IJob 改为 IJobFor，把原来的 Execute 和内部 for 整段替换为：

```csharp
public void Execute(int index)
{
    Output[index] = A[index] + B[index];
}
```

每次 Execute(index) 只负责一个索引，不再自己遍历全部数组。Start 中的调度改为：

```csharp
JobHandle handle = job.ScheduleParallel(output.Length, 64, default);
handle.Complete();
```

这里 output 是 Start 中的小写局部变量。其他字段、属性、结果核对和 Dispose 保持不变。

- output.Length 是迭代总数，本例为 1024。
- 64 是批次粒度，不是线程数、SIMD 宽度，也不保证固定分成某个数量的任务。这里只选作练习起点，没有测量最优值。
- default 表示没有指定需要先等待的前置 Job。

系统可以将不同索引分批分配给工作线程，不是每个索引新建一个线程。执行顺序没有保证，但输出位置由 index 决定：即使 100 比 5 先执行，它仍然写 Output[100]，不会和 Output[5] 交换位置。

实际 Console 第三次仍然输出：

```text
[BurstSimdProbe] PASS: 1024/1024; first = 0, 3, 6, 9; last = 3069
```

这次只核对了结果，**没有重新查看 IJobFor 的 Inspector**。旧 IJob 截图不能当作新版本已经 SIMD 的证据；也没有通过 Profiler 测量实际线程数或性能。

## 为什么可以并行，什么时候不能照搬

本例计算 Output[5] 只依赖 A[5]、B[5]，不需要先算出 Output[4]。输入数组只读，各次执行写入不同的输出位置，三个数组独立分配，所以适合按索引并行处理。

SIMD 与多线程发生在不同层面：多个线程可以各自负责一段工作，每个线程内部又可能使用 SIMD。四份、八份等分法只是理解模型，不能据此断言调度器实际采用固定线程数量。

如果把每次写各自的 Output[index] 改成向同一个共享 total 累加，原来的独立性就没有了。普通累加包含读取、计算、写回，不可假设整个过程不会被其他线程穿插。

例如 total 初始为 0：A 读到 0 准备加 1，B 也读到 0 准备加 2；A 写回 1 后 B 写回 2，最后可能得到 2 而不是 3。这是共享读改写的数据竞争示意，不是在本实验中执行过的代码。

但正确结论不是求和绝对不能并行。可以让各部分分别得到小计，再把小计合并，这叫归约。同步或合适的原子操作也是其他方向，但会有支持范围和额外开销。浮点归约改变加法分组时还可能改变舍入结果，不能默认与原来的串行顺序逐位一致。

## 本课结论与下一步

三条执行路径都完成了数值核对；原始 IJob 的所选 Inspector 配置展示了自动向量化和循环展开。理解检查也覆盖了指令、尾部处理、同步顺序、按索引独立性以及数据竞争。

尚未验证的项目保持明确：性能收益、实际线程分布、IJobFor 的向量化，以及 Inspector 与运行时的配置一致性。不能把三个 PASS 写成三次性能测量。

后续准备继续学习 Burst 的编译优化原理与多个 Job 的依赖衔接；基础实验完成不意味着所有 Burst 原理已经学完。本课提到 JobHandle 的依赖用途，但还没有实际构建多阶段任务链。

## 官方资料

- [Burst 1.8 文档入口](https://docs.unity3d.com/Packages/com.unity.burst@1.8/manual/index.html)
- [循环向量化与优化](https://docs.unity3d.com/Packages/com.unity.burst@1.8/manual/optimization-loop-vectorization.html)
- [Burst Inspector](https://docs.unity3d.com/Packages/com.unity.burst@1.8/manual/editor-burst-inspector.html)
- [IJobExtensions.Run](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Unity.Jobs.IJobExtensions.Run.html)
- [创建和运行 Job](https://docs.unity3d.com/6000.3/Documentation/Manual/job-system-creating-jobs.html)
- [JobHandle.Complete](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Unity.Jobs.JobHandle.Complete.html)
- [IJobFor](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Unity.Jobs.IJobFor.html)
- [IJobForExtensions.ScheduleParallel](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Unity.Jobs.IJobForExtensions.ScheduleParallel.html)

文档的 1.8 链接可能显示该系列更新的补丁版本，本实验安装版本仍按实际确认的 1.8.30 记录。
