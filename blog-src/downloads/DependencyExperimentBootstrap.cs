// 文件名必须保留为 DependencyExperimentBootstrap.cs。
// 空场景中只挂这个 MonoBehaviour；下面的 ISystem 不挂到 GameObject。
// 实验：Velocity 1 -> 2，再用新速度让 Position 0 -> 2（固定 dt = 1）。
// 目标环境：Unity 6000.3.25f1 / Entities 1.5.0 / Burst 1.8.30（用户提供）。
// 已核对官方 Entities 1.5.0 包源码中的相关 API；尚未在 Unity 中编译或实跑。

using Unity.Burst;
using Unity.Entities;
using UnityEngine;

namespace EcsDependencyExperiment
{
    // 独立类型，避免和此前实验的 Position / Velocity 混用。
    public struct Position : IComponentData { public float Value; }
    public struct Velocity : IComponentData { public float Value; }

    // 场景开关：只有 Bootstrap 创建它，这三个系统才开始更新。
    public struct RunOnce : IComponentData { }

    [DisallowMultipleComponent]
    public sealed class DependencyExperimentBootstrap : MonoBehaviour
    {
        private World _world;
        private Entity _entity;

        private void Start()
        {
            _world = World.DefaultGameObjectInjectionWorld;
            if (_world == null || !_world.IsCreated)
            {
                Debug.LogError("[DependencyExperiment] 默认 ECS World 不存在。");
                return;
            }

            EntityManager em = _world.EntityManager;

            // 防止不同 GameObject 上重复挂载，破坏本实验的单实体前提。
            using (EntityQuery existing = em.CreateEntityQuery(
                ComponentType.ReadOnly<Position>()))
            {
                if (!existing.IsEmptyIgnoreFilter)
                {
                    Debug.LogError("[DependencyExperiment] 已存在实验实体；请只保留一个 Bootstrap。");
                    return;
                }
            }

            _entity = em.CreateEntity(typeof(Position), typeof(Velocity), typeof(RunOnce));
            em.SetComponentData(_entity, new Position { Value = 0f });
            em.SetComponentData(_entity, new Velocity { Value = 1f });
            Debug.Log("[DependencyExperiment] START | Velocity=1, Position=0 (dt=1)");
        }

        private void OnDestroy()
        {
            // 只清理自己创建的实体，不销毁共享 World，也不碰旧实验。
            if (_world != null && _world.IsCreated &&
                _world.EntityManager.Exists(_entity))
            {
                _world.EntityManager.DestroyEntity(_entity);
            }
        }
    }

    [BurstCompile]
    [UpdateInGroup(typeof(SimulationSystemGroup))]
    public partial struct AccelerationSystem : ISystem
    {
        public void OnCreate(ref SystemState state)
        {
            state.RequireForUpdate<RunOnce>();
        }

        [BurstCompile]
        public void OnUpdate(ref SystemState state)
        {
            // 输入：当前系统需要等待的工作；输出：登记 A，供后续系统接上。
            state.Dependency = new AccelerateJob { DeltaTime = 1f }
                .ScheduleParallel(state.Dependency);
            // 这里只完成“调度”，不是等待 A 执行完毕。
        }
    }

    [BurstCompile]
    [WithAll(typeof(RunOnce))]
    public partial struct AccelerateJob : IJobEntity
    {
        public float DeltaTime;

        private void Execute(ref Velocity velocity)
        {
            velocity.Value += 1f * DeltaTime; // 加速度为 1：速度 1 -> 2。
        }
    }

    [BurstCompile]
    [UpdateInGroup(typeof(SimulationSystemGroup))]
    [UpdateAfter(typeof(AccelerationSystem))]
    public partial struct MovementSystem : ISystem
    {
        public void OnCreate(ref SystemState state)
        {
            state.RequireForUpdate<RunOnce>();
        }

        [BurstCompile]
        public void OnUpdate(ref SystemState state)
        {
            // UpdateAfter 只保证 A 系统先调度；不是主线程等待 A。
            // A 写 Velocity，B 读 Velocity：ECS 把相关依赖带到本系统。
            state.Dependency = new MoveJob { DeltaTime = 1f }
                .ScheduleParallel(state.Dependency);
            // 因为传入依赖，B 的工作必须等 A 完成；主线程可继续。
        }
    }

    [BurstCompile]
    [WithAll(typeof(RunOnce))]
    public partial struct MoveJob : IJobEntity
    {
        public float DeltaTime;

        private void Execute(ref Position position, in Velocity velocity)
        {
            position.Value += velocity.Value * DeltaTime; // 使用新速度 2：位置 0 -> 2。
        }
    }

    [UpdateInGroup(typeof(SimulationSystemGroup))]
    [UpdateAfter(typeof(MovementSystem))]
    public partial struct VerifySystem : ISystem
    {
        public void OnCreate(ref SystemState state)
        {
            state.RequireForUpdate<RunOnce>();
        }

        public void OnUpdate(ref SystemState state)
        {
            Entity entity = SystemAPI.GetSingletonEntity<RunOnce>();
            EntityManager em = state.EntityManager;

            // 主线程现在真要读结果：按组件类型完成写入依赖。
            // 此系统只查询了 RunOnce，不能假定它自己的 Dependency 已包含 A/B。
            em.CompleteDependencyBeforeRO<Position>();
            em.CompleteDependencyBeforeRO<Velocity>();

            float position = em.GetComponentData<Position>(entity).Value;
            float velocity = em.GetComponentData<Velocity>(entity).Value;
            bool pass = position == 2f && velocity == 2f; // 0、1、2 可被 float 精确表示。

            if (pass)
                Debug.Log("[DependencyExperiment] PASS | Velocity=2, Position=2 (dt=1)");
            else
                Debug.LogError($"[DependencyExperiment] FAIL | Velocity={velocity}, Position={position}");

            // 同步后关闭开关：此后不再调度；保留结果，直到场景对象销毁。
            em.RemoveComponent<RunOnce>(entity);
        }
    }
}

