# SVG/CSS 代码配方

组装规则：一个 HTML 文件，`<body>` 里一个 `.canvas` 容器，内联一个 `<svg viewBox="0 0 1200 H">`。
所有坐标手工布局，token 值见 style-guide.md。下面的坐标、文字都是**占位示意**，按你的内容重算。

**手绘感的来源**：所有静态几何形状加 `data-rough`（本风格默认 `data-roughness="1.8"`），
加载时由捆绑的 rough.js + sketchify.js 自动替换成抖动描边的手绘版本。
你只管写干净的 `<rect>/<path>/<circle>`，不要自己模拟抖动。
例外：**参与 CSS 动画的元素**（流动圆点、旋转齿轮、描画对勾等）**不加** `data-rough`
（rough 替换的是静态视觉副本，动画类挂在原元素上会看不见）。

## 0. 文件骨架 + 资产内联 + 纸纹

HTML 里写三个占位符：`__FONTFACES__`（在 `<style>` 内）、`__ROUGH_JS__`、`__SKETCHIFY_JS__`，
写完后用脚本一次性注入（别手工粘贴几十 KB 字符串）：

```bash
python3 - <<'EOF'
import base64, pathlib, re
skill = pathlib.Path.home() / '.claude/skills/animated-sketch-diagram'
p = pathlib.Path('diagram.html')
html = p.read_text()
faces = ''
# 拉丁手写后备字体（无 Comic Sans 环境用），全量内联
for f in sorted((skill/'assets/fonts').glob('*.woff2')):
    fam, w = f.stem.rsplit('-', 1)
    b64 = base64.b64encode(f.read_bytes()).decode()
    faces += ("@font-face{font-family:'%s';font-weight:%s;"
              "src:url(data:font/woff2;base64,%s) format('woff2');}\n" % (fam, w, b64))
# 汉字：LXGW WenKai Screen 按用到的字符子集化（几十 KB），永不整包内联
chars = ''.join(sorted(set(re.findall(r'[^\x00-\x7f]', html))))
if chars:
    import tempfile
    from fontTools import subset  # pip3 install --user --break-system-packages fonttools brotli
    out = tempfile.mktemp(suffix='.woff2')
    subset.main([str(skill/'assets/fonts-cn/LXGWWenKaiScreen.ttf'),
                 '--text=%s' % chars, '--flavor=woff2', '--output-file=%s' % out])
    b64 = base64.b64encode(open(out, 'rb').read()).decode()
    faces += ("@font-face{font-family:'LXGW WenKai Screen';"
              "src:url(data:font/woff2;base64,%s) format('woff2');}\n" % b64)
html = html.replace('__FONTFACES__', faces)
html = html.replace('__ROUGH_JS__', (skill/'assets/vendor/rough.js').read_text())
html = html.replace('__SKETCHIFY_JS__', (skill/'assets/vendor/sketchify.js').read_text())
p.write_text(html)
EOF
```

```html
<meta charset="utf-8">
<style>
__FONTFACES__
:root { --loop: 3000ms; --ink: #212020; --paper: #f8f5e8;
        --font-title: 'Comic Sans MS','Kalam','LXGW WenKai Screen','Kaiti SC',cursive;
        --font-body: 'Comic Sans MS','PatrickHand','LXGW WenKai Screen','Kaiti SC',cursive; }
body { margin: 0; background: var(--paper); }
.canvas { width: 1200px; margin: 0 auto; }
svg { display: block; }  /* 不加会有 ~5px 行内基线空隙被录进 GIF */
svg text { font-family: var(--font-body); fill: var(--ink); }
.t-title { font-family: var(--font-title); font-weight: 700; }
.t-strong { font-family: var(--font-title); font-weight: 700; }
.mono { font-family: ui-monospace, Menlo, monospace; }
</style>
<div class="canvas">
  <svg viewBox="0 0 1200 900" width="1200" height="900">
    <!-- 纸纹（可选，放最底层）：极淡颗粒。alpha 行系数 0.06，调大更糙 -->
    <filter id="grain">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2"/>
      <feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0.06 0.06 0.06 0 0"/>
    </filter>
    <rect width="1200" height="900" fill="var(--paper)"/>
    <rect width="1200" height="900" filter="url(#grain)"/>
    <!-- 内容 -->
  </svg>
</div>
<!-- body 末尾 -->
<script>__ROUGH_JS__</script>
<script>__SKETCHIFY_JS__</script>
<script>sketchify()</script>
```

