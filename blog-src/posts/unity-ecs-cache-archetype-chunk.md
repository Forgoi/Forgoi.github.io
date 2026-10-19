---
title: "Unity ECS 学习笔记 01：从缓存局部性到 Chunk 迁移"
date: "2026-10-19"
categories:
  - Unity
tags:
  - ECS
  - 数据布局
  - Archetype
  - Chunk
---

学完固定时间步和插值后，这次开始追问另一个问题：**ECS 到底为什么可能更快？**

这一节先沿着“CPU 怎样取数据 → 数据怎样排列 → Archetype 与 Chunk 怎样组织实体 → 改变组件组合为什么有成本”往下走。暂时不展开 Query、Burst / SIMD 和 Job System。

> 本篇记录的是概念阅读、示意推演和理解检查，没有运行 ECS 示例或性能基准。Unity 编辑器版本是 6000.3.25f1；阅读参考为 Entities 1.5 文档，这不代表已经在项目中安装了该包版本。文中的数组与数字都用于解释布局，不是实测结果。

## 1. 访问一个字段，会把整个对象都搬进缓存吗？

最开始，我把这个过程想成了“访问对象里的位置，就把整个对象加载进来”。继续拆开以后，才发现要区分语言里的对象和硬件里的缓存行。

CPU 执行一次字段读取，并不是以 C# 对象边界作为缓存搬运边界。需要从下一层存储填充缓存时，通常涉及的是包含该地址的**缓存行（cache line）**。如果数据已经在缓存中，也不需要每次都重新从主存取一遍。

