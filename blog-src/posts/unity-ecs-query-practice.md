---
title: "Unity ECS 学习笔记 03：用四个实体验证 Query 筛选与读写"
date: "2026-10-22"
categories:
  - Unity
tags:
  - ECS
  - Query
  - ISystem
  - 组件读写
---

前面理解了 Query 怎样按组件组合筛选实体，这一节把概念变成一个可以重复运行的小实验：创建 A、B、C、D 四个实体，预测哪些位置会更新，再用 Console 核对结果。

> 本次使用 Unity 6000.3.25f1、Entities 1.5.0。下文两组日志来自我实际运行后的 Console 输出；后面的两个理解检查只是推演，不是额外的运行结果。本实验不包含性能测试，也没有验证 Jobs、Burst 或 SIMD 的效果。

## 1. 实验只关心数据，不需要场景里的物体

[下载完整实验脚本 EcsQueryPractice.cs](/downloads/EcsQueryPractice.cs)。把文件放进 Assets/Scripts，避免放入 Editor 文件夹，等待编译完成后进入 Play，在 Console 查看结果。

脚本使用默认 World 中的 ISystem，不需要挂到 GameObject 上，也不需要 SubScene、Baker 或 Entities Graphics。这里的 Position 是自己定义的一维数值，不是 Transform 或 LocalTransform，所以场景里没有物体移动是正常的。

四个实体的初始 Position 都是 0，组件组合如下：

| 实体 | 组件组合 | Velocity.Value |
| --- | --- | --- |
| A | Position、Velocity | 1 |
| B | Position、Velocity、Health | 2 |
| C | Position | 没有 Velocity 组件 |
| D | Position、Velocity、Frozen | 3 |

Health 是额外的普通数据组件。Frozen 是普通空标签，表示“有这个组件”，不是 IEnableableComponent。四种组合对应四种 Archetype，但这个实验不要求手工安排 Chunk。

## 2. 先分清类型、实体和组件值

```csharp
public struct Position : IComponentData
{
    public float Value;
}
```

这只是定义 Position 组件的数据格式，并没有创建实体。Value 是我给字段起的名字，不是 ECS 保留的特殊字段。

```csharp
private Entity _a;

_a = em.CreateEntity(typeof(Position), typeof(Velocity));
em.SetComponentData(_a, new Velocity { Value = 1f });
```

这三处各有职责：

- Entity 字段保存实体句柄，方便之后找到 A；它不是 A 的全部组件数据，也不是 A 在 Chunk 里的数组下标。
- CreateEntity 创建实体，参数指定它具有哪些组件类型。typeof(Velocity) 表示类型，不表示速度值。
- SetComponentData 把值写入已有的 Velocity 组件，不会创建另一个实体，也不是给实体添加缺失的组件。

