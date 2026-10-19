# Forgoi · Unity 学习手记

一个轻量、中文优先的 Unity 技术学习博客。文章以 Markdown 保存，使用 Python 标准库生成静态页面，部署在 GitHub Pages。

在线站点：https://forgoi.github.io/

## 本地生成与检查

需要 Python 3.10 或更新版本；不需要安装 npm 包、Python 包、外部主题或其他依赖。

```sh
python scripts/build.py
python -m unittest discover -s scripts -p 'test_*.py' -v
python scripts/check.py
python -m http.server 8000
```

在浏览器中打开 http://localhost:8000/。不要直接双击 HTML 文件，站内链接使用根路径。

`check.py` 会重新构建，并检查输出是否逐字节一致、HTML 结构和必要元数据、内部链接与锚点、XML 订阅文件、代码下载和第三方运行时资源。它不会自动访问外部参考链接，也不替代实际浏览器检查。

## 修改文章

1. 在 `blog-src/posts/` 中新增或编辑 Markdown 文件。
2. 在 `blog-src/site.json` 的 `posts` 数组维护文章信息。必需字段：
   - `file`：Markdown 文件名
   - `title`、`date`（YYYY-MM-DD）、`excerpt`、`tags`
   - `permalink`：稳定的小写根路径，例如 `/2026/10/19/unity-fixed-timestep-interpolation/`
   - `status`：`completed`（学习笔记）或 `reading`（阅读中）
   - `read_minutes`：预计阅读分钟数
   - `short_title`：可选的首页短标题
3. 运行构建与检查，并一并提交源文件和生成结果。

正文可以保留 YAML front matter，生成器会跳过它；站点索引信息以 `site.json` 为准，避免引入 YAML 依赖。文章状态描述的是学习记录，不自动意味着文中的每个实验都已经做完。应在正文中明确区分实测、阅读理解、数值推演与待验证项。

### 支持的 Markdown

- 段落、一级至六级标题、粗体、斜体、行内代码
- HTTP(S) / 根路径 / 锚点链接
- 一级有序和无序列表、引用块、水平线
- 围栏代码块（可标注 `text`、`csharp`、`python` 等语言）
- 常规管道表格（单元格内不要使用未转义管道）

这是有意限定的 Markdown 子集，不是完整 CommonMark。暂不支持嵌套列表、脚注、内嵌 HTML、Markdown 图片语法和复杂表格。正文原始 HTML 会转义，HTML 注释会忽略。要扩展语法，请同时增加 `scripts/test_build.py` 的测试。

## 目录

```text
blog-src/
  site.json         站点设置和文章索引
  posts/            文章 Markdown 原稿
  static/           CSS、少量增强 JS 和 SVG 图标
  downloads/        可下载的实验脚本源文件
scripts/
  build.py          零依赖静态生成器与页面模板
  check.py          确定性构建和内部链接检查
  test_build.py     Markdown 与转义单元测试
assets/             生成的运行时资源，不要直接编辑
2026/.../           生成的文章页面
archives/           文章归档（渐进增强的搜索）
learning/           学习路线
about/              关于本站
```

`index.html`、`404.html`、`atom.xml`、`sitemap.xml`、`robots.txt`、`.nojekyll` 以及 `.build-manifest.json` 也由构建器生成。`.build-manifest.json` 列出生成器拥有的文件，重建时仅清理这些文件；不扫描删除任意源文件。

## 设计与阅读

- 响应式布局，中文系统字体，无远程字体、图标库、统计或跟踪脚本
- 文章桌面目录、手机折叠目录、可横向滚动代码/表格
- 语义 HTML、跳转正文链接、可见键盘焦点、减少动态效果偏好与打印样式
- 复制代码和归档搜索为渐进增强，关闭 JavaScript 仍可阅读和导航
- 固定时间步首页图为概念示意，实际测量值只来自正文记录的实验

## 发布

保持现有 GitHub Pages 的分支根目录发布方式，并保留 `.nojekyll`。将源文件和已生成页面一起提交至仓库的 Pages 发布分支。无需新增 Actions 工作流、密钥或权限。

仓库改版移除了旧的占位文章与 Hexo/Vivia 生成资源。旧提交仍保留在 Git 历史中，没有重写历史。

新增文章以后，请手工更新 `build.py` 中的学习路线和首页进度摘要，使状态与真实学习进度一致。不要把计划中的 ECS 实验标记为已完成。