## 1. 大标题（签名式）+ 下划线扫尾 + ✦

```html
<text class="t-title" x="880" y="80" font-size="62">MyTitle</text>
<!-- 抖动下划线：从标题下方扫过，末端上翘 -->
<path data-rough data-roughness="2.2" d="M878 96 Q1030 106 1180 92" fill="none"
      stroke="var(--ink)" stroke-width="3"/>
<!-- 4 角星 ✦（可挂 .pulse 微动效） -->
<path d="M1186 118 l3.5 8.5 8.5 3.5 -8.5 3.5 -3.5 8.5 -3.5 -8.5 -8.5 -3.5 8.5 -3.5 z" fill="var(--ink)"/>
```

中央口号放版面天然空隙：

```html
<text class="t-title" x="600" y="360" font-size="30" text-anchor="middle">Every run becomes a better next start</text>
<!-- 两侧各一颗 ✦，同上 path，缩放/平移 -->
```

## 2. 区块面板：序号章 + 居中标题（以横向区块为例）

这是"横向区块"的写法；纵向层/径向/对比柱等原型用同样的 token 照此类推。

```html
<g class="region region-sage">
  <rect data-rough data-roughness="1.8" x="240" y="250" width="360" height="170" rx="18"
        fill="#f0f1e0" stroke="var(--ink)" stroke-width="2.2"/>
  <!-- 序号章：ink 实心圆 + paper 数字 -->
  <circle data-rough cx="272" cy="278" r="15" fill="var(--ink)" stroke="none"/>
  <!-- 数字必须用 style= 内联（CSS 的 svg text{fill:ink} 会覆盖 fill 属性，黑圆上黑字 = 看不见） -->
  <text x="272" y="286" font-size="20" font-weight="bold" style="fill:var(--paper)" text-anchor="middle">2</text>
  <!-- 居中标题 + 分隔线（分隔线可省） -->
  <text class="t-strong" x="435" y="286" font-size="25" text-anchor="middle">Memory Extraction</text>
  <path data-rough d="M258 300 H582" fill="none" stroke="var(--ink)" stroke-width="1.4"/>
</g>
```

## 3. 内卡：纸白卡片、一叠纸、折角文档

```html
<!-- 普通内卡：图标 + 标签 -->
<rect data-rough x="260" y="316" width="150" height="34" rx="8"
      fill="#faf7eb" stroke="var(--ink)" stroke-width="1.7"/>
<text x="300" y="338" font-size="15">User Messages</text>

<!-- 一叠纸：背后垫 1~2 张偏移副本（先画后面的） -->
<rect data-rough x="496" y="308" width="86" height="98" rx="6" fill="#faf7eb" stroke="var(--ink)" stroke-width="1.5"/>
<rect data-rough x="490" y="303" width="86" height="98" rx="6" fill="#faf7eb" stroke="var(--ink)" stroke-width="1.5"/>
<rect data-rough x="484" y="298" width="86" height="98" rx="6" fill="#faf7eb" stroke="var(--ink)" stroke-width="1.7"/>

<!-- 折角文档：右上角折角 + 内部三两行短横线（"速记涂鸦"表达内容） -->
<path data-rough d="M484 298 h66 l20 20 v78 h-86 z" fill="#faf7eb" stroke="var(--ink)" stroke-width="1.7"/>
<path d="M550 298 v20 h20" fill="none" stroke="var(--ink)" stroke-width="1.7"/>
<line x1="496" y1="340" x2="556" y2="340" stroke="var(--ink)" stroke-width="1.6"/>
<line x1="496" y1="352" x2="548" y2="352" stroke="var(--ink)" stroke-width="1.6"/>
<line x1="496" y1="364" x2="552" y2="364" stroke="var(--ink)" stroke-width="1.6"/>
```

