using UnityEngine;

// Unity 6.3：把脚本挂到空物体上。场景中只放一个，且不要让其他脚本修改这些全局设置。
// 在 Inspector 切换 30 / 120 FPS；每约 5 秒看一次 Console 汇总。
[DisallowMultipleComponent]
public sealed class FixedStepProbe : MonoBehaviour
{
    public enum FrameRate { Fps30 = 30, Fps120 = 120 }

    [SerializeField] private FrameRate targetFps = FrameRate.Fps30;

    private const double ReportSeconds = 5.0;
    private int activeTarget;
    private int fixedSinceLastUpdate;
    private int frames, fixedSteps, zeroFrames, oneFrames, multipleFrames;
    private double windowStart;
    private bool discardNextUpdate;

    private int savedTargetFps, savedVSync;
    private float savedFixedDeltaTime, savedTimeScale;
    private bool settingsSaved;

    private void OnEnable()
    {
        // 临时改动全局设置；禁用组件时恢复实验开始前的值。
        savedTargetFps = Application.targetFrameRate;
        savedVSync = QualitySettings.vSyncCount;
        savedFixedDeltaTime = Time.fixedDeltaTime;
        savedTimeScale = Time.timeScale;
        settingsSaved = true;

        QualitySettings.vSyncCount = 0; // 桌面平台开启 VSync 时，目标帧率会被忽略。
        Time.timeScale = 1f;
        Time.fixedDeltaTime = 0.02f;    // 正常推进时，每秒游戏时间有约 50 个固定步。
        ApplyTarget();
    }

    private void ApplyTarget()
    {
        activeTarget = (int)targetFps;
        Application.targetFrameRate = activeTarget;
        discardNextUpdate = true;
    }

    private void FixedUpdate()
    {
        // 同一渲染帧前可以执行 0 次、1 次或多次固定更新。
        fixedSinceLastUpdate++;
    }

    private void Update()
    {
        if (activeTarget != (int)targetFps)
            ApplyTarget();

        double now = Time.realtimeSinceStartupAsDouble;
        if (discardNextUpdate)
        {
            // 首帧／切换目标的这一帧不完整，清掉它，避免混入上一组结果。
            fixedSinceLastUpdate = 0;
            ResetWindow(now);
            discardNextUpdate = false;
            return;
        }

        int stepsThisFrame = fixedSinceLastUpdate;
        fixedSinceLastUpdate = 0;
        frames++;
        fixedSteps += stepsThisFrame;

        if (stepsThisFrame == 0) zeroFrames++;
        else if (stepsThisFrame == 1) oneFrames++;
        else multipleFrames++;

        double elapsed = now - windowStart;
        if (elapsed < ReportSeconds) return;

        // 用真实经过时间算平均 FPS；目标 120 不代表实际一定能跑到 120。
        // 仅每 5 秒输出一次，避免逐帧日志本身拖慢实验。
        Debug.Log(
            $"[FixedStepProbe] 目标={activeTarget} FPS；窗口={elapsed:F2}s\n" +
            $"实测 FPS (Update/s)={frames / elapsed:F1}；" +
            $"FixedUpdate/s={fixedSteps / elapsed:F1}；" +
            $"平均固定步/帧={(double)fixedSteps / frames:F3}\n" +
            $"总帧数={frames}；固定步数={fixedSteps}\n" +
            $"0 次：{zeroFrames} 帧 ({100.0 * zeroFrames / frames:F1}%)；" +
            $"1 次：{oneFrames} 帧 ({100.0 * oneFrames / frames:F1}%)；" +
            $"2+ 次：{multipleFrames} 帧 ({100.0 * multipleFrames / frames:F1}%)",
            this);

        ResetWindow(now);
    }

    private void ResetWindow(double now)
    {
        windowStart = now;
        frames = fixedSteps = zeroFrames = oneFrames = multipleFrames = 0;
    }

    private void OnDisable()
    {
        if (!settingsSaved) return;

        Application.targetFrameRate = savedTargetFps;
        QualitySettings.vSyncCount = savedVSync;
        Time.fixedDeltaTime = savedFixedDeltaTime;
        Time.timeScale = savedTimeScale;
        settingsSaved = false;
    }
}
