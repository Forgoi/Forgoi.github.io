---
title: "Unity ECS 学习笔记 02：Query 怎样筛选和遍历数据"
date: "2026-10-20"
---

上一节解决了数据放在哪里：Archetype 按完整的组件类型组合分类，Chunk 实际存储数据。这一节继续看：**系统怎样找到需要的数据，又怎样读取和修改它？**

> 本篇记录概念阅读与三次理解检查，没有运行 ECS 代码或性能基准。阅读参考为 Entities 1.5 文档，不代表项目已安装该版本。示例中的 Position、Velocity、Health、Player、Enemy、Frozen 均为用于解释的组件类型；本节只讨论普通、不可启用／禁用的组件，不展开共享组件过滤等高级规则。

## 1. Query 看条件，不要求组件组合完全相同

移动系统需要位置 `Position` 和速度 `Velocity`，那么查询条件可以是同时具有这两种组件。

| Archetype | 组件类型组合 | 是否匹配 |
| --- | --- | --- |
| A | Position、Velocity | 是 |
| B | Position、Velocity、Health | 是 |
| C | Position、Health | 否 |

B 多出 `Health`，但仍满足要求。查询要求拥有 Position 和 Velocity，不等于只允许拥有这两种组件。C 缺少 Velocity，所以不匹配。

这与 Archetype 的分类标准不同：**Archetype 看完整的组件类型组合；Query 看是否满足声明的条件。** 一个 Query 因此可以匹配多个 Archetype，每个 Archetype 又可以有多个 Chunk。

[Unity 的 EntityQuery 概述](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/systems-entityquery.html)说明，查询找到具有指定组件类型的 Archetype，再让系统处理它们的 Chunk。对于本节限定的类型条件，同一个 Archetype 内的实体具有相同组件类型，无须对每个实体重复判断有没有 Position 和 Velocity。

### 第一次理解检查：增加 Health 后，还能被选中吗？

问题：移动 Query 要求 Position 和 Velocity。给 A 中某个实体添加 Health，使它进入 B，它还会匹配吗？

我的回答：

> 会的，Query只看你有没有Position 和 Velocity

结论正确，但要把范围说准：**在这道题的查询条件下**，新增 Health 不会让它失去匹配资格。不是所有 Query 都只检查这两种组件；如果另外设置了排除 Health 的条件，结果就不同。

## 2. All、Any、None 怎样组合？

在普通组件的范围内，三种常见条件可以这样理解：

- All：列出的组件必须全部具有。
- Any：列出的组件至少具有一种。
- None：列出的组件都不能具有。

如果同时设置这三组条件，需要同时满足三组要求。例如：

```text
All：Position、Velocity
Any：Player、Enemy
None：Frozen
```

含义是：有位置和速度，属于玩家或敌人，同时没有 Frozen 组件。Player、Enemy、Frozen 是示例中定义的类型名称，不是 Unity 根据名字自动判断的对象类别。