## 4. 简笔涂鸦图标（纯 ink 单色，2px）

就地用几条 `line/circle/path` 画，不引图标库。常用速记：

```html
<!-- 小人（圆头 + 弧身），"人/agent 在做事" -->
<circle data-rough cx="400" cy="330" r="11" fill="#faf7eb" stroke="var(--ink)" stroke-width="2"/>
<path data-rough d="M384 372 q16 -22 32 0 z" fill="#faf7eb" stroke="var(--ink)" stroke-width="2"/>
<!-- 放大镜（塞在小人手边表示在检索） -->
<circle cx="424" cy="352" r="7" fill="none" stroke="var(--ink)" stroke-width="2"/>
<line x1="429" y1="358" x2="437" y2="366" stroke="var(--ink)" stroke-width="2.4" stroke-linecap="round"/>

<!-- 文件夹 -->
<path data-rough d="M700 340 h16 l5 6 h23 v26 h-44 z" fill="#faf7eb" stroke="var(--ink)" stroke-width="1.8"/>
<!-- 纸箱（牛皮纸棕 fill） -->
<path data-rough d="M760 350 l30 -8 30 8 v24 l-30 8 -30 -8 z" fill="#e9dac1" stroke="var(--ink)" stroke-width="1.8"/>
<line x1="790" y1="342" x2="790" y2="374" stroke="var(--ink)" stroke-width="1.4"/>
<!-- 月亮（Dream/夜间任务；可挂 .spin 微转） -->
<path d="M900 330 a12 12 0 1 0 10 18 a9 9 0 0 1 -10 -18 z" fill="var(--ink)"/>
<!-- 齿轮 = 圆 + 4 短齿；勾 = 折线；叉 = 两斜线；笔记本电脑 = 梯形 + 屏幕矩形 -->
```

## 5. 连线：微弯箭头 / 大回环 / 虚线弱关联

`<defs>` 里放一个箭头 marker（ink 实心小三角）：

```html
<defs>
  <marker id="arr" viewBox="0 0 10 8" refX="9" refY="4"
          markerWidth="8" markerHeight="6.5" orient="auto-start-reverse">
    <path d="M0 0 L10 4 L0 8 Z" fill="var(--ink)"/>
  </marker>
</defs>

<!-- 主流程：浅弧，不要笔直（手绘图没有直线） -->
<path data-rough id="e1" d="M410 333 Q447 328 486 334" fill="none" stroke="var(--ink)"
      stroke-width="2.0" marker-end="url(#arr)"/>
<text x="448" y="320" font-size="14" text-anchor="middle">线上标签</text>

<!-- 大回环：绕版面外侧的长弧，收尾点题（如 "Better Next Run"），圆点沿它跑 -->
<path data-rough data-roughness="2" d="M300 760 C120 700 100 260 300 120" fill="none"
      stroke="var(--ink)" stroke-width="2.2" marker-end="url(#arr)"/>

<!-- 核心迭代回环：实线弧（循环是主流程时不要用虚线弱化它） -->
<path data-rough d="M900 420 Q760 500 620 430" fill="none" stroke="var(--ink)"
      stroke-width="2.0" marker-end="url(#arr)"/>

<!-- 偶发降级/弱关联：才用虚线弧 -->
<path data-rough d="M900 300 Q780 350 660 310 " fill="none" stroke="var(--ink)"
      stroke-width="1.6" stroke-dasharray="7 6" marker-end="url(#arr)"/>

<!-- 分支：一出二（同一起点两条弧，各自带箭头、标签、圆点） -->
<path data-rough d="M420 330 Q470 300 520 292" fill="none" stroke="var(--ink)" stroke-width="2.0" marker-end="url(#arr)"/>
<path data-rough d="M420 336 Q470 366 520 374" fill="none" stroke="var(--ink)" stroke-width="2.0" marker-end="url(#arr)"/>
<!-- 汇聚：二入一 = 两条弧指向同一节点边缘的不同锚点，反向同理 -->

<!-- 环形轨道：节点绕环排布时，一条闭合椭圆弧当"传送带"，多个圆点错开在上面转 -->
<path data-rough id="orbit" d="M600 470 a170 90 0 1 0 0.1 0" fill="none"
      stroke="var(--ink)" stroke-width="2.2"/>
```

