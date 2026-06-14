# AnimeAgent UI 上下文

本词汇表定义 AnimeAgent Web 面板中反复出现的界面概念，确保前后端、文档与实现使用同一套语言。

## Language

**全局刷新 (Global Refresh)**
触发当前页面数据重新加载的操作入口。位置固定在顶部导航栏右侧，以图标按钮呈现，不随页面滚动消失。
_Avoid_: 页面底部悬浮刷新按钮、retry FAB

**页面主操作 (Page Primary Action)**
当前页面最重要的创建/添加操作。位置在每个页面顶部的页面标题行（Page Header）右侧，以普通 Button 呈现。
_Avoid_: 悬浮圆形主操作按钮（FAB）、与标题分离的底部按钮

**页面标题行 (Page Header)**
每个页面顶部的标题 + 主操作按钮区域，用于承载页面级标题和 Page Primary Action。
_Avoid_: 操作区、头部卡片

**内联刷新 (Inline Refresh)**
绑定到特定卡片、数据项或局部控件的刷新操作（如 Dashboard 健康检查卡片、订阅卡片元数据刷新、Logs 工具栏刷新），保留在对应组件内部，不属于 Global Refresh。
_Avoid_: 把局部刷新和全局刷新混为一谈

**悬浮操作按钮 / FAB (Floating Action Button)**
固定于视口底部角落的圆形按钮。除后续明确需要的特殊场景外，本项目默认不使用 FAB，已由 Global Refresh + Page Primary Action 替代。
_Avoid_: 默认把新增/刷新做成 FAB

**内容安全区 (Content Safe Area)**
页面主内容容器不再需要为底部悬浮按钮预留额外 padding；移除 FAB 后，列表最后一项不会被遮挡。
_Avoid_: 底部内边距补偿、FAB 占位

**模态弹窗 / Modal Dialog**
在当前页内打开的覆盖层窗口，必须阻断背景交互：背景禁止滚动、点击 overlay 可关闭、按 ESC 可关闭。弹窗内容按用途选择尺寸 preset（sm/md/lg/xl），并通过 Portal 挂载到 body，避免被父级样式影响定位。
_Avoid_: 弹出层、Dialog、新窗口

**弹窗尺寸 Preset (Modal Size Preset)**
Modal 的宽度等级，按内容类型选择：sm（确认提示）、md（短表单，如 RSS 源）、lg（中等表单，如新增订阅）、xl（复杂内容，如规则管理、剧集详情）。
_Avoid_: 所有弹窗都用同一个尺寸

**背景锁定 (Backdrop Lock)**
Modal 打开时禁止底层页面滚动，并将交互限制在弹窗内；关闭后恢复滚动。
_Avoid_: 背景还能滚动、底层可点击

**外部 ID (External ID)**
用于关联第三方元数据源的标识符：Bangumi ID、AniList ID、TMDB ID。在新增订阅时作为可选字段填写，用于自动拉取标题、集数等元数据。
_Avoid_: 平台 ID、源 ID

**搜索区 (Search Section)**
新增订阅弹窗内位于表单字段上方的独立区域，同时承载标题搜索与外部 ID 查询。用户可输入标题关键词，或填写 Bangumi / AniList / TMDB 中的任意一个/多个 ID，点击搜索后弹出候选弹窗供选择。
_Avoid_: 搜索栏、查询卡片

**ID 查询 (ID Lookup)**
根据已填写的外部 ID（Bangumi / AniList / TMDB 中的任意一个或多个）向对应元数据源请求详情，结果以候选弹窗展示，用户选择正确番剧后回填表单标题、集数与外部 ID。
_Avoid_: ID 搜索、自动填充

**标题搜索 (Title Search)**
在新增订阅弹窗顶部的搜索区输入标题文本，按标题在 Bangumi / AniList 中搜索候选作品，结果供用户选择后回填表单。
_Avoid_: 名称搜索、文本查询

**候选弹窗 (Candidate Dialog)**
标题搜索后展示结果列表的次级 Modal / Drawer。用户点击候选条目后，将其外部 ID 和多语言标题回填到新增订阅表单。
_Avoid_: 结果弹窗、选择抽屉

## Example dialogue

> Dev: “Discovery 页面有两个 FAB，左下角刷新、右下角新增规则，会挡住最后一行内容。我想把刷新放到顶部导航栏，新增规则放到页面标题行。”
>
> Domain expert: “对。刷新是 Global Refresh，放在导航栏右侧；新增规则是这个页面的 Page Primary Action，放在 Page Header 的右侧。Discovery 的 Page Header 里已经有‘自动订阅规则’按钮，把‘新增规则’作为 Primary Button 放在它旁边或替换为直接打开规则的入口都可以。注意不要把 Logs 的局部刷新和内联刷新混用。”
>
> Dev: “那 Dashboard 的刷新 FAB 也要移走吗？”
>
> Domain expert: “是的。Dashboard 只有全局刷新需求，没有 Page Primary Action，所以只保留 Global Refresh 即可。Health 卡片里的刷新是 Inline Refresh，保留。”
