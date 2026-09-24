import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { executeItems, getNumber, textItem, textProperties } from '../common';

export class IflyAnimatedSketch implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek Animated Sketch', name: 'iflyAnimatedSketch', icon: 'fa:picture-o', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek Animated Sketch' },
    description: 'Render existing static HTML/SVG/CSS diagrams to GIF locally without API credentials.',
    inputs: ['main'], outputs: ['main'], properties: [
      ...textProperties.map(property => property.name === 'text' ? {
        ...property, displayName: 'Diagram HTML',
        description: 'Restricted HTML/SVG/CSS, up to 256 KiB. Scripts and external resources are unsupported.',
      } : property),
      { displayName: 'Width', name: 'width', type: 'number', default: 800, typeOptions: { minValue: 64, maxValue: 1600 } },
      { displayName: 'Height', name: 'height', type: 'number', default: 500, typeOptions: { minValue: 64, maxValue: 1200 } },
      { displayName: 'Frames Per Second', name: 'fps', type: 'number', default: 10, typeOptions: { minValue: 1, maxValue: 25 } },
      {
        displayName: 'Duration (ms)', name: 'durationMs', type: 'number', default: 2000,
        typeOptions: { minValue: 100, maxValue: 5000 }, description: 'Match the diagram CSS animation loop duration.',
      },
      { displayName: 'Scale', name: 'scale', type: 'options', default: 1, options: [
        { name: '1x', value: 1 }, { name: '2x', value: 2 },
      ] },
    ],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index) => ({
      ...textItem(this, index, 'animated-sketch-diagram', 'renderHtmlToGif', {
        width: getNumber(this, 'width', index, 800), height: getNumber(this, 'height', index, 500),
        fps: getNumber(this, 'fps', index, 10), durationMs: getNumber(this, 'durationMs', index, 2000),
        scale: getNumber(this, 'scale', index, 1),
      }),
      outputBinaryPrefix: 'image',
    }));
  }
}
