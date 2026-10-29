using Unity.Collections;
using Unity.Entities;
using Unity.Jobs;
using UnityEngine;

namespace EcbPlaybackLesson
{
    // 独立类型：查询和清理都只针对本实验，不碰项目中的其他实体。
    public struct ExperimentMarker : IComponentData { }
    public struct ExperimentValue : IComponentData
    {
        public int Value;
    }

    // 文件名保持 EcbPlaybackExperiment.cs，挂到普通空 GameObject 后进入 Play。
    // 目标环境：Unity 6000.3.25f1 / Entities 1.5.0 / Burst 1.8.30。
    // 不需要 SubScene、Baker 或 ISystem；这次演示语义，不测性能。
    public sealed class EcbPlaybackExperiment : MonoBehaviour
    {
        private struct RecordCommandsJob : IJob
        {
            public EntityCommandBuffer Ecb;
            public EntityArchetype MarkerArchetype;

            public void Execute()
            {
                // 此时只记录命令！返回的 temporary 是这个 ECB 内的临时占位符。
                // 创建时就带标记，确保 Playback 即使中途失败也能定位并清理它。
                Entity temporary = Ecb.CreateEntity(MarkerArchetype);
                Ecb.AddComponent(temporary, new ExperimentValue { Value = 42 });
                // 同一 ECB 会在 Playback 时把 temporary 映射到真正创建的实体。
            }
        }

        private void Start()
        {
            World world = World.DefaultGameObjectInjectionWorld;
            if (world == null || !world.IsCreated)
            {
                Debug.LogError("[ECB] 未找到默认 ECS World，实验未运行。", this);
                return;
            }

            EntityManager em = world.EntityManager;
            using var query = em.CreateEntityQuery(ComponentType.ReadOnly<ExperimentMarker>());
            int beforeRecord = query.CalculateEntityCount();
            if (beforeRecord != 0)
            {
                // 不删除已经存在的同标记实体；避免把别的运行实例当成本次产物。
                Debug.LogError("[ECB] 已有实验标记实体，本次跳过且不清理它们。", this);
                return;
            }

            EntityArchetype markerArchetype = em.CreateArchetype(
                ComponentType.ReadWrite<ExperimentMarker>());
            var ecb = new EntityCommandBuffer(Allocator.TempJob);
            JobHandle producer = default;

            try
            {
                Debug.Log($"[ECB] 记录前 count = {beforeRecord}", this);

                // 只有一个 IJob 写这个 ECB，因此不需要 ParallelWriter / sortKey。
                producer = new RecordCommandsJob
                {
                    Ecb = ecb,
                    MarkerArchetype = markerArchetype
                }.Schedule();

                producer.Complete(); // 只保证生产者已记录完，不会自动 Playback。
                int afterComplete = query.CalculateEntityCount();
                Debug.Log($"[ECB] Complete 后 count = {afterComplete}", this);

                ecb.Playback(em); // Start 在主线程执行；此处才真正创建实体并加组件。
                int afterPlayback = query.CalculateEntityCount();
                int value = afterPlayback == 1
                    ? em.GetComponentData<ExperimentValue>(query.GetSingletonEntity()).Value
                    : -1;
                Debug.Log($"[ECB] Playback 后 count = {afterPlayback}, value = {value}", this);

                bool pass = beforeRecord == 0 && afterComplete == 0
                    && afterPlayback == 1 && value == 42;
                if (pass)
                    Debug.Log("[ECB] PASS：Complete 只等记录；Playback 才改变 World。", this);
                else
                    Debug.LogError("[ECB] FAIL：预期 count 为 0 → 0 → 1，value = 42。", this);
            }
            finally
            {
                // 即使上面抛异常，也先等生产者结束，再释放它可能仍在写的 ECB。
                producer.Complete();
                ecb.Dispose();
                em.DestroyEntity(query); // 初始为 0；只清理本次创建的带标记实体。
                // query 由 using 释放。本实验结束后实体会消失，这是主动清理。
            }
        }
    }
}