new Velocity 在这里构造的是结构体值，不能看到 new 就把它理解成“创建了一个托管类对象”。实体和组件的存储由 ECS 管理，不需要在这个实验里自己给 A、B、C、D 分配数组位置。相关 API 可查阅 [EntityManager 文档](https://docs.unity3d.com/Packages/com.unity.entities@1.5/api/Unity.Entities.EntityManager.html)。

## 3. 第一次运行：要求 Position 和 Velocity，排除 Frozen

核心循环如下：

```csharp
const float deltaTime = 1f;
int matchedCount = 0;

foreach (var (position, velocity) in
         SystemAPI.Query<RefRW<Position>, RefRO<Velocity>>()
             .WithNone<Frozen>())
{
    position.ValueRW.Value += velocity.ValueRO.Value * deltaTime;
    matchedCount++;
}
```

本例的匹配条件是：同时具有 Position 和 Velocity，并且没有 Frozen。

A 满足条件；B 虽然额外带着 Health，也满足条件。C 缺少 Velocity；D 则因为带有 Frozen 被排除。Query 不是要求组件组合与 A 完全相同，额外组件只有在被明确用于筛选时才影响这里的匹配。

deltaTime 固定为 1，表示这一步按一个模拟秒计算，不是在等待一秒，也没有修改 Unity 的时间设置。

实际输出：

```text
[Query实验] 执行前：A=0，B=0，C=0，D=0
[Query实验] 本次匹配数量：2
[Query实验] 执行后：A=1，B=2，C=0，D=0
```

这验证了本例的筛选和修改结果。日志按保存的实体句柄打印 A、B、C、D，不代表 Query 保证按这个顺序遍历。

## 4. 第二次运行：只移除 WithNone 条件

退出 Play 后，只去掉 .WithNone<Frozen>()，保留 foreach 本身的右括号。D 仍然拥有 Frozen，不删除它的组件，也不修改速度。

修改后的循环开头是：

```csharp
foreach (var (position, velocity) in
         SystemAPI.Query<RefRW<Position>, RefRO<Velocity>>())
```

我先预测：匹配数量是 3，结果为 A=1、B=2、C=0、D=3。

再次进入 Play，实际输出是：

```text
[Query实验] 执行前：A=0，B=0，C=0，D=0
[Query实验] 本次匹配数量：3
[Query实验] 执行后：A=1，B=2，C=0，D=3
```

预测和结果一致。Frozen 不会因为名字叫“冻结”就自动阻止位置更新；是原先的 WithNone 条件把 D 排除。移除条件后，D 与 A、B 一样满足 Position 和 Velocity 的要求。C 仍然不匹配。

下载文件保留第一次运行的基线版本，方便从头复现实验；第二次实验需要手动做上面这一处修改。

## 5. ValueRW、ValueRO 和最后一个 Value

```csharp
position.ValueRW.Value += velocity.ValueRO.Value * deltaTime;
```

把这一行拆开就不容易混淆了：

- position 是当前实体的 Position 访问包装，使用 RefRW，允许读写。
- position.ValueRW 取得可写的组件引用；最后的 .Value 才是自定义 float 字段。
- velocity 使用 RefRO，通过 ValueRO 读取组件，不通过它修改 Velocity。

因此，这一行会修改实体实际保存的 Position。循环中的 position 和 velocity 来自当前同一个匹配实体，不是分别随便取出的两个组件。SystemAPI.Query 的使用方式和访问声明见 [Unity 官方说明](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/systems-systemapi-query.html)。

### 理解检查一：有速度组件，但速度值为零

如果创建 A 时仍然包含 Velocity，只是不再把它的 Value 设置成 1，它的默认 float 值为 0，那么 A 仍会匹配，位置却不变。

我的回答是：“会，但是位置不变。”

这里要区分两件事：本例 Query 检查组件是否存在；计算结果取决于组件里的值。“没有 Velocity”和“Velocity.Value 等于零”不是同一个状态。

### 理解检查二：普通变量接到的是副本

```csharp
var p = position.ValueRO;
p.Value += 10;
```

在这个写法里，没有使用 ref 接收引用，也没有把 p 写回组件。p 是 Position 结构体的值副本，修改它不会让实体原本的位置增加。

我的回答是：“不会增加。”

这不意味着读取 ValueRO 总会复制；关键是这里用普通的 var 赋值，而不是引用局部变量。结构体默认赋值的值语义可参考 [Microsoft 的结构体说明](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/builtin-types/struct)。这两个问题都属于理解检查，没有记录为第三次或第四次运行。

## 6. 这段系统为什么只执行一次？

脚本把准备、更新和收尾分开：

- OnCreate：系统创建时初始化四个实体及其数据，不是每帧重复创建。
- OnUpdate：打印执行前位置，遍历 Query 更新组件，再打印匹配数量和执行后位置。
- state.Enabled = false：关闭本系统后续的更新，避免每帧刷日志；并没有删除实体或关闭某个 Frozen 组件。
- OnDestroy：本例没有手工分配的 Native 容器需要释放。默认 World 销毁时会清理其中的实体。

重新退出并进入 Play，可以重新建立初始状态。上述流程针对本实验使用的默认 World；如果改变了 World 的创建和销毁方式，需要相应检查生命周期。可参考 [ISystem 生命周期](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/systems-isystem.html)、[SystemState](https://docs.unity3d.com/Packages/com.unity.entities@1.5/api/Unity.Entities.SystemState.html) 和 [World 概念](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/concepts-worlds.html)。

## 7. 这一节真正完成了什么？

完成了两次真实运行，验证“组件存在条件决定本例的匹配范围”，也把组件定义、创建实体、写入数值、引用访问和普通结构体副本串在了一起。

本次循环只改变 Position 的字段，没有添加或删除组件，因此不会因为这行位置更新而改变实体的 Archetype。至于这种布局怎样帮助计算、Burst 能否向量化、Job System 怎样安排并行工作，还需要后面的独立学习和实验，不能从这两组日志直接推出性能结论。

## 后续补充：只让实验在指定场景运行

完成 Query 后，在同一个项目继续学习 Burst 时，遇到了实验 System 会在其他场景运行的问题。System 属于 World，不天然属于某一个普通 Scene；默认初始化自动创建的系统，不会因为源文件放在某个场景相关文件夹就受该场景限制。

本课采用显式隔离方案：[下载场景限定版 EcsQueryPractice.cs](/downloads/EcsQueryPractice.SceneScoped.cs)。下载后将文件重命名为 EcsQueryPractice.cs，再完整替换旧文件，不要同时保留两份同名定义。只在 Query 课的场景空对象上挂载 EcsQueryPractice，保存场景后运行。

该版本给实验 ISystem 添加 DisableAutoCreation，避免自动加入默认 World。场景中的 MonoBehaviour 在 Start 创建专用 World，创建实验系统并手动更新一次；不注册到 PlayerLoop，也不修改默认 World。对象销毁时释放整个实验 World，初始化失败也会释放。

此补充保留的是去掉 WithNone 的第二次实验条件，因此匹配 3 个，结果是 A=1、B=2、C=0、D=3。前文原始基线下载仍保留，用于复现最初匹配 2 个的对照，不应混为同一个版本。

限定版已在课堂得到使用者确认可用。这种生命周期跟随挂载对象存在与销毁，而不是每次改变 Active Scene 都重跑；采用叠加加载时，原场景对象未销毁，不能假定切换活动场景就卸载了它。也不要给这个实验对象设置 DontDestroyOnLoad。

参考：[World 概念](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/concepts-worlds.html)、[DisableAutoCreation](https://docs.unity3d.com/Packages/com.unity.entities@1.5/api/Unity.Entities.DisableAutoCreationAttribute.html)。
