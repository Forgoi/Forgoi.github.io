using Unity.Entities;
using Unity.Jobs;
using UnityEngine;

namespace AutomaticEcbLesson
{
    // 目标：Unity 6000.3.25f1 / Entities 1.5.0 / Burst 1.8.30。
    // 文件名保持 AutomaticEcbExperiment.cs；挂到空场景的一个空 GameObject。
    // 不需要 SubScene / Baker。使用默认 ECS World、默认 PlayerLoop；不要禁用相关系统。
    // 使用默认的 Play Mode 重载设置；需要正常客户端的 Presentation（不是纯服务器 World）。
    // 请只放一个实验组件；每次进入 Play 跑一次。不测性能，因此这里不加 BurstCompile。
    //
    // 预期只有三条观察日志：
    // [Auto ECB] ① 记录前 count = 0
    // [Auto ECB] ② Schedule 后、自动 Playback 前 count = 0
    // [Auto ECB] ③ 自动 Playback 后 count = 1, value = 42
    //
    // 重点看 AutoEcbProducerSystem.OnUpdate 中的三个步骤。
    // 与上一实验不同：本文件不手动 Complete / Playback / Dispose 这个 ECB。

    // 以下类型只属于本实验，不会查询或清理上一实验的实体。
    public struct AutoEcbMarker : IComponentData { }
    public struct AutoEcbValue : IComponentData
    {
        public int Value;
    }

    // 这是运行开关，不是本实验要观察的“产物”。count 只数 AutoEcbMarker。
    public struct AutoEcbRun : IComponentData
    {
        public int Stage; // 0 = 尚未调度；1 = 已调度；2 = 已观察或已中止。
        public bool CleanupRequested;
    }

    [DisallowMultipleComponent]
    public sealed class AutomaticEcbExperiment : MonoBehaviour
    {
        private World _world;
        private Entity _runEntity;

        private void Start()
        {
            _world = World.DefaultGameObjectInjectionWorld;
            if (_world == null || !_world.IsCreated)
            {
                Debug.LogError("[Auto ECB] 未找到默认 ECS World，实验未运行。", this);
                return;
            }

            EntityManager em = _world.EntityManager;
            using var runs = em.CreateEntityQuery(ComponentType.ReadOnly<AutoEcbRun>());
            using var results = em.CreateEntityQuery(ComponentType.ReadOnly<AutoEcbMarker>());
            if (!runs.IsEmptyIgnoreFilter || !results.IsEmptyIgnoreFilter)
            {
                // 不接管已有实验，失败的启动实例也不会清理它的实体。
                Debug.LogError("[Auto ECB] 已有实验运行或产物；请只保留一个实验组件。", this);
                return;
            }

            _runEntity = em.CreateEntity(ComponentType.ReadWrite<AutoEcbRun>());
            // 新组件默认 Stage = 0。只有这个开关存在，下面两个系统才会更新。
        }

        private void OnDestroy()
        {
            if (_world == null || !_world.IsCreated || _runEntity == Entity.Null)
                return;

            EntityManager em = _world.EntityManager;
            if (!em.Exists(_runEntity))
                return;

            // 不抢在自动 Playback 前清理，否则稍后 Playback 可能又创建出实体。
            // 请 Presentation 系统在安全的观察阶段清理；World 已销毁时无需再清理。
            AutoEcbRun run = em.GetComponentData<AutoEcbRun>(_runEntity);
            run.CleanupRequested = true;
            em.SetComponentData(_runEntity, run);
        }
    }

    [UpdateInGroup(typeof(SimulationSystemGroup))]
    [UpdateBefore(typeof(EndSimulationEntityCommandBufferSystem))]
    public partial struct AutoEcbProducerSystem : ISystem
    {
        private EntityQuery _results;
        private EntityArchetype _resultArchetype;

        public void OnCreate(ref SystemState state)
        {
            state.RequireForUpdate<AutoEcbRun>();
            state.RequireForUpdate<EndSimulationEntityCommandBufferSystem.Singleton>();
            _results = state.GetEntityQuery(ComponentType.ReadOnly<AutoEcbMarker>());
            _resultArchetype = state.EntityManager.CreateArchetype(
                ComponentType.ReadWrite<AutoEcbMarker>());
        }

        private struct RecordCommandsJob : IJob
        {
            public EntityCommandBuffer Ecb;
            public EntityArchetype ResultArchetype;

            public void Execute()
            {
                // 仍然只记录命令。temporary 仍然只是这个 ECB 内的临时占位符。
                Entity temporary = Ecb.CreateEntity(ResultArchetype);
                Ecb.AddComponent(temporary, new AutoEcbValue { Value = 42 });
            }
        }