所以，一个对象里的其他字段可能恰好跟位置落在同一条缓存行里，一起进入缓存；较大的对象也可能横跨多条缓存行。不能简单说“访问一个字段，就把整个对象都加载了”。Intel 的[循环优化资料](https://www.intel.com/content/www/us/en/developer/articles/technical/loop-optimizations-where-blocks-are-required.html)可以作为理解缓存行与数据访问方式的参考。

### 一个只用于理解的 64 B / 16 B 示例

先规定示意模型的条件：

- 假设缓存行大小为 64 字节。
- 假设每条位置记录占一个 16 字节的槽。
- 假设数组起点按缓存行边界对齐，记录连续排列。
- 当前任务只遍历位置，不使用生命值、装备等其他数据。

那么，一条 64 字节缓存行可以容纳 4 个这样的槽：

```text
一条假设的缓存行：64 B
[Position A:16 B][Position B:16 B][Position C:16 B][Position D:16 B]
```

这个例子里，刚取到的一条缓存行，后续几次位置访问就有机会继续利用。相反，如果位置夹在每个实体的很多其他字段之间，同一条缓存行中可能只有一部分数据是这次任务需要的。

这里的 **16 B 是人为设定的槽大小，不是在说 Unity 的 float3 就是 16 B**。实际类型大小、字段布局、对齐方式以及硬件缓存行大小，需要分别确认。

这个例子也不能直接换算成“性能提高 4 倍”。缓存命中、预取、内存带宽、计算量和实际访问顺序都会影响结果。本节只建立一个判断方向：一次带进来的数据，接下来能用上多少？

## 2. 数组连续，是否就代表数据一定紧凑？

继续想这个问题时，需要区分“数组元素是什么”。

如果数组元素是引用类型，连续的是引用槽位；这些引用指向的对象，并不保证也按同样顺序紧挨着排列。访问对象字段时，还需要沿引用找到对象。

如果 `Position` 是一个结构体，那么 `Position[]` 中的元素值直接内联在数组元素区域。这里不能再简化成“class 都在堆、struct 都在栈”：引用类型实例通常由托管堆管理，而结构体的存储位置要看它所在的上下文；结构体数组本身通常也是托管堆对象。Microsoft 的[class 与 struct 设计说明](https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/choosing-between-class-and-struct)明确区分了引用数组和内联值类型数组。

```text
引用类型数组：
[引用 A][引用 B][引用 C]  →  各自指向对象

结构体数组 Position[]：
[位置 A][位置 B][位置 C]  →  元素值内联排列
```

不过，“内联且连续”也没有结束讨论。

假如数组元素是一个大结构体，里面混着位置、生命值和许多其他字段，而当前循环只处理位置，那么数组虽然连续，位置之间仍隔着当前用不到的数据。理解局部性时，既要看对象是否分散，也要看**这一轮任务真正读取的字段是否集中**。

### AoS 与 SoA：先看任务，再看布局

用同一组数据做一个布局示意：

```text
AoS：Array of Structures，结构体数组
[Position A, Health A][Position B, Health B][Position C, Health C]

SoA：Structure of Arrays，按字段或数据类别组织数组
Position: [A][B][C]
Health:   [A][B][C]
```

如果任务只更新位置，第二种布局可以集中遍历位置数组，减少夹带其他字段的情况。如果任务每次都需要同一个实体的多个字段，取舍又会变化。

因此，AoS 和 SoA 不是脱离访问方式就能排出胜负的两种标签。普通程序里的数组同样可以利用连续访问和局部性；这些收益并不是 ECS 独占的能力。

## 3. Archetype 按什么给实体分组？

在 Unity ECS 里，理解布局之前，先看实体有哪些组件类型。

假设两个实体都具有 `Position` 和 `Health`：

| 实体 | 组件类型集合 | Health 的值 |
| --- | --- | ---: |
| A | Position、Health | 100 |
| B | Position、Health | 80 |
| C | Position、Health、Armor | 100 |

A 和 B 的生命值不同，但它们的组件类型集合相同，因此属于同一个 Archetype。C 多了 `Armor`，属于另一种 Archetype。

可以把这里的判断记成：**看“有哪些组件类型”，而不是看“组件里现在装着什么值”。** 组件列出来的先后顺序，也不是区分类型集合的依据。[Entities 1.5 的 Archetype 文档](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/concepts-archetypes.html)给出了这个分组定义。

这也解释了本节的一道检查题：把普通 `Health` 组件中的数值从 100 改成 80，没有改变组件类型集合；给实体添加它原本没有的 `Armor` 组件，则改变了集合。

## 4. Chunk 把同一类实体的数据怎样放在一起？

Archetype 描述组件类型的组合，Chunk 承载实际数据。按本节阅读的 Entities 1.5 文档，Chunk 是 **16 KiB 的内存块**；能容纳多少实体，取决于该 Archetype 的组件布局等因素，还要计入 Entity 标识及管理开销，不能把“一个 Chunk”理解成固定数量的实体。

先只看普通有数据的非托管组件。一个 Chunk 为不同组件类型安排各自的数组，并有保存 Entity 标识的数组；**这些数组中的相同索引，属于同一个实体**。

```text
某个 Position + Health 的 Chunk（示意）

索引:       0      1      2      3
Entity:    [A]    [B]    [C]    [D]
Position:  [P_A]  [P_B]  [P_C]  [P_D]
Health:    [H_A]  [H_B]  [H_C]  [H_D]
```

例如索引 1 的 Entity、Position 和 Health 对应的都是 B。后续系统如果只需要 Position，就有机会沿该组件数组顺序遍历。布局与索引配对规则见 [Archetype chunks](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/concepts-archetypes.html#archetype-chunks)。

这里说的 SoA，首先是**组件层级的数组分离**。如果 `Position` 内部包含 x、y、z，不能据此断言 ECS 会自动再把它拆成三个独立数组。

这个简化图也不覆盖所有组件形式。托管组件、共享组件、零大小组件和动态缓冲区等另有存储或管理规则，本节不把它们强行塞进同一个模型。

到这里，已经能解释一部分“为什么可能快”：同类数据被成批组织起来，适合特定的顺序访问。但还没有证明实际程序快了多少，也没有证明它已经使用 SIMD 或在多个线程上执行。

## 5. 添加 Armor，为什么会涉及数据迁移？

沿用刚才的 B。它原来有 `Position + Health`，现在要添加普通、有数据的非托管组件 `Armor`。

组件集合变成了 `Position + Health + Armor`，目标 Archetype 与原来不同。根据 Unity 的[结构变化处理流程](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/optimize-structural-changes.html)，可以按以下顺序理解：

1. 找到目标 Archetype；不存在时创建。
2. 在目标中寻找有空位的 Chunk；现有空间不足时才需要分配新的 Chunk。
3. 将已有组件的数据复制到目标位置，并创建或复制新增组件的数据。
4. 更新实体与其存储位置之间的记录。
5. 清理来源位置，并维护受到影响的查询等管理信息。

因此，“添加一个组件”不是简单地在原来那一行后面无限追加字段。它可能触发搬运和管理工作，也不意味着每次都必定新建一个 Chunk。

### B 搬走以后，原来的洞由谁来补？

同一个 Chunk 内，实体槽位保持紧凑。移除中间实体时，用末尾实体填补空位。

```text
迁移前，来源 Chunk：
索引:   0   1   2   3
实体:  [A] [B] [C] [D]

B 迁移到目标 Chunk 后：
索引:   0   1   2
实体:  [A] [D] [C]
```

所以，这道题的结果是 **D 从索引 3 补到索引 1**，不是把 C、D 都向前挪一格。所有相关组件数组要同步保持对应关系，EntityManager 中 D 的存储位置记录也要跟着更新。这个补洞步骤通常称为 swap-back。

迁移改变了 B 的存储位置，但这次添加组件操作中，B 的 Entity 身份没有因此变成另一个实体。需要分开记住“它是谁”和“它现在存在哪里”。

这也是不能把某个 Chunk 索引长期当成实体身份的原因：B 搬走了，D 的槽位也变了，先前缓存的存储位置可能失效。

不过，不能再把这个结论扩大成“每次结构变化都会挪动所有既有实体”。例如，在有空位的 Chunk 末尾加入一个实体，可以保留前面实体的现有槽位。更稳妥的理解是：**结构变化后，应按 API 的有效性规则重新获取所需访问视图，不能假设缓存的位置始终有效。**

## 本节的理解检查与下一步

这次讨论中，我先修正了“访问字段就加载整个对象”的理解，随后通过几道题把后面的关系串了起来：

| 问题 | 本节整理出的答案 |
| --- | --- |
| 普通 Health 从 100 改到 80，要换 Archetype 吗？ | 不需要，组件类型集合没有变化。 |
| 给原本没有 Armor 的实体添加 Armor 呢？ | 需要进入新的组件类型组合，并迁移到合适的存储位置。 |
| A、B、C、D 中，B 搬走后谁补索引 1？ | 末尾的 D。 |
| D 换了 Chunk 内索引，就变成新实体了吗？ | 没有，实体身份与存储位置是两回事。 |
| 每次结构变化都会移动每一个既有实体吗？ | 不会，但也不能无条件继续使用旧的存储位置。 |

本节完成的是概念阅读和理解检查。现在可以把“缓存局部性 → 数据布局 → Archetype / Chunk → 迁移成本”连起来解释；还没有做性能测量，也没有验证 Burst 生成代码或多线程执行。

下一步继续 **Query 怎样筛选和遍历数据**。等存储与访问方式更清楚以后，再分别讨论 Burst / SIMD 和 Job System 的作用。

## 参考资料

- [Unity Entities 1.5：Archetypes concepts](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/concepts-archetypes.html)
- [Unity Entities 1.5：Optimize structural changes](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/optimize-structural-changes.html)
- [Microsoft：Choosing Between Class and Struct](https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/choosing-between-class-and-struct)
- [Intel：Loop Optimizations Where Blocks are Required](https://www.intel.com/content/www/us/en/developer/articles/technical/loop-optimizations-where-blocks-are-required.html)