在[EntityQuery API 文档](https://docs.unity3d.com/Packages/com.unity.entities@1.5/api/Unity.Entities.EntityQuery.html)中，可以进一步查看组件集合条件与查询 API。本节不能直接套用于可启用组件：那类组件的启用状态也会影响匹配，None 不再简单等于组件类型不存在。

### 第二次理解检查：Frozen 的字段是 false，还会被排除吗？

问题：实体具有 Position、Velocity、Enemy、Frozen，普通 Frozen 组件里的 `isFrozen = false`。它会被上面的 Query 选中吗？

我的回答：

> 不会，因为它包含Frozen组件

关键是 **组件存在** 和 **组件内部字段的值** 是两件事。None 排除普通 Frozen 组件的存在，不会自动读取里面的 isFrozen 字段。因此，即使字段值为 false，仍违反 None 条件。

类似地，只要求具有 Health，并不会自动过滤出 Health 大于 0 的实体。如果还需要判断普通组件的数值，通常要在遍历逻辑中明确写出判断；共享组件值过滤是另一套机制，不能混为一谈。

## 3. 找到 Chunk 后，怎样遍历？

假设 A 有两个 Chunk，B 有一个 Chunk。移动系统处理这些匹配的 Chunk，在每个 Chunk 中访问位置数组与速度数组。

```text
当前 Chunk 中：
Position[0] 与 Velocity[0] → 第 0 个实体
Position[1] 与 Velocity[1] → 第 1 个实体
Position[2] 与 Velocity[2] → 第 2 个实体
```

同一个 Chunk 内，相同下标的组件属于同一个实体。系统读取第 0 个实体的位置和速度，计算并写回位置，再处理第 1 个实体，直到处理完这个 Chunk，然后继续处理其他匹配的 Chunk。

更新逻辑是：

```text
新位置 = 原位置 + 速度 × 本次时间间隔
```

这正好连接上一节的数据布局：同类型组件在 Chunk 内连续排列，适合按顺序访问。不需要为了处理这些实体，先把它们的全部组件搬到一个新的大数组里。

这里的说法是 **普通遍历不要求先复制全部组件**，而不是所有查询 API 都不分配或复制。显式调用 ToEntityArray、ToComponentDataArray 等 API，是另外请求生成数组；Query 本身也不是把原有实体重新分组的存储容器。

## 4. RefRO、RefRW：选中之后，怎样访问？

筛选和计算是两件事。Query 决定谁参与处理，系统中的逻辑决定对选中的数据做什么。

对上述移动逻辑而言：

| 组件 | 当前任务中的用途 | 访问方式 |
| --- | --- | --- |
| Position | 读原位置，写新位置 | RefRW，读写引用 |
| Velocity | 读取速度，不修改速度 | RefRO，只读引用 |

引用指向实体原有的组件数据。通过读写引用修改 Position，是更新实体的位置，而不是只修改一个与原数据无关的副本。

读写声明不等于数值过滤，也不意味着数据已经被修改。它表达的是怎样访问组件，为安全检查和任务依赖提供信息。后续学习 Job System 时，还会用到这个区别。

[SystemAPI.Query 官方说明](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/systems-systemapi-query.html)展示了 RefRO、RefRW 与 foreach 的配合：生成器缓存 EntityQuery，并生成遍历查询数据的枚举器。这里的 SystemAPI.Query foreach 在主线程执行，**不会因为用了 Query 就自动成为多线程任务**。

本节先理解数据流，没有直接照抄示例运行。代码实践前，需要先确认项目实际安装的 Entities 版本。

## 5. 修改位置，会触发结构性迁移吗？

第三次检查的问题是：只修改普通 Position 组件的数值，不新增或删除组件，需要换 Archetype、搬到另一个 Chunk 吗？

我的回答：

> 不需要的

原因是组件类型组合没有改变。实体仍属于原来的 Archetype，不需要因为这次普通字段更新而迁移 Chunk。这不是结构性变化。

它与上一节的添加 Armor 不同：添加组件会改变类型组合；修改普通组件中的位置、速度、血量数值，不会因此改变类型组合。这里也不要把普通组件的结论扩展到所有特殊组件操作。

因此，移动循环所做的是在已有布局上逐项更新数据，而不是每更新一次位置就搬家。这也说明，理解 ECS 的性能必须区分连续数据处理与结构性变化的成本，不能只凭框架名称判断快慢。

## 6. 这一节串起来了什么？

1. Archetype 按完整的组件类型组合分组；Query 按指定条件匹配，可以覆盖多个 Archetype。
2. 对本节的普通组件，All、Any、None 分别表达全部具备、至少一种、全部排除；组件是否存在不同于字段值判断。
3. 系统遍历匹配的 Chunk，在 Chunk 内按对应下标访问需要的组件数据，不必先复制所有组件到新数组。
4. RefRO 与 RefRW 表达只读和读写访问；SystemAPI.Query 的 foreach 不会自动多线程。
5. 修改普通 Position 的值不改变组件类型组合，不会因此触发 Archetype / Chunk 迁移。

三次概念检查完成后，我确认这一部分没有剩余疑问。下一步进入 Query 代码实践，再继续理解 Burst / SIMD 和 Job System。代码运行与性能测量仍待进行，本篇不把概念理解写成实验结论。

## 参考与下一步

- [Unity Entities 1.5：Query data with EntityQuery](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/systems-entityquery.html)
- [Unity Entities 1.5：EntityQuery API](https://docs.unity3d.com/Packages/com.unity.entities@1.5/api/Unity.Entities.EntityQuery.html)
- [Unity Entities 1.5：Iterate over component data with SystemAPI.Query](https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/systems-systemapi-query.html)
- [上一节：从缓存局部性到 Chunk 迁移](/2026/10/19/unity-ecs-cache-archetype-chunk/)
- [查看 ECS 学习路线](/learning/)
