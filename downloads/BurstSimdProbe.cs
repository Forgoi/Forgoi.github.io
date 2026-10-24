using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using UnityEngine;

// 只在挂有此组件的场景对象启用并进入 Play 后运行一次。
// 不创建 ECS System 或 World，也不调度到工作线程。
public sealed class BurstSimdProbe : MonoBehaviour
{
    private const int Count = 1024;

    // 在 Burst Inspector 中搜索 AddArraysJob。
    [BurstCompile(CompileSynchronously = true)]
    public struct AddArraysJob : IJob
    {
        [ReadOnly] public NativeArray<float> A;
        [ReadOnly] public NativeArray<float> B;
        [WriteOnly] public NativeArray<float> Output;

        public void Execute()
        {
            // 各次迭代互不依赖，给 Burst 自动向量化的机会。
            for (int i = 0; i < Output.Length; i++)
            {
                Output[i] = A[i] + B[i];
            }
        }
    }

    private void Start()
    {
        NativeArray<float> a = default;
        NativeArray<float> b = default;
        NativeArray<float> output = default;

        try
        {
            // 三次独立分配，不要让输入、输出指向同一块内存。
            a = new NativeArray<float>(Count, Allocator.TempJob);
            b = new NativeArray<float>(Count, Allocator.TempJob);
            output = new NativeArray<float>(Count, Allocator.TempJob);

            for (int i = 0; i < Count; i++)
            {
                a[i] = i;
                b[i] = 2 * i;
                output[i] = -1f;
            }

            var job = new AddArraysJob { A = a, B = b, Output = output };
            // Run 是 Job 扩展方法，在当前主线程同步执行。
            // 不要改为 job.Execute()，那只是普通的 C# 方法调用。
            job.Run();

            int mismatchCount = 0;
            for (int i = 0; i < Count; i++)
            {
                // 本例的小整数可用 float 精确表示，可直接比较。
                if (output[i] != 3f * i)
                    mismatchCount++;
            }

            if (mismatchCount == 0)
            {
                Debug.Log($"[BurstSimdProbe] PASS: {Count}/{Count}; " +
                          $"first = {output[0]}, {output[1]}, {output[2]}, {output[3]}; " +
                          $"last = {output[Count - 1]}");
            }
            else
            {
                Debug.LogError($"[BurstSimdProbe] FAIL: {mismatchCount}/{Count} mismatches.");
            }
        }
        finally
        {
            if (output.IsCreated) output.Dispose();
            if (b.IsCreated) b.Dispose();
            if (a.IsCreated) a.Dispose();
        }
    }
}
