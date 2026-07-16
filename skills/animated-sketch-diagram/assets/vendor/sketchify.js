// sketchify.js — 把带 data-rough 的 SVG 元素替换成 rough.js 手绘版本
// 支持 rect(含 rx)/line/circle/ellipse/path；原元素保留（隐藏描边）以保住 marker 箭头和 offset-path 引用
function sketchify(root = document) {
  root.querySelectorAll('svg').forEach(svg => {
    const rc = rough.svg(svg);
    let seed = 7; // 固定种子：每次打开抖动一致，GIF 帧间不闪
    svg.querySelectorAll('[data-rough]').forEach(el => {
      const attr = n => el.getAttribute(n);
      const stroke = attr('stroke') || 'none';
      const fill = attr('fill');
      const o = {
        roughness: +(el.dataset.roughness || 1.1),
        bowing: 0.9,
        seed: seed++,
        stroke,
        strokeWidth: +(attr('stroke-width') || 1.5),
        fill: fill && fill !== 'none' ? fill : undefined,
        fillStyle: 'solid',
        strokeLineDash: (attr('stroke-dasharray') || '').split(/[ ,]+/).filter(Boolean).map(Number),
      };
      const num = n => +attr(n);
      let node;
      switch (el.tagName) {
        case 'rect': {
          const x = num('x'), y = num('y'), w = num('width'), h = num('height');
          const r = Math.min(num('rx') || 0, w / 2, h / 2);
          node = r > 0
            ? rc.path(`M${x + r} ${y} h${w - 2 * r} a${r} ${r} 0 0 1 ${r} ${r} v${h - 2 * r} a${r} ${r} 0 0 1 -${r} ${r} h${-(w - 2 * r)} a${r} ${r} 0 0 1 -${r} -${r} v${-(h - 2 * r)} a${r} ${r} 0 0 1 ${r} -${r} z`, o)
            : rc.rectangle(x, y, w, h, o);
          break;
        }
        case 'line': node = rc.line(num('x1'), num('y1'), num('x2'), num('y2'), o); break;
        case 'circle': node = rc.circle(num('cx'), num('cy'), 2 * num('r'), o); break;
        case 'ellipse': node = rc.ellipse(num('cx'), num('cy'), 2 * num('rx'), 2 * num('ry'), o); break;
        case 'path': node = rc.path(attr('d'), o); break;
        default: return;
      }
      el.parentNode.insertBefore(node, el); // 原元素在上层：marker 箭头盖在手绘线之上
      el.setAttribute('fill', 'none');
      el.setAttribute('stroke', 'transparent'); // transparent 而非 none：保证 marker 仍渲染
    });
  });
}
