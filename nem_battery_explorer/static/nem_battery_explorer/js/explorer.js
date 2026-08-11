(function () {
  'use strict';

  const intervals = JSON.parse(document.getElementById('bex-interval-data').textContent);
  const opportunity = JSON.parse(document.getElementById('bex-opportunity-data').textContent);
  const periodData = JSON.parse(document.getElementById('bex-period-data').textContent);
  const comparisons = JSON.parse(document.getElementById('bex-comparison-data').textContent);
  const fleetRegions = JSON.parse(document.getElementById('bex-fleet-regions').textContent);
  const fleetPoints = JSON.parse(document.getElementById('bex-fleet-points').textContent);
  const marketTrend = JSON.parse(document.getElementById('bex-market-trend').textContent);
  const config = window.BEX_CONFIG || {};
  const NS = 'http://www.w3.org/2000/svg';

  function svgNode(name, attrs, text) {
    const node = document.createElementNS(NS, name);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function svgCanvas(width, height) {
    return svgNode('svg', { viewBox: `0 0 ${width} ${height}`, 'aria-hidden': 'true' });
  }

  function addText(svg, x, y, text, anchor) {
    svg.appendChild(svgNode('text', { x, y, 'text-anchor': anchor || 'start' }, text));
  }

  function niceNumber(value) {
    const absolute = Math.abs(value);
    if (absolute >= 1000) return `${(value / 1000).toFixed(1)}k`;
    if (absolute >= 100) return value.toFixed(0);
    return value.toFixed(1);
  }

  function renderPeriodOperation(mode) {
    const host = document.getElementById('period-operation-chart');
    if (!host || !periodData.length) return;
    mode = mode || 'energy';
    const width = 1000, height = 360;
    const margin = { left: 58, right: 72, top: 25, bottom: 52 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const slot = innerW / periodData.length;
    const x = index => margin.left + (index + .5) * slot;
    const labelStep = Math.max(1, Math.ceil(periodData.length / 10));
    const svg = svgCanvas(width, height);

    if (mode === 'value') {
      const values = periodData.flatMap(row => [Number(row.energy_value) || 0, Number(row.fcas_value) || 0]);
      const minValue = Math.min(0, ...values), maxValue = Math.max(1, ...values);
      const maxCycles = Math.max(.01, ...periodData.map(row => Number(row.cycles) || 0));
      const yValue = value => margin.top + (maxValue - value) / (maxValue - minValue || 1) * innerH;
      const yCycles = value => margin.top + (maxCycles - value) / maxCycles * innerH;
      const zeroY = yValue(0);
      for (let i = 0; i <= 4; i += 1) {
        const gridY = margin.top + i / 4 * innerH;
        svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: gridY, y2: gridY, stroke: '#d8d1c5', 'stroke-width': .7 }));
        addText(svg, margin.left - 8, gridY + 4, `$${niceNumber(maxValue - i / 4 * (maxValue - minValue))}`, 'end');
        addText(svg, width - margin.right + 8, gridY + 4, (maxCycles - i / 4 * maxCycles).toFixed(2));
      }
      const barWidth = Math.max(4, Math.min(25, slot * .28));
      periodData.forEach((row, index) => {
        [[row.energy_value, -1, '#287a67', 'energy'], [row.fcas_value, 1, '#c79a3b', 'FCAS']].forEach(([value, side, fill, label]) => {
          const y = yValue(Number(value) || 0);
          const rect = svgNode('rect', { x: x(index) + side * barWidth * .58 - barWidth / 2, y: Math.min(y, zeroY), width: barWidth, height: Math.max(Math.abs(zeroY - y), .6), rx: 2, fill, opacity: .86 });
          rect.appendChild(svgNode('title', {}, `${row.label} · ${label} $${Math.round(value || 0).toLocaleString()}`));
          svg.appendChild(rect);
        });
        if (index % labelStep === 0 || index === periodData.length - 1) addText(svg, x(index), height - 22, row.label, 'middle');
      });
      const cyclePath = periodData.map((row, index) => `${index ? 'L' : 'M'}${x(index).toFixed(2)},${yCycles(Number(row.cycles) || 0).toFixed(2)}`).join(' ');
      svg.appendChild(svgNode('path', { d: cyclePath, fill: 'none', stroke: '#2e5870', 'stroke-width': 2.4, 'stroke-linejoin': 'round' }));
      periodData.forEach((row, index) => {
        const dot = svgNode('circle', { cx: x(index), cy: yCycles(Number(row.cycles) || 0), r: 3.5, fill: '#fffdf8', stroke: '#2e5870', 'stroke-width': 2 });
        dot.appendChild(svgNode('title', {}, `${row.label} · ${Number(row.cycles || 0).toFixed(2)} equivalent cycles`));
        svg.appendChild(dot);
      });
      addText(svg, margin.left, 15, 'Observable value ($)');
      addText(svg, width - margin.right, 15, 'Equivalent cycles', 'end');
      host.replaceChildren(svg);
      return;
    }

    const maxEnergy = Math.max(1, ...periodData.flatMap(row => [row.discharge_mwh || 0, row.charge_mwh || 0]));
    const values = periodData.map(row => Number(row.observable_value) || 0);
    let minValue = Math.min(0, ...values), maxValue = Math.max(1, ...values);
    if (minValue === maxValue) maxValue += 1;
    const yEnergy = value => margin.top + (maxEnergy - value) / (maxEnergy * 2) * innerH;
    const yValue = value => margin.top + (maxValue - value) / (maxValue - minValue) * innerH;

    for (let i = 0; i <= 4; i += 1) {
      const gridY = margin.top + i / 4 * innerH;
      svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: gridY, y2: gridY, stroke: '#d8d1c5', 'stroke-width': .7 }));
      addText(svg, margin.left - 8, gridY + 4, niceNumber(maxEnergy - i / 4 * maxEnergy * 2), 'end');
    }
    const zeroY = yEnergy(0);
    svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: zeroY, y2: zeroY, stroke: '#657179', 'stroke-width': 1 }));
    const barWidth = Math.max(4, Math.min(38, slot * .5));
    periodData.forEach((row, index) => {
      const dischargeTop = yEnergy(row.discharge_mwh || 0);
      const discharge = svgNode('rect', { x: x(index) - barWidth / 2, y: dischargeTop, width: barWidth, height: Math.max(zeroY - dischargeTop, .5), rx: 2, fill: '#287a67', opacity: .88 });
      discharge.appendChild(svgNode('title', {}, `${row.label} · discharged ${Number(row.discharge_mwh || 0).toFixed(1)} MWh`));
      svg.appendChild(discharge);
      const chargeBottom = yEnergy(-(row.charge_mwh || 0));
      const charge = svgNode('rect', { x: x(index) - barWidth / 2, y: zeroY, width: barWidth, height: Math.max(chargeBottom - zeroY, .5), rx: 2, fill: '#c96e3a', opacity: .78 });
      charge.appendChild(svgNode('title', {}, `${row.label} · charged ${Number(row.charge_mwh || 0).toFixed(1)} MWh`));
      svg.appendChild(charge);
    });
    const valuePath = periodData.map((row, index) => `${index ? 'L' : 'M'}${x(index).toFixed(2)},${yValue(row.observable_value || 0).toFixed(2)}`).join(' ');
    svg.appendChild(svgNode('path', { d: valuePath, fill: 'none', stroke: '#2e5870', 'stroke-width': 2.4, 'stroke-linejoin': 'round' }));
    periodData.forEach((row, index) => {
      const dot = svgNode('circle', { cx: x(index), cy: yValue(row.observable_value || 0), r: 3.5, fill: '#fffdf8', stroke: '#2e5870', 'stroke-width': 2 });
      dot.appendChild(svgNode('title', {}, `${row.label} · $${Math.round(row.observable_value || 0).toLocaleString()} observable value`));
      svg.appendChild(dot);
      if (index % labelStep === 0 || index === periodData.length - 1) addText(svg, x(index), height - 22, row.label, 'middle');
    });
    addText(svg, margin.left, 15, 'MWh');
    addText(svg, width - margin.right, 15, 'Observable value ($)', 'end');
    addText(svg, width - margin.right + 8, margin.top + 4, `$${niceNumber(maxValue)}`);
    addText(svg, width - margin.right + 8, height - margin.bottom, `$${niceNumber(minValue)}`);
    host.replaceChildren(svg);
  }

  function renderPeriodOpportunity(mode) {
    const host = document.getElementById('period-opportunity-chart');
    const rows = periodData.filter(row => row.benchmark_value !== null && row.benchmark_value !== undefined);
    if (!host || !rows.length) return;
    mode = mode || 'dollars';
    const width = 1000, height = 350;
    const margin = { left: 64, right: 68, top: 28, bottom: 52 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const values = rows.flatMap(row => [Number(row.energy_value) || 0, Number(row.benchmark_value) || 0]);
    const minValue = Math.min(0, ...values), maxValue = Math.max(1, ...values);
    const captureCeiling = Math.max(120, ...rows.map(row => Number(row.capture_pct) || 0));
    const slot = innerW / rows.length;
    const x = index => margin.left + (index + .5) * slot;
    const yValue = value => margin.top + (maxValue - value) / (maxValue - minValue || 1) * innerH;
    const yCapture = value => margin.top + (captureCeiling - value) / captureCeiling * innerH;
    const zeroY = yValue(0);
    const svg = svgCanvas(width, height);

    if (mode === 'capture') {
      const captureRows = rows
        .map((row, index) => ({ row, index }))
        .filter(item => item.row.capture_pct !== null && item.row.capture_pct !== undefined);
      const maxCapture = Math.max(125, ...captureRows.map(item => Number(item.row.capture_pct)));
      const y = value => margin.top + (maxCapture - value) / maxCapture * innerH;
      for (let i = 0; i <= 5; i += 1) {
        const value = maxCapture - i / 5 * maxCapture;
        const gridY = y(value);
        svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: gridY, y2: gridY, stroke: '#d8d1c5', 'stroke-width': .7 }));
        addText(svg, margin.left - 8, gridY + 4, `${Math.round(value)}%`, 'end');
      }
      const targetY = y(100);
      svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: targetY, y2: targetY, stroke: '#c96e3a', 'stroke-width': 1.5, 'stroke-dasharray': '6 5' }));
      addText(svg, width - margin.right, targetY - 7, '100% hindsight reference', 'end');
      const labelStep = Math.max(1, Math.ceil(rows.length / 10));
      captureRows.forEach(item => {
        const value = Number(item.row.capture_pct);
        svg.appendChild(svgNode('line', { x1: x(item.index), x2: x(item.index), y1: targetY, y2: y(value), stroke: value >= 100 ? '#287a67' : '#c96e3a', 'stroke-width': Math.max(4, Math.min(14, slot * .16)), opacity: .45 }));
        const dot = svgNode('circle', { cx: x(item.index), cy: y(value), r: 6, fill: value >= 100 ? '#287a67' : '#c96e3a', stroke: '#fffdf8', 'stroke-width': 2 });
        dot.appendChild(svgNode('title', {}, `${item.row.label} · ${value.toFixed(0)}% capture`));
        svg.appendChild(dot);
        if (item.index % labelStep === 0 || item.index === rows.length - 1) addText(svg, x(item.index), height - 22, item.row.label, 'middle');
      });
      addText(svg, margin.left, 16, 'Public-data capture ratio');
      host.replaceChildren(svg);
      return;
    }
    for (let i = 0; i <= 4; i += 1) {
      const gridY = margin.top + i / 4 * innerH;
      svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: gridY, y2: gridY, stroke: '#d8d1c5', 'stroke-width': .7 }));
      addText(svg, margin.left - 8, gridY + 4, `$${niceNumber(maxValue - i / 4 * (maxValue - minValue))}`, 'end');
      addText(svg, width - margin.right + 8, gridY + 4, `${Math.round(captureCeiling - i / 4 * captureCeiling)}%`);
    }
    const barWidth = Math.max(4, Math.min(24, slot * .26));
    const labelStep = Math.max(1, Math.ceil(rows.length / 10));
    rows.forEach((row, index) => {
      [[row.energy_value, -1, '#287a67', 'actual'], [row.benchmark_value, 1, '#c79a3b', 'benchmark']].forEach(([value, side, fill, label]) => {
        const y = yValue(Number(value) || 0);
        const rect = svgNode('rect', { x: x(index) + side * barWidth * .58 - barWidth / 2, y: Math.min(y, zeroY), width: barWidth, height: Math.max(Math.abs(zeroY - y), .6), rx: 2, fill, opacity: .86 });
        rect.appendChild(svgNode('title', {}, `${row.label} · ${label} $${Math.round(value || 0).toLocaleString()}`));
        svg.appendChild(rect);
      });
      if (index % labelStep === 0 || index === rows.length - 1) addText(svg, x(index), height - 22, row.label, 'middle');
    });
    const captureRows = rows
      .map((row, index) => ({ row, index }))
      .filter(item => item.row.capture_pct !== null && item.row.capture_pct !== undefined);
    if (captureRows.length) {
      const capturePath = captureRows.map((item, pointIndex) => `${pointIndex ? 'L' : 'M'}${x(item.index).toFixed(2)},${yCapture(Number(item.row.capture_pct)).toFixed(2)}`).join(' ');
      svg.appendChild(svgNode('path', { d: capturePath, fill: 'none', stroke: '#2e5870', 'stroke-width': 2.2, 'stroke-linejoin': 'round' }));
      captureRows.forEach(item => {
        const dot = svgNode('circle', { cx: x(item.index), cy: yCapture(Number(item.row.capture_pct)), r: 3.5, fill: '#fffdf8', stroke: '#2e5870', 'stroke-width': 2 });
        dot.appendChild(svgNode('title', {}, `${item.row.label} · ${Number(item.row.capture_pct).toFixed(0)}% capture`));
        svg.appendChild(dot);
      });
    }
    addText(svg, margin.left, 16, 'Energy value ($)');
    addText(svg, width - margin.right, 16, 'Capture ratio', 'end');
    host.replaceChildren(svg);
  }

  function renderDispatch() {
    const host = document.getElementById('dispatch-chart');
    const width = 1000, height = 360;
    const margin = { left: 55, right: 64, top: 22, bottom: 36 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const svg = svgCanvas(width, height);
    const power = intervals.map(row => row.scada_mw);
    const prices = intervals.map(row => row.rrp);
    const maxMw = Math.max(1, ...power.filter(v => v !== null).map(Math.abs));
    let minPrice = Math.min(...prices.filter(v => v !== null));
    let maxPrice = Math.max(...prices.filter(v => v !== null));
    if (minPrice === maxPrice) { minPrice -= 1; maxPrice += 1; }
    const x = index => margin.left + index / Math.max(intervals.length - 1, 1) * innerW;
    const yMw = value => margin.top + (maxMw - value) / (2 * maxMw) * innerH;
    const yPrice = value => margin.top + (maxPrice - value) / (maxPrice - minPrice) * innerH;

    for (let i = 0; i <= 4; i += 1) {
      const y = margin.top + i / 4 * innerH;
      svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: y, y2: y, stroke: '#d8d1c5', 'stroke-width': .7 }));
      addText(svg, margin.left - 8, y + 4, niceNumber(maxMw - i / 4 * 2 * maxMw), 'end');
    }
    const zeroY = yMw(0);
    svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: zeroY, y2: zeroY, stroke: '#657179', 'stroke-width': 1.1 }));

    const barWidth = Math.max(1.3, innerW / intervals.length * .72);
    intervals.forEach((row, index) => {
      if (row.scada_mw === null) return;
      const barY = yMw(Math.max(row.scada_mw, 0));
      const barBottom = yMw(Math.min(row.scada_mw, 0));
      const rect = svgNode('rect', {
        x: x(index) - barWidth / 2,
        y: barY,
        width: barWidth,
        height: Math.max(barBottom - barY, .6),
        fill: row.scada_mw >= 0 ? '#287a67' : '#c96e3a',
        opacity: .86,
      });
      rect.appendChild(svgNode('title', {}, `${row.time} · ${row.scada_mw.toFixed(1)} MW · $${row.rrp.toFixed(2)}/MWh`));
      svg.appendChild(rect);
    });

    const path = intervals.map((row, index) => {
      if (row.rrp === null) return '';
      return `${index === 0 ? 'M' : 'L'}${x(index).toFixed(2)},${yPrice(row.rrp).toFixed(2)}`;
    }).join(' ');
    svg.appendChild(svgNode('path', { d: path, fill: 'none', stroke: '#2e5870', 'stroke-width': 2.2, 'stroke-linejoin': 'round' }));
    addText(svg, width - margin.right + 8, margin.top + 4, `$${niceNumber(maxPrice)}`, 'start');
    addText(svg, width - margin.right + 8, height - margin.bottom, `$${niceNumber(minPrice)}`, 'start');
    addText(svg, margin.left, 13, 'MW');
    addText(svg, width - margin.right, 13, '$/MWh', 'end');

    [0, 72, 144, 216, intervals.length - 1].forEach(index => {
      if (!intervals[index]) return;
      addText(svg, x(index), height - 12, intervals[index].time, index === 0 ? 'start' : index === intervals.length - 1 ? 'end' : 'middle');
    });
    host.replaceChildren(svg);
  }

  function renderStorage() {
    const host = document.getElementById('storage-chart');
    const width = 1000, height = 270;
    const margin = { left: 55, right: 24, top: 22, bottom: 34 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const values = intervals.map(row => row.storage_mwh);
    const observed = values.filter(value => value !== null);
    const ceiling = Math.max(config.capacityMwh || 0, ...observed, 1) * 1.05;
    const floor = Math.min(0, ...observed);
    const svg = svgCanvas(width, height);
    const x = index => margin.left + index / Math.max(intervals.length - 1, 1) * innerW;
    const y = value => margin.top + (ceiling - value) / (ceiling - floor) * innerH;

    for (let i = 0; i <= 4; i += 1) {
      const lineY = margin.top + i / 4 * innerH;
      svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: lineY, y2: lineY, stroke: '#d8d1c5', 'stroke-width': .7 }));
      addText(svg, margin.left - 8, lineY + 4, niceNumber(ceiling - i / 4 * (ceiling - floor)), 'end');
    }
    if (config.capacityMwh) {
      const capacityY = y(config.capacityMwh);
      svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: capacityY, y2: capacityY, stroke: '#c96e3a', 'stroke-width': 1.2, 'stroke-dasharray': '6 5' }));
      addText(svg, width - margin.right, capacityY - 5, 'public capacity', 'end');
    }

    let segment = [];
    const flush = () => {
      if (segment.length > 1) {
        const d = segment.map((point, index) => `${index ? 'L' : 'M'}${point[0]},${point[1]}`).join(' ');
        svg.appendChild(svgNode('path', { d, fill: 'none', stroke: '#287a67', 'stroke-width': 2.6, 'stroke-linejoin': 'round' }));
      }
      segment = [];
    };
    intervals.forEach((row, index) => {
      if (row.storage_mwh === null) { flush(); return; }
      segment.push([x(index).toFixed(2), y(row.storage_mwh).toFixed(2)]);
    });
    flush();
    [0, 72, 144, 216, intervals.length - 1].forEach(index => {
      if (intervals[index]) addText(svg, x(index), height - 10, intervals[index].time, index === 0 ? 'start' : index === intervals.length - 1 ? 'end' : 'middle');
    });
    addText(svg, margin.left, 13, 'MWh');
    host.replaceChildren(svg);
  }

  function renderHeatmap() {
    const host = document.getElementById('cycle-heatmap');
    if (!host) return;
    const maxCycles = Math.max(.01, ...periodData.map(day => day.cycles || 0));
    periodData.forEach(day => {
      const link = document.createElement('div');
      link.className = 'bex-heatmap__cell';
      const intensity = Math.max(.08, (day.cycles || 0) / maxCycles);
      const alpha = .12 + intensity * .68;
      link.style.backgroundColor = `rgba(40, 122, 103, ${alpha.toFixed(2)})`;
      link.title = `${day.label}: ${(day.cycles || 0).toFixed(2)} cycles · $${Math.round(day.observable_value || 0).toLocaleString()} · ${day.quality}`;
      const label = document.createElement('span');
      label.textContent = day.label;
      const value = document.createElement('strong');
      value.textContent = (day.cycles || 0).toFixed(2);
      link.append(label, value);
      host.appendChild(link);
    });
  }

  function renderDonut() {
    const donut = document.getElementById('value-donut');
    if (!donut) return;
    const energy = Math.max(Number(config.energyValue) || 0, 0);
    const fcas = Math.max(Number(config.fcasValue) || 0, 0);
    const share = energy + fcas > 0 ? energy / (energy + fcas) * 100 : 50;
    donut.style.setProperty('--energy-share', `${share.toFixed(1)}%`);
  }

  function renderComparison() {
    const host = document.getElementById('comparison-chart');
    const maxValue = Math.max(1, ...comparisons.map(row => Math.max(row.value, 0)));
    comparisons.forEach(row => {
      const link = document.createElement('a');
      const url = new URL(window.location.href);
      url.searchParams.set('asset', row.slug);
      link.href = url.toString();
      link.className = `bex-compare-row${row.selected ? ' is-selected' : ''}`;

      const name = document.createElement('div');
      name.className = 'bex-compare-row__name';
      const strong = document.createElement('strong');
      strong.textContent = row.asset;
      const region = document.createElement('span');
      region.textContent = row.region;
      name.append(strong, region);

      const bar = document.createElement('div');
      bar.className = 'bex-compare-bar';
      const fill = document.createElement('i');
      fill.style.width = `${Math.max(row.value, 0) / maxValue * 100}%`;
      bar.appendChild(fill);

      const gross = document.createElement('div');
      gross.className = 'bex-compare-stat';
      gross.innerHTML = `<span>Gross value</span>$${Math.round(row.value).toLocaleString()}`;
      const cycles = document.createElement('div');
      cycles.className = 'bex-compare-stat';
      cycles.innerHTML = `<span>Cycles</span>${Number(row.cycles).toFixed(2)}`;
      link.append(name, bar, gross, cycles);
      host.appendChild(link);
    });
  }

  function renderOpportunity() {
    const host = document.getElementById('opportunity-chart');
    if (!host || !opportunity.length) return;
    const width = 1000, height = 370;
    const margin = { left: 55, right: 64, top: 22, bottom: 38 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const svg = svgCanvas(width, height);
    const dispatch = opportunity.flatMap(row => [row.actual_mw, row.benchmark_mw]).filter(value => value !== null);
    const prices = opportunity.map(row => row.rrp).filter(value => value !== null);
    const maxMw = Math.max(1, ...dispatch.map(Math.abs));
    let minPrice = Math.min(...prices), maxPrice = Math.max(...prices);
    if (minPrice === maxPrice) { minPrice -= 1; maxPrice += 1; }
    const x = index => margin.left + index / Math.max(opportunity.length - 1, 1) * innerW;
    const yMw = value => margin.top + (maxMw - value) / (2 * maxMw) * innerH;
    const yPrice = value => margin.top + (maxPrice - value) / (maxPrice - minPrice) * innerH;
    const slot = innerW / Math.max(opportunity.length, 1);

    opportunity.forEach((row, index) => {
      if (row.window === 'hold') return;
      svg.appendChild(svgNode('rect', {
        x: margin.left + index * slot,
        y: margin.top,
        width: slot + .5,
        height: innerH,
        fill: row.window === 'discharge' ? '#dcece4' : '#fae7dc',
        opacity: .72,
      }));
    });
    for (let i = 0; i <= 4; i += 1) {
      const y = margin.top + i / 4 * innerH;
      svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: y, y2: y, stroke: '#d8d1c5', 'stroke-width': .7 }));
      addText(svg, margin.left - 8, y + 4, niceNumber(maxMw - i / 4 * 2 * maxMw), 'end');
    }
    const zeroY = yMw(0);
    svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: zeroY, y2: zeroY, stroke: '#657179', 'stroke-width': 1 }));
    const barWidth = Math.max(1.2, slot * .62);
    opportunity.forEach((row, index) => {
      if (row.actual_mw === null) return;
      const top = yMw(Math.max(row.actual_mw, 0));
      const bottom = yMw(Math.min(row.actual_mw, 0));
      const rect = svgNode('rect', {
        x: x(index) - barWidth / 2,
        y: top,
        width: barWidth,
        height: Math.max(bottom - top, .5),
        fill: row.actual_mw >= 0 ? '#287a67' : '#c96e3a',
        opacity: .45,
      });
      rect.appendChild(svgNode('title', {}, `${row.time} · actual ${row.actual_mw.toFixed(1)} MW · benchmark ${row.benchmark_mw.toFixed(1)} MW · $${row.rrp.toFixed(2)}/MWh`));
      svg.appendChild(rect);
    });
    const benchmarkPath = opportunity.map((row, index) => `${index ? 'L' : 'M'}${x(index).toFixed(2)},${yMw(row.benchmark_mw).toFixed(2)}`).join(' ');
    svg.appendChild(svgNode('path', { d: benchmarkPath, fill: 'none', stroke: '#15323a', 'stroke-width': 2.2, 'stroke-linejoin': 'round' }));
    const pricePath = opportunity.map((row, index) => `${index ? 'L' : 'M'}${x(index).toFixed(2)},${yPrice(row.rrp).toFixed(2)}`).join(' ');
    svg.appendChild(svgNode('path', { d: pricePath, fill: 'none', stroke: '#c99a32', 'stroke-width': 1.6, 'stroke-linejoin': 'round', opacity: .9 }));
    addText(svg, margin.left, 13, 'MW');
    addText(svg, width - margin.right, 13, '$/MWh', 'end');
    addText(svg, width - margin.right + 8, margin.top + 4, `$${niceNumber(maxPrice)}`);
    addText(svg, width - margin.right + 8, height - margin.bottom, `$${niceNumber(minPrice)}`);
    [0, 72, 144, 216, opportunity.length - 1].forEach(index => {
      if (opportunity[index]) addText(svg, x(index), height - 12, opportunity[index].time, index === 0 ? 'start' : index === opportunity.length - 1 ? 'end' : 'middle');
    });
    host.replaceChildren(svg);
  }

  function renderFleetRegions() {
    const host = document.getElementById('fleet-region-map');
    if (!host) return;
    const title = document.createElement('p');
    title.className = 'bex-region-map__title';
    title.textContent = 'NEM state coverage · tile map';
    host.appendChild(title);
    const grid = document.createElement('div');
    grid.className = 'bex-region-grid';
    const key = document.createElement('div');
    key.className = 'bex-region-grid__key';
    key.innerHTML = '<strong>NEM</strong><span>Coverage by registered MW</span><small>Tiles follow the east-coast market geography, not physical scale.</small>';
    grid.appendChild(key);
    fleetRegions.forEach(region => {
      const card = document.createElement('article');
      card.className = `bex-region-node bex-region-node--${region.region.toLowerCase()}`;
      const pct = Math.max(0, Math.min(100, region.coverage_pct));
      card.innerHTML = `<div><strong>${region.region.replace('1', '')}</strong><small>${region.label}</small></div><span>${Math.round(region.covered_mw).toLocaleString()} / ${Math.round(region.total_mw).toLocaleString()} MW</span><i><b style="width:${pct.toFixed(1)}%"></b></i><footer><b>${pct.toFixed(0)}% covered</b><small>${region.covered_assets} asset${region.covered_assets === 1 ? '' : 's'}</small></footer>`;
      grid.appendChild(card);
    });
    host.appendChild(grid);
  }

  function renderFleetLandscape() {
    const host = document.getElementById('fleet-landscape-chart');
    if (!host || !fleetPoints.length) return;
    const width = 620, height = 390;
    const margin = { left: 52, right: 24, top: 34, bottom: 48 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const maxDuration = Math.max(8, ...fleetPoints.map(point => point.duration));
    const maxMw = Math.max(700, ...fleetPoints.map(point => point.mw));
    const x = value => margin.left + value / maxDuration * innerW;
    const y = value => margin.top + (maxMw - value) / maxMw * innerH;
    const colors = { NSW1: '#2e5870', QLD1: '#c99a32', SA1: '#c96e3a', VIC1: '#287a67', TAS1: '#736b85' };
    const svg = svgCanvas(width, height);
    addText(svg, margin.left, 17, 'Power versus duration · largest in-service sites');
    for (let i = 0; i <= 4; i += 1) {
      const gridY = margin.top + i / 4 * innerH;
      svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: gridY, y2: gridY, stroke: '#d8d1c5', 'stroke-width': .7 }));
      addText(svg, margin.left - 8, gridY + 4, Math.round(maxMw - i / 4 * maxMw), 'end');
    }
    [0, 2, 4, 6, 8].forEach(value => {
      if (value > maxDuration) return;
      const gridX = x(value);
      svg.appendChild(svgNode('line', { x1: gridX, x2: gridX, y1: margin.top, y2: height - margin.bottom, stroke: '#e6dfd2', 'stroke-width': .6 }));
      addText(svg, gridX, height - 19, `${value}h`, value === 0 ? 'start' : 'middle');
    });
    fleetPoints.forEach(point => {
      const radius = 4 + Math.sqrt(point.mwh) / 8;
      const circle = svgNode('circle', {
        cx: x(point.duration), cy: y(point.mw), r: Math.min(radius, 18),
        fill: point.covered ? colors[point.region] : '#f7f3e9',
        stroke: colors[point.region], 'stroke-width': point.covered ? 2.2 : 1.4,
        opacity: point.covered ? .86 : .68,
      });
      circle.appendChild(svgNode('title', {}, `${point.name} · ${point.mw.toFixed(0)} MW · ${point.mwh.toFixed(0)} MWh · ${point.duration.toFixed(1)} hours${point.covered ? ' · in ChargeTrace' : ''}`));
      svg.appendChild(circle);
    });
    addText(svg, margin.left, height - 2, 'Duration (MWh ÷ MW)');
    addText(svg, 8, margin.top - 10, 'MW');
    host.replaceChildren(svg);
  }

  function renderMarketTrend() {
    const host = document.getElementById('market-trend-chart');
    if (!host || !marketTrend.length) return;
    const width = 1000, height = 350;
    const margin = { left: 58, right: 68, top: 32, bottom: 48 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const maxDischarge = 520, maxSpread = 150;
    const x = index => margin.left + (index + .5) / marketTrend.length * innerW;
    const yMw = value => margin.top + (maxDischarge - value) / maxDischarge * innerH;
    const ySpread = value => margin.top + (maxSpread - value) / maxSpread * innerH;
    const svg = svgCanvas(width, height);
    for (let i = 0; i <= 4; i += 1) {
      const gridY = margin.top + i / 4 * innerH;
      svg.appendChild(svgNode('line', { x1: margin.left, x2: width - margin.right, y1: gridY, y2: gridY, stroke: '#d8d1c5', 'stroke-width': .7 }));
      addText(svg, margin.left - 8, gridY + 4, Math.round(maxDischarge - i / 4 * maxDischarge), 'end');
      addText(svg, width - margin.right + 8, gridY + 4, `$${Math.round(maxSpread - i / 4 * maxSpread)}`);
    }
    const barWidth = innerW / marketTrend.length * .34;
    marketTrend.forEach((row, index) => {
      const top = yMw(row.average_discharge_mw);
      const rect = svgNode('rect', { x: x(index) - barWidth / 2, y: top, width: barWidth, height: height - margin.bottom - top, rx: 5, fill: '#287a67', opacity: .86 });
      rect.appendChild(svgNode('title', {}, `${row.quarter} · ${row.average_discharge_mw} MW average discharge · $${row.price_spread}/MWh spread · $${row.revenue_m}m revenue`));
      svg.appendChild(rect);
      addText(svg, x(index), top - 8, `${row.average_discharge_mw} MW`, 'middle');
      addText(svg, x(index), height - 22, row.quarter, 'middle');
      addText(svg, x(index), height - 5, `$${row.revenue_m.toFixed(1)}m revenue`, 'middle');
    });
    const spreadPath = marketTrend.map((row, index) => `${index ? 'L' : 'M'}${x(index)},${ySpread(row.price_spread)}`).join(' ');
    svg.appendChild(svgNode('path', { d: spreadPath, fill: 'none', stroke: '#c96e3a', 'stroke-width': 3 }));
    marketTrend.forEach((row, index) => {
      svg.appendChild(svgNode('circle', { cx: x(index), cy: ySpread(row.price_spread), r: 5, fill: '#fffaf0', stroke: '#c96e3a', 'stroke-width': 2.5 }));
      addText(svg, x(index), ySpread(row.price_spread) - 11, `$${row.price_spread}`, 'middle');
    });
    addText(svg, margin.left, 18, 'Average discharge (MW)');
    addText(svg, width - margin.right, 18, 'Captured spread ($/MWh)', 'end');
    host.replaceChildren(svg);
  }

  function wireChartModes(controlName, renderer, initialMode) {
    const controls = document.querySelector(`[data-chart-controls="${controlName}"]`);
    if (!controls) return;
    const legend = document.querySelector(`[data-chart-legend="${controlName}"]`);
    const activate = mode => {
      if (legend) {
        legend.querySelectorAll('[data-for-mode]').forEach(item => {
          item.hidden = item.dataset.forMode !== mode;
        });
      }
      renderer(mode);
    };
    controls.querySelectorAll('button').forEach(button => {
      button.addEventListener('click', () => {
        controls.querySelectorAll('button').forEach(candidate => {
          const active = candidate === button;
          candidate.classList.toggle('is-active', active);
          candidate.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        activate(button.dataset.chartMode);
      });
    });
    activate(initialMode);
  }

  wireChartModes('operation', renderPeriodOperation, 'energy');
  wireChartModes('opportunity', renderPeriodOpportunity, 'dollars');
  renderDispatch();
  renderStorage();
  renderOpportunity();
  renderHeatmap();
  renderDonut();
  renderComparison();
  renderFleetRegions();
  renderFleetLandscape();
  renderMarketTrend();
})();
