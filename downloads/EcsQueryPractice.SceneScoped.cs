using Unity.Entities;
using UnityEngine;

// 使用方法：退出 Play，用本文件完整替换原来的 EcsQueryPractice.cs，不要保留重复定义。
// 文件名保持 EcsQueryPractice.cs；放在 Assets/Scripts，不要放在 Editor 文件夹。
// 只在本课场景中创建一个空 GameObject，把 EcsQueryPractice 挂上去，再按 Play。
// 本实验只看 Console；不需要 SubScene、Baker、Entities Graphics。
// 当前保留“去掉 WithNone<Frozen>()”的实验版本：匹配 3 个，D 也移动。
namespace EcsQueryLesson
{
    // 普通场景中的启动入口，不是 ECS System。
    [DisallowMultipleComponent]
    public sealed class EcsQueryPractice : MonoBehaviour
    {
        private World _world;

        private void Start()
        {
            // 单独的实验 World；不使用、不修改默认 World。
            _world = new World("EcsQueryPractice");

            try
            {
                var system = _world.CreateSystem<EcsQueryPracticeSystem>();

                // 只手动执行一次，不注册到 PlayerLoop，不需要 SystemGroup。
                system.Update(_world.Unmanaged);
            }
            catch
            {
                DisposeWorld();
                throw;
            }
        }

        private void OnDestroy()
        {
            // 场景卸载、物体销毁时，连同实验的系统和实体一起释放。
            DisposeWorld();
        }

        private void DisposeWorld()
        {
            if (_world != null && _world.IsCreated)
                _world.Dispose();

            _world = null;
        }
    }

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
    // 关键：禁止 Entities 把这个实验系统自动创建到默认 World。
    [DisableAutoCreation]
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
            // 当前没有 WithNone<Frozen>()，所以带 Frozen 的 D 仍会被匹配。
            // 想恢复原对照组，在 Query 调用后加上 .WithNone<Frozen>()：匹配数变成 2。
            foreach (var (position, velocity) in
                     SystemAPI.Query<RefRW<Position>, RefRO<Velocity>>())
            {
                // 修改的是组件值，没有增加 / 删除组件，不会因此改变 Archetype。
                position.ValueRW.Value += velocity.ValueRO.Value * deltaTime;
                matchedCount++;
            }

            Debug.Log($"[Query实验] 本次匹配数量：{matchedCount}");
            PrintPositions(em, "执行后");

            // 本来只手动更新一次；再禁用系统，防止意外重复更新。
            // 数据保留在专用 World 中，直到启动物体被销毁。
            state.Enabled = false;
        }

        public void OnDestroy(ref SystemState state)
        {
            // 本例没有自己分配的 Native 容器；专用 World 销毁时会清理其中的实体。
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