- 箭头指到目标边缘外 2px，别扎进卡片里。
- **流动拓扑跟内容走**：分支、汇聚、往返、跨区块长弧、环形轨道都是常规手段。
  一张图的连线如果全是同向平行线，先怀疑是拓扑画错了，不是内容真的这么单调。

## 6. 流动圆点（动画的灵魂）

圆点是独立 `<circle>`，用 CSS `offset-path` 沿**同一条 `d` 字符串**跑；
黑墨线上必须带 paper 色 halo 才看得清：

```html
<!-- --t 按路径长度选档：目标速度 80~150px/s（短线 loop/3≈1000ms，中长线 loop/2，长弧 loop） -->
<circle class="dot" r="4.5" fill="#5f7a4a" stroke="var(--paper)" stroke-width="2.5"
        style="offset-path: path('M410 333 Q447 328 486 334'); --t: calc(var(--loop) / 3)"/>
```

```css
.dot { offset-rotate: 0deg; transform-box: fill-box; transform-origin: center;
       animation: travel var(--t, var(--loop)) linear infinite,
                  breathe calc(var(--loop) / 4) ease-in-out infinite; }
@keyframes travel { from { offset-distance: 0%; } to { offset-distance: 100%; } }
@keyframes breathe { 50% { transform: scale(1.35); } }  /* 呼吸让点"活"起来 */
/* 多条线负延迟错开（用显式类，别用 nth-of-type，多区块下计数会乱） */
.d2 { animation-delay: calc(var(--loop) / -3); }
.d3 { animation-delay: calc(var(--loop) * -2 / 3); }
```

- **时长必须仍是 loop 的整数分之一**（loop/2、loop/3、loop/4），否则 GIF 循环有接缝；
  在这个约束里选最接近目标速度的档。一圈 3s 爬一条 50px 短线的点是死的。
- 圆点颜色 = 所在区块的 dot token（style-guide 色板）。
- **凡有"流动"语义的路径都放圆点**：主流程、回环（沿弧转回去才有"循环起来"的感觉）、
  分支两臂、跨区块长弧、环形轨道（放 2~3 个错开）。不放的只有标注框的引出虚线。
- 返回方向的流动不用重写路径：同一条 `d` 加 `animation-direction: reverse` 即可
  （如双向同步的去/回两个点）。
- `offset-path` 的 `d` 必须和连线的 `d` 逐字符一致，改线时同步改。

## 7. 图标微动效（挑 2~4 处）

```css
.spin { transform-box: fill-box; transform-origin: center;
        animation: spin var(--loop) linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.tick { stroke-dasharray: 26; animation: draw var(--loop) ease-in-out infinite; }
@keyframes draw { 0%{stroke-dashoffset:26} 40%,70%{stroke-dashoffset:0} 100%{stroke-dashoffset:-26} }

.blink { animation: blink calc(var(--loop) / 4) steps(2) infinite; }
@keyframes blink { 50% { opacity: 0; } }

/* ✦ 呼吸脉冲 */
.pulse { transform-box: fill-box; transform-origin: center;
         animation: pulse calc(var(--loop) / 2) ease-in-out infinite; }
@keyframes pulse { 50% { transform: scale(1.25) rotate(10deg); } }
```

只用 `transform/opacity/stroke-dashoffset`，时长限定 loop 的整数分之一（无缝循环）。

## 8. 引用/命令框

```html
<rect data-rough x="330" y="430" width="640" height="40" rx="8" fill="#faf7eb"
      stroke="var(--ink)" stroke-width="1.4" stroke-dasharray="4 4"/>
<text class="mono" x="650" y="456" font-size="16" text-anchor="middle">$ command --example</text>
```

## 9. 自检渲染（写完必做）

有显示环境 `open diagram.html`；无头环境用 scripts/ 里装好的 playwright-core
截 PNG 后用 Read 看图。动画正确性以浏览器实际播放为准，不要只靠读代码。