        public void OnUpdate(ref SystemState state)
        {
            AutoEcbRun run = SystemAPI.GetSingleton<AutoEcbRun>();
            if (run.Stage != 0 || run.CleanupRequested)
                return;

            int beforeRecord = _results.CalculateEntityCount();
            if (beforeRecord != 0)
            {
                run.Stage = 2;
                SystemAPI.SetSingleton(run);
                Debug.LogError("[Auto ECB] 记录前产物不是 0，实验中止。");
                return;
            }

            // 开关更新放在 Schedule 之前；Schedule 之后不做结构变化或额外同步。
            run.Stage = 1;
            SystemAPI.SetSingleton(run);
            Debug.Log($"[Auto ECB] ① 记录前 count = {beforeRecord}");

            // 1. 取得负责“本帧 Simulation 末尾”回放的系统单例。
            var singleton = SystemAPI.GetSingleton<EndSimulationEntityCommandBufferSystem.Singleton>();

            // 2. 向它申请 ECB；这不是自己 new 出来、自己管理生命周期的 ECB。
            EntityCommandBuffer ecb = singleton.CreateCommandBuffer(state.WorldUnmanaged);

            // 3. 调度记录命令的 Job，并把返回的句柄写回 state.Dependency。
            // GetSingleton 的依赖登记 + 这个句柄，才能让 ECBSystem 等到生产者。
            // 这里是普通 IJob，不能省略赋值，误以为它会自动写回 Dependency。
            state.Dependency = new RecordCommandsJob
            {
                Ecb = ecb,
                ResultArchetype = _resultArchetype
            }.Schedule(state.Dependency);

            int beforePlayback = _results.CalculateEntityCount();
            Debug.Log($"[Auto ECB] ② Schedule 后、自动 Playback 前 count = {beforePlayback}");
            // 这里只能断言“尚未 Playback”，不能断言“Job 已经完成记录”。
            // Job 此刻可能没开始、正在跑，也可能已完成；都不会直接创建 World 中的实体。
            // 查询是普通非 enableable 标记，未设置过滤器，不靠它等待生产者。
            // OnUpdate 返回后，EndSimulation ECBSystem 会自动：等生产者 → Playback → Dispose。
        }
    }

    // 默认 PlayerLoop：Simulation 完成之后，才轮到 Presentation。
    // 不要把普通 Simulation 系统仅用 UpdateAfter 排到 EndSimulation 后：
    // EndSimulation 有 OrderLast，优先级高于 UpdateAfter。
    [UpdateInGroup(typeof(PresentationSystemGroup))]
    public partial struct AutoEcbObserveSystem : ISystem
    {
        private EntityQuery _results;

        public void OnCreate(ref SystemState state)
        {
            state.RequireForUpdate<AutoEcbRun>();
            _results = state.GetEntityQuery(ComponentType.ReadOnly<AutoEcbMarker>());
        }

        public void OnUpdate(ref SystemState state)
        {
            AutoEcbRun run = SystemAPI.GetSingleton<AutoEcbRun>();

            if (run.CleanupRequested)
            {
                // 删除挂载组件/物体或卸载场景后，在下一次 Presentation 更新清理。
                // 若退出 Play 时 World 先销毁，则其实体会随 World 一起销毁。
                // 只清理本实验标记和本次开关，不碰其他教学实验或游戏实体。
                Entity runEntity = SystemAPI.GetSingletonEntity<AutoEcbRun>();
                state.EntityManager.DestroyEntity(_results);
                state.EntityManager.DestroyEntity(runEntity);
                return;
            }

            if (run.Stage != 1)
                return;

            int afterPlayback = _results.CalculateEntityCount();
            int value = -1;
            if (afterPlayback == 1)
            {
                Entity result = _results.GetSingletonEntity();
                if (state.EntityManager.HasComponent<AutoEcbValue>(result))
                    value = state.EntityManager.GetComponentData<AutoEcbValue>(result).Value;
            }

            Debug.Log($"[Auto ECB] ③ 自动 Playback 后 count = {afterPlayback}, value = {value}");
            if (afterPlayback != 1 || value != 42)
                Debug.LogError("[Auto ECB] 结果不符合预期：应为 count = 1, value = 42。");

            run.Stage = 2; // 下帧不再调度、不再重复打印。
            SystemAPI.SetSingleton(run);
            // 注意：ECB 已被 ECBSystem 释放，但刚创建的实体仍然保留。
            // 可在 Entities Hierarchy 查看它；直到实验组件销毁时才请求删除。
        }
    }
}
