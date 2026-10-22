using Unity.Entities;
using UnityEngine;

// 使用方法：把本文件放到 Assets/Scripts（不要放在 Editor 文件夹），等待编译后按 Play。
// 不要把它挂到 GameObject 上：ISystem 由 Entities 的默认 World 自动创建和更新。
// 本实验只看 Console；不需要 SubScene、Baker、Entities Graphics 或任何场景物体。
namespace EcsQueryLesson
{
    // 自定义的一维位置数据，不是 GameObject.Transform，也不是 ECS 的 LocalTransform。
    public struct Position : IComponentData
    {
        public float Value;
    }

    // 每个模拟秒的位置变化量。
    public struct Velocity : IComponentData
    {
        public float Value;
    }

    // 额外的普通组件，用来验证：多一个组件不会自动被 Query 排除。
    public struct Health : IComponentData
    {
        public int Value;
    }

    // 普通空标签：只有“有 / 没有”，本实验不使用 IEnableableComponent。
    public struct Frozen : IComponentData { }

    // partial 让 Entities 的源码生成器可以补充 SystemAPI.Query 所需的代码。
    [UpdateInGroup(typeof(SimulationSystemGroup))]
    public partial struct EcsQueryPracticeSystem : ISystem
    {
        // 保存实体句柄只是为了按 A、B、C、D 的固定顺序打印，不代表 Query 的遍历顺序。
        private Entity _a;
        private Entity _b;
        private Entity _c;
        private Entity _d;

        public void OnCreate(ref SystemState state)
        {
            var em = state.EntityManager;

            // 四种组件组合，对应四种不同的 Archetype。
            _a = em.CreateEntity(typeof(Position), typeof(Velocity));
            _b = em.CreateEntity(typeof(Position), typeof(Velocity), typeof(Health));
            _c = em.CreateEntity(typeof(Position));
            _d = em.CreateEntity(typeof(Position), typeof(Velocity), typeof(Frozen));

            // 起点统一设为 0，便于看清哪些实体被 Query 修改。
            em.SetComponentData(_a, new Position { Value = 0f });
            em.SetComponentData(_b, new Position { Value = 0f });
            em.SetComponentData(_c, new Position { Value = 0f });
            em.SetComponentData(_d, new Position { Value = 0f });

            em.SetComponentData(_a, new Velocity { Value = 1f });
            em.SetComponentData(_b, new Velocity { Value = 2f });
            em.SetComponentData(_b, new Health { Value = 100 });
            em.SetComponentData(_d, new Velocity { Value = 3f });
        }

        public void OnUpdate(ref SystemState state)
        {
            var em = state.EntityManager;
            PrintPositions(em, "执行前");

            // 只模拟一步，明确把这一步视作 1 秒；不依赖实际帧率，也不是等待 1 秒。
            const float deltaTime = 1f;
            int matchedCount = 0;

            // Query 中的两个类型都必须存在，相当于 All(Position, Velocity)。
            // RefRW：允许读写 Position。RefRO：只读 Velocity。
            // WithNone<Frozen>：排除带有 Frozen 标签的实体。
            foreach (var (position, velocity) in
                     SystemAPI.Query<RefRW<Position>, RefRO<Velocity>>()
                         .WithNone<Frozen>())
            {
                // 修改的是组件值，没有增加 / 删除组件，不会因此改变 Archetype。
                position.ValueRW.Value += velocity.ValueRO.Value * deltaTime;
                matchedCount++;
            }

            Debug.Log($"[Query实验] 本次匹配数量：{matchedCount}");
            PrintPositions(em, "执行后");

            // 关闭本系统后续的更新，避免每帧执行、刷屏；实体和组件仍保留。
            // 退出 Play 后再次进入，可以从初始状态重新实验。
            state.Enabled = false;
        }

        public void OnDestroy(ref SystemState state)
        {
            // 本例没有自己分配的 Native 容器；默认 World 销毁时会清理其中的实体。
        }

        private void PrintPositions(EntityManager em, string stage)
        {
            float a = em.GetComponentData<Position>(_a).Value;
            float b = em.GetComponentData<Position>(_b).Value;
            float c = em.GetComponentData<Position>(_c).Value;
            float d = em.GetComponentData<Position>(_d).Value;

            Debug.Log($"[Query实验] {stage}：A={a}，B={b}，C={c}，D={d}");
        }
    }
}
