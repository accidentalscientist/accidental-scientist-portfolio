/* East Coast Gas System Stress Monitor: charts.
 *
 * Hand-built SVG rather than a charting library, for four reasons that all
 * apply to this app specifically:
 *
 *   1. Two of the visuals are a heatmap grid and a network schematic.
 *      Chart.js draws neither without plugins, so a library would leave
 *      two rendering models on one page.
 *   2. The data is daily. A year is 365 points, so the performance case
 *      for canvas does not arise.
 *   3. Colours come from CSS custom properties, so dark mode works by
 *      inheritance. A canvas chart has to re-read tokens and redraw when
 *      the theme toggles.
 *   4. Real DOM nodes carry <title> and aria, which the site's quality bar
 *      asks for and canvas cannot provide.
 *
 * The cost is that scales and axes are written here. They are small
 * because the domains are simple: dates across, quantities up.
 */
(function () {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';

  function svgEl(name, attrs) {
    var element = document.createElementNS(NS, name);
    for (var key in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, key) && attrs[key] !== null) {
        element.setAttribute(key, attrs[key]);
      }
    }
    return element;
  }

  function readData(id) {
    var node = document.getElementById(id);
    if (!node) { return null; }
    try {
      return JSON.parse(node.textContent);
    } catch (err) {
      return null;
    }
  }

  function niceCeiling(value) {
    if (value <= 0) { return 1; }
    var magnitude = Math.pow(10, Math.floor(Math.log10(value)));
    var scaled = value / magnitude;
    // 2.5 and 7.5 keep a 51k storage series from being flattened beneath
    // a 100k ceiling while retaining round, readable axis labels.
    var step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 2.5 ? 2.5 :
               scaled <= 5 ? 5 : scaled <= 7.5 ? 7.5 : 10;
    return step * magnitude;
  }

  function formatTj(value) {
    if (value >= 1000) { return (value / 1000).toFixed(1) + 'k'; }
    return String(Math.round(value));
  }

  function shortDate(iso) {
    var parts = iso.split('-');
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return parts[2].replace(/^0/, '') + ' ' + months[parseInt(parts[1], 10) - 1];
  }

  function monthLabel(iso) {
    var parts = iso.split('-');
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return months[parseInt(parts[1], 10) - 1] + ' ' + parts[0].slice(2);
  }

  /* Tooltip shared by every chart: one element, moved and refilled. */
  function makeTooltip(container) {
    var tip = document.createElement('div');
    tip.className = 'gasmon-tip';
    tip.setAttribute('role', 'status');
    tip.hidden = true;
    container.appendChild(tip);

    return {
      show: function (html, x, y) {
        tip.innerHTML = html;
        tip.hidden = false;
        var bounds = container.getBoundingClientRect();
        var width = tip.offsetWidth;
        var left = Math.min(Math.max(x - width / 2, 4), bounds.width - width - 4);
        tip.style.left = left + 'px';
        tip.style.top = (y + 14) + 'px';
      },
      hide: function () { tip.hidden = true; }
    };
  }

  /* ── System balance: supply against end-use demand ─────────────── */

  function drawSystemBalance() {
    var host = document.getElementById('gasmon-balance-chart');
    var data = readData('gasmon-balance-data');
    if (!host || !data || !data.dates.length) { return; }

    var width = 900;
    var height = 300;
    var pad = { top: 16, right: 16, bottom: 30, left: 52 };
    var plotW = width - pad.left - pad.right;
    var plotH = height - pad.top - pad.bottom;

    var count = data.dates.length;
    var yMax = niceCeiling(Math.max(
      Math.max.apply(null, data.supply), Math.max.apply(null, data.demand)));

    var x = function (i) { return pad.left + (count === 1 ? plotW / 2 : (i / (count - 1)) * plotW); };
    var y = function (v) { return pad.top + plotH - (v / yMax) * plotH; };

    var svg = svgEl('svg', {
      viewBox: '0 0 ' + width + ' ' + height,
      class: 'gasmon-chart', role: 'img',
      'aria-label': 'East coast gas supply against end-use demand, ' + data.dates[0] +
                    ' to ' + data.dates[count - 1] + '. LNG export is ' +
                    Math.round(data.export_share) + ' per cent of demand over the window.'
    });

    for (var g = 0; g <= 4; g++) {
      var value = (yMax / 4) * g;
      svg.appendChild(svgEl('line', {
        x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value), class: 'gasmon-grid'
      }));
      var label = svgEl('text', { x: pad.left - 8, y: y(value) + 4,
                                  class: 'gasmon-axis-label', 'text-anchor': 'end' });
      label.textContent = formatTj(value);
      svg.appendChild(label);
    }

    // Export shown as a filled band beneath the demand line, so the
    // domestic remainder is the visible gap rather than a number.
    var band = [];
    data.export.forEach(function (v, i) { band.push((i === 0 ? 'M' : 'L') + x(i) + ' ' + y(v)); });
    band.push('L' + x(count - 1) + ' ' + y(0));
    band.push('L' + x(0) + ' ' + y(0) + ' Z');
    svg.appendChild(svgEl('path', { d: band.join(' '), class: 'gasmon-band gasmon-band--lngexport' }));

    var line = function (values, cls) {
      var d = values.map(function (v, i) { return (i === 0 ? 'M' : 'L') + x(i) + ' ' + y(v); });
      svg.appendChild(svgEl('path', { d: d.join(' '), class: cls }));
    };
    line(data.demand, 'gasmon-line');
    line(data.supply, 'gasmon-line gasmon-line--supply');

    var lastMonth = null;
    data.dates.forEach(function (iso, i) {
      var month = iso.slice(0, 7);
      if (month === lastMonth) { return; }
      lastMonth = month;
      if (i === 0 && count > 40) { return; }
      var text = svgEl('text', { x: x(i), y: height - 10, class: 'gasmon-axis-label',
                                 'text-anchor': 'middle' });
      text.textContent = monthLabel(iso);
      svg.appendChild(text);
    });

    svg.appendChild(svgEl('line', {
      x1: pad.left, x2: width - pad.right, y1: pad.top + plotH, y2: pad.top + plotH,
      class: 'gasmon-axis'
    }));

    var cursor = svgEl('line', { x1: 0, x2: 0, y1: pad.top, y2: pad.top + plotH,
                                 class: 'gasmon-cursor', visibility: 'hidden' });
    svg.appendChild(cursor);
    host.appendChild(svg);
    var tip = makeTooltip(host);

    svg.addEventListener('mousemove', function (event) {
      var box = svg.getBoundingClientRect();
      var scale = width / box.width;
      var index = Math.round((((event.clientX - box.left) * scale - pad.left) / plotW) * (count - 1));
      if (index < 0 || index >= count) { tip.hide(); cursor.setAttribute('visibility', 'hidden'); return; }

      cursor.setAttribute('visibility', 'visible');
      cursor.setAttribute('x1', x(index));
      cursor.setAttribute('x2', x(index));

      var share = data.demand[index] ? (data.export[index] / data.demand[index]) * 100 : 0;
      tip.show([
        '<strong>' + shortDate(data.dates[index]) + '</strong>',
        'Supply ' + Math.round(data.supply[index]).toLocaleString() + ' TJ',
        'End-use demand ' + Math.round(data.demand[index]).toLocaleString() + ' TJ',
        'LNG export ' + Math.round(data.export[index]).toLocaleString() +
          ' TJ (' + share.toFixed(0) + '%)',
        'Domestic ' + Math.round(data.domestic[index]).toLocaleString() + ' TJ'
      ].join('<br>'), x(index) / scale, 8);
    });

    svg.addEventListener('mouseleave', function () {
      tip.hide();
      cursor.setAttribute('visibility', 'hidden');
    });
  }

  /* ── Utilisation: bars, not a table ────────────────────────────── */

  function drawUtilisation() {
    var host = document.getElementById('gasmon-utilisation-chart');
    var data = readData('gasmon-utilisation-data');
    if (!host || !data || !data.rows.length) { return; }

    var labelW = 210;
    var rowH = 26;
    var barW = 480;
    var width = labelW + barW + 90;
    var height = data.rows.length * rowH + 26;

    var svg = svgEl('svg', {
      viewBox: '0 0 ' + width + ' ' + height,
      class: 'gasmon-chart', role: 'img',
      'aria-label': 'Pipeline throughput against the capacity in force, gas day ' +
                    data.gas_date + '. The table below carries the same figures.'
    });

    // The 100% mark is the only reference that matters, so it is the only
    // gridline drawn.
    var scale = function (pct) { return Math.min(pct, 130) / 130 * barW; };
    var hundred = labelW + scale(100);
    svg.appendChild(svgEl('line', { x1: hundred, x2: hundred, y1: 4, y2: height - 22,
                                    class: 'gasmon-axis' }));
    var mark = svgEl('text', { x: hundred, y: height - 8, class: 'gasmon-axis-label',
                               'text-anchor': 'middle' });
    mark.textContent = 'rated capacity';
    svg.appendChild(mark);

    data.rows.forEach(function (row, index) {
      var y = index * rowH;

      var name = svgEl('text', { x: labelW - 10, y: y + rowH / 2 + 4,
                                 class: 'gasmon-row-label', 'text-anchor': 'end' });
      name.textContent = row.name.length > 30 ? row.name.slice(0, 29) + '…' : row.name;
      svg.appendChild(name);

      var cls = 'gasmon-bar';
      if (row.suspect) { cls += ' gasmon-bar--suspect'; }
      else if (row.pct >= 90) { cls += ' gasmon-bar--tight'; }

      var bar = svgEl('rect', {
        x: labelW, y: y + 5, width: Math.max(1, scale(row.pct)), height: rowH - 12,
        rx: 2, class: cls
      });
      var title = svgEl('title');
      title.textContent = row.name + ': ' + Math.round(row.received).toLocaleString() +
                          ' of ' + Math.round(row.capacity).toLocaleString() + ' TJ, ' +
                          Math.round(row.pct) + '%' +
                          (row.suspect ? ' — receipts exceed the largest single rated leg' : '');
      bar.appendChild(title);
      svg.appendChild(bar);

      var value = svgEl('text', { x: labelW + scale(row.pct) + 8, y: y + rowH / 2 + 4,
                                  class: 'gasmon-axis-label' });
      value.textContent = Math.round(row.pct) + '%';
      svg.appendChild(value);
    });

    host.appendChild(svg);
  }

  /* ── Demand composition: stacked area ──────────────────────────── */

  function drawDemandComposition() {
    var host = document.getElementById('gasmon-demand-chart');
    var data = readData('gasmon-demand-data');
    if (!host || !data || !data.dates.length) { return; }

    var width = 900;
    var height = 320;
    var pad = { top: 16, right: 16, bottom: 30, left: 52 };
    var plotW = width - pad.left - pad.right;
    var plotH = height - pad.top - pad.bottom;

    var count = data.dates.length;
    // Cumulative totals per day give the stack's upper edge and the y domain.
    var totals = data.dates.map(function (_, i) {
      return data.series.reduce(function (sum, s) { return sum + s.values[i]; }, 0);
    });
    var yMax = niceCeiling(Math.max.apply(null, totals));

    var x = function (i) { return pad.left + (count === 1 ? plotW / 2 : (i / (count - 1)) * plotW); };
    var y = function (v) { return pad.top + plotH - (v / yMax) * plotH; };

    var svg = svgEl('svg', {
      viewBox: '0 0 ' + width + ' ' + height,
      class: 'gasmon-chart',
      role: 'img',
      'aria-label': 'End-use gas demand by consumer type, ' + data.dates[0] +
                    ' to ' + data.dates[count - 1] + '. The table below carries the same figures.'
    });

    // Gridlines and y axis
    for (var g = 0; g <= 4; g++) {
      var value = (yMax / 4) * g;
      svg.appendChild(svgEl('line', {
        x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value), class: 'gasmon-grid'
      }));
      var label = svgEl('text', { x: pad.left - 8, y: y(value) + 4, class: 'gasmon-axis-label',
                                  'text-anchor': 'end' });
      label.textContent = formatTj(value);
      svg.appendChild(label);
    }

    // Bands, drawn bottom-up so each sits on the running total.
    var running = new Array(count).fill(0);
    data.series.forEach(function (series, seriesIndex) {
      var upper = running.map(function (base, i) { return base + series.values[i]; });
      var path = [];
      upper.forEach(function (v, i) { path.push((i === 0 ? 'M' : 'L') + x(i) + ' ' + y(v)); });
      for (var i = count - 1; i >= 0; i--) { path.push('L' + x(i) + ' ' + y(running[i])); }
      path.push('Z');

      var area = svgEl('path', {
        d: path.join(' '),
        class: 'gasmon-band gasmon-band--' + series.code.toLowerCase()
      });
      var title = svgEl('title');
      title.textContent = series.label;
      area.appendChild(title);
      svg.appendChild(area);

      running = upper;
      series._index = seriesIndex;
    });

    // X axis: month boundaries only, or the record would be unreadable.
    var lastMonth = null;
    data.dates.forEach(function (iso, i) {
      var month = iso.slice(0, 7);
      if (month === lastMonth) { return; }
      lastMonth = month;
      if (i === 0 && count > 40) { return; }
      svg.appendChild(svgEl('line', {
        x1: x(i), x2: x(i), y1: pad.top + plotH, y2: pad.top + plotH + 4, class: 'gasmon-tick'
      }));
      var text = svgEl('text', { x: x(i), y: height - 10, class: 'gasmon-axis-label',
                                 'text-anchor': 'middle' });
      text.textContent = monthLabel(iso);
      svg.appendChild(text);
    });

    svg.appendChild(svgEl('line', {
      x1: pad.left, x2: width - pad.right, y1: pad.top + plotH, y2: pad.top + plotH,
      class: 'gasmon-axis'
    }));

    // Hover readout
    var cursor = svgEl('line', { x1: 0, x2: 0, y1: pad.top, y2: pad.top + plotH,
                                 class: 'gasmon-cursor', visibility: 'hidden' });
    svg.appendChild(cursor);

    host.appendChild(svg);
    var tip = makeTooltip(host);

    svg.addEventListener('mousemove', function (event) {
      var box = svg.getBoundingClientRect();
      var scale = width / box.width;
      var localX = (event.clientX - box.left) * scale;
      var index = Math.round(((localX - pad.left) / plotW) * (count - 1));
      if (index < 0 || index >= count) { tip.hide(); cursor.setAttribute('visibility', 'hidden'); return; }

      cursor.setAttribute('visibility', 'visible');
      cursor.setAttribute('x1', x(index));
      cursor.setAttribute('x2', x(index));

      var lines = ['<strong>' + shortDate(data.dates[index]) + '</strong>'];
      data.series.forEach(function (series) {
        var v = series.values[index];
        var pct = totals[index] ? (v / totals[index]) * 100 : 0;
        lines.push('<span class="gasmon-tip__swatch gasmon-tip__swatch--' +
                   series.code.toLowerCase() + '"></span>' + series.label + ' ' +
                   Math.round(v).toLocaleString() + ' TJ (' + pct.toFixed(1) + '%)');
      });
      lines.push('Total ' + Math.round(totals[index]).toLocaleString() + ' TJ');
      tip.show(lines.join('<br>'), (x(index) / scale), 8);
    });

    svg.addEventListener('mouseleave', function () {
      tip.hide();
      cursor.setAttribute('visibility', 'hidden');
    });
  }

  /* ── Constraint strip: one row per flagged pipeline ────────────── */

  function drawConstraintStrip() {
    var host = document.getElementById('gasmon-constraint-chart');
    var data = readData('gasmon-constraint-data');
    if (!host || !data || !data.dates.length) { return; }

    var labelW = 210;
    var rowH = 22;
    var gap = 3;
    var count = data.dates.length;
    var sparse = count < Math.min(14, data.requested_days || 14);
    var cellW = sparse ? 18 : Math.max(2, Math.min(10, 640 / count));
    var plotW = cellW * count;
    var width = labelW + plotW + 12;
    var summaryH = 34;
    var rowCount = ((data.chronic || []).length + (data.episodic || []).length) || data.rows.length;
    var height = summaryH + rowCount * (rowH + gap) + 26;

    var svg = svgEl('svg', {
      viewBox: '0 0 ' + width + ' ' + height,
      class: 'gasmon-chart gasmon-strip',
      role: 'img',
      'aria-label': 'Linepack adequacy by pipeline and gas day, ' + data.dates[0] + ' to ' +
                    data.dates[count - 1] + '. ' + data.pipelines_flagged + ' of ' +
                    data.pipelines_assessed + ' pipelines were flagged at least once.'
    });

    // A three-day forward file used to stretch a 252-unit SVG across the
    // whole page, making labels and cells enormous.  Preserve the natural
    // pixel scale until enough dates exist to behave like a heatmap.
    if (sparse) {
      svg.classList.add('gasmon-strip--sparse');
      svg.style.width = width + 'px';
      svg.style.maxWidth = '100%';
    }

    // Summary band: how many pipelines were constrained each day.
    var peak = Math.max(1, Math.max.apply(null, data.totals.map(function (t) { return t.constrained; })));
    data.totals.forEach(function (total, i) {
      if (!total.constrained) { return; }
      var h = (total.constrained / peak) * (summaryH - 12);
      var bar = svgEl('rect', {
        x: labelW + i * cellW, y: summaryH - 8 - h,
        width: Math.max(1, cellW - 0.5), height: h, class: 'gasmon-cell gasmon-cell--amber'
      });
      var t = svgEl('title');
      t.textContent = shortDate(total.date) + ': ' + total.constrained + ' of ' +
                      total.assessed + ' pipelines flagged';
      bar.appendChild(t);
      svg.appendChild(bar);
    });

    var summaryLabel = svgEl('text', { x: labelW - 10, y: summaryH - 10,
                                       class: 'gasmon-axis-label', 'text-anchor': 'end' });
    summaryLabel.textContent = 'flagged per day';
    svg.appendChild(summaryLabel);

    // Chronic first, then a rule, then episodic. Sorting them together
    // buried two single-day events under two permanently amber slabs.
    var ordered = [];
    (data.chronic || []).forEach(function (row) { ordered.push(row); });
    var ruleAfter = (data.chronic || []).length;
    (data.episodic || []).forEach(function (row) { ordered.push(row); });
    if (!ordered.length) { ordered = data.rows; ruleAfter = -1; }

    ordered.forEach(function (row, rowIndex) {
      var y = summaryH + rowIndex * (rowH + gap);

      if (rowIndex === ruleAfter && ruleAfter > 0) {
        svg.appendChild(svgEl('line', {
          x1: 10, x2: labelW + plotW, y1: y - gap, y2: y - gap, class: 'gasmon-grid'
        }));
      }

      var name = svgEl('text', { x: labelW - 10, y: y + rowH - 7,
                                 class: 'gasmon-row-label' + (row.chronic ? ' gasmon-row-label--chronic' : ''),
                                 'text-anchor': 'end' });
      name.textContent = row.name.length > 30 ? row.name.slice(0, 29) + '…' : row.name;
      var nameTitle = svgEl('title');
      nameTitle.textContent = row.name + ' — flagged on ' + row.constrained_days +
                              ' gas days (' + (row.chronic ? 'chronic' : 'episodic') + ')';
      name.appendChild(nameTitle);
      svg.appendChild(name);

      row.cells.forEach(function (flag, i) {
        if (!flag) { return; }
        var cls = 'gasmon-cell gasmon-cell--' + flag.toLowerCase();
        var cell = svgEl('rect', {
          x: labelW + i * cellW, y: y,
          width: Math.max(1, cellW - 0.5), height: rowH - 4,
          class: cls
        });
        // Colour is not the only encoding: constrained cells are also
        // taller and carry a marker, so the strip survives a monochrome
        // print and a colour-vision difference.
        if (flag !== 'GREEN') {
          cell.setAttribute('height', rowH);
          cell.setAttribute('y', y - 2);
        }
        var title = svgEl('title');
        title.textContent = row.name + ' — ' + shortDate(data.dates[i]) + ': ' + flag.toLowerCase();
        cell.appendChild(title);
        svg.appendChild(cell);
      });
    });

    // X axis: first of each month.
    var lastMonth = null;
    data.dates.forEach(function (iso, i) {
      var month = iso.slice(0, 7);
      if (month === lastMonth) { return; }
      lastMonth = month;
      var text = svgEl('text', { x: labelW + i * cellW, y: height - 8,
                                 class: 'gasmon-axis-label', 'text-anchor': 'middle' });
      text.textContent = monthLabel(iso);
      svg.appendChild(text);
    });

    host.appendChild(svg);
  }

  /* ── Storage: holdings against their own seasonal median ───────── */

  function drawStorage() {
    var host = document.getElementById('gasmon-storage-chart');
    var data = readData('gasmon-storage-data');
    if (!host || !data || !data.dates.length) { return; }

    var width = 900;
    var height = 300;
    var pad = { top: 16, right: 16, bottom: 30, left: 56 };
    var plotW = width - pad.left - pad.right;
    var plotH = height - pad.top - pad.bottom;

    var count = data.dates.length;
    var peak = Math.max.apply(null, data.totals.concat(
      data.reference.filter(function (v) { return v !== null; })));
    var yMax = niceCeiling(peak);

    var x = function (i) { return pad.left + (count === 1 ? plotW / 2 : (i / (count - 1)) * plotW); };
    var y = function (v) { return pad.top + plotH - (v / yMax) * plotH; };

    var svg = svgEl('svg', {
      viewBox: '0 0 ' + width + ' ' + height,
      class: 'gasmon-chart',
      role: 'img',
      'aria-label': 'East coast gas storage held, ' + data.dates[0] + ' to ' +
                    data.dates[count - 1] + (data.has_reference
                      ? ', against the median for the same day in other years. '
                      : '. Seasonal comparison is not yet available. ') +
                    'Latest ' + Math.round(data.latest_total).toLocaleString() + ' terajoules.'
    });

    for (var g = 0; g <= 4; g++) {
      var value = (yMax / 4) * g;
      svg.appendChild(svgEl('line', {
        x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value), class: 'gasmon-grid'
      }));
      var label = svgEl('text', { x: pad.left - 8, y: y(value) + 4, class: 'gasmon-axis-label',
                                  'text-anchor': 'end' });
      label.textContent = formatTj(value);
      svg.appendChild(label);
    }

    // Seasonal median, drawn first so the actual sits on top of it. Broken
    // into runs so a year with no comparison does not draw a false line
    // across the gap.
    var run = [];
    var runs = [];
    data.reference.forEach(function (v, i) {
      if (v === null) { if (run.length) { runs.push(run); run = []; } return; }
      run.push([x(i), y(v)]);
    });
    if (run.length) { runs.push(run); }
    runs.forEach(function (points) {
      var d = points.map(function (p, i) { return (i === 0 ? 'M' : 'L') + p[0] + ' ' + p[1]; });
      svg.appendChild(svgEl('path', { d: d.join(' '), class: 'gasmon-reference' }));
    });

    var actual = data.totals.map(function (v, i) {
      return (i === 0 ? 'M' : 'L') + x(i) + ' ' + y(v);
    });
    svg.appendChild(svgEl('path', { d: actual.join(' '), class: 'gasmon-line' }));

    var lastMonth = null;
    data.dates.forEach(function (iso, i) {
      var year = iso.slice(0, 4);
      if (year === lastMonth) { return; }
      lastMonth = year;
      if (i === 0) { return; }
      svg.appendChild(svgEl('line', {
        x1: x(i), x2: x(i), y1: pad.top, y2: pad.top + plotH, class: 'gasmon-grid'
      }));
      var text = svgEl('text', { x: x(i), y: height - 10, class: 'gasmon-axis-label',
                                 'text-anchor': 'middle' });
      text.textContent = year;
      svg.appendChild(text);
    });

    svg.appendChild(svgEl('line', {
      x1: pad.left, x2: width - pad.right, y1: pad.top + plotH, y2: pad.top + plotH,
      class: 'gasmon-axis'
    }));

    var cursor = svgEl('line', { x1: 0, x2: 0, y1: pad.top, y2: pad.top + plotH,
                                 class: 'gasmon-cursor', visibility: 'hidden' });
    svg.appendChild(cursor);

    host.appendChild(svg);
    var tip = makeTooltip(host);

    svg.addEventListener('mousemove', function (event) {
      var box = svg.getBoundingClientRect();
      var scale = width / box.width;
      var localX = (event.clientX - box.left) * scale;
      var index = Math.round(((localX - pad.left) / plotW) * (count - 1));
      if (index < 0 || index >= count) { tip.hide(); cursor.setAttribute('visibility', 'hidden'); return; }

      cursor.setAttribute('visibility', 'visible');
      cursor.setAttribute('x1', x(index));
      cursor.setAttribute('x2', x(index));

      var lines = ['<strong>' + shortDate(data.dates[index]) + '</strong>',
                   'Held ' + Math.round(data.totals[index]).toLocaleString() + ' TJ'];
      if (data.reference[index] !== null) {
        var diff = data.totals[index] - data.reference[index];
        var pct = (diff / data.reference[index]) * 100;
        lines.push('Seasonal median ' + Math.round(data.reference[index]).toLocaleString() + ' TJ');
        lines.push((diff >= 0 ? '+' : '') + Math.round(pct) + '% versus median');
      } else {
        lines.push('No comparable history for this day');
      }
      lines.push(data.reporting[index] + ' facilities reporting');
      tip.show(lines.join('<br>'), (x(index) / scale), 8);
    });

    svg.addEventListener('mouseleave', function () {
      tip.hide();
      cursor.setAttribute('visibility', 'hidden');
    });
  }

  /* ── Flow network: where gas moved between locations ───────────── */
  /*
   * Redesigned around one problem: the raw dynamic range. On a typical
   * gas day the LNG export flow (Regional QLD to Curtis Island) runs
   * roughly 8x the next-largest domestic flow, and domestic flows
   * themselves span a ~50x range. A single linear scale across all of it
   * renders one dominant line and forty near-identical hairlines, so:
   *
   *   - domestic and export edges are scaled SEPARATELY (the export edge
   *     never sets the domestic width scale, and vice versa);
   *   - both scales are square-root, not linear, which compresses the
   *     range without hiding it;
   *   - node radius follows the same principle: radius is proportional
   *     to sqrt(|net supply or demand|), i.e. VALUE maps to AREA, with a
   *     ceiling so Regional QLD and Curtis Island cannot dwarf every
   *     other node on the page.
   *
   * Direction is a small arrowhead at the destination plus a ribbon that
   * tapers from source width to a narrower target width — a true varying
   * width along the curve, not a separate triangle sitting mid-line.
   */

  function formatQuantity(tj) {
    if (Math.abs(tj) >= 1000) { return (tj / 1000).toFixed(2) + ' PJ/d'; }
    return Math.round(tj).toLocaleString() + ' TJ/d';
  }

  function quadPoint(t, x1, y1, cx, cy, x2, y2) {
    var mt = 1 - t;
    return {
      x: mt * mt * x1 + 2 * mt * t * cx + t * t * x2,
      y: mt * mt * y1 + 2 * mt * t * cy + t * t * y2
    };
  }

  function quadTangent(t, x1, y1, cx, cy, x2, y2) {
    var mt = 1 - t;
    return { x: 2 * mt * (cx - x1) + 2 * t * (x2 - cx), y: 2 * mt * (cy - y1) + 2 * t * (y2 - cy) };
  }

  /* A filled ribbon along a quadratic curve, half-width w1/2 at the start
   * tapering to w2/2 at the end — true continuous tapering rather than a
   * fixed-width stroke with a triangle stuck on. */
  function taperedRibbonPath(x1, y1, cx, cy, x2, y2, w1, w2) {
    var steps = 14;
    var left = [], right = [];
    for (var i = 0; i <= steps; i++) {
      var t = i / steps;
      var p = quadPoint(t, x1, y1, cx, cy, x2, y2);
      var tan = quadTangent(t, x1, y1, cx, cy, x2, y2);
      var len = Math.sqrt(tan.x * tan.x + tan.y * tan.y) || 1;
      var nx = -tan.y / len, ny = tan.x / len;
      var w = (w1 + (w2 - w1) * t) / 2;
      left.push(p.x + nx * w);
      left.push(p.y + ny * w);
      right.push(p.x - nx * w);
      right.push(p.y - ny * w);
    }
    var d = 'M' + left[0].toFixed(1) + ' ' + left[1].toFixed(1);
    for (i = 1; i <= steps; i++) { d += ' L' + left[i * 2].toFixed(1) + ' ' + left[i * 2 + 1].toFixed(1); }
    for (i = steps; i >= 0; i--) { d += ' L' + right[i * 2].toFixed(1) + ' ' + right[i * 2 + 1].toFixed(1); }
    return d + ' Z';
  }

  function drawFlowNetwork() {
    var host = document.getElementById('gasmon-network-chart');
    var data = readData('gasmon-network-data');
    if (!host || !data || !data.nodes.length) { return; }

    var width = 1000;
    // The original 860-unit canvas made the schematic dominate an entire
    // desktop screen and amplified its intentionally empty state regions.
    // The topology is categorical, so a tighter vertical canvas improves
    // scanning without implying geographic distance.
    var height = 680;
    var pad = 42;
    var plotW = width - pad * 2;
    var plotH = height - pad * 2;

    var px = function (x) { return pad + x * plotW; };
    var py = function (y) { return pad + y * plotH; };

    var byId = {};
    data.nodes.forEach(function (node) {
      node._x = px(node.x);
      node._y = py(node.y);
      byId[node.id] = node;
    });

    /* ── Scales ──────────────────────────────────────────────────
     * Domestic and export edges are scaled independently so the one
     * enormous LNG flow never sets the width of everything else.
     * Square-root, not linear: a linear scale across a ~50x domestic
     * range renders one visible line and forty near-identical hairlines. */
    var domestic = data.edges.filter(function (e) { return !e.export; });
    var exportEdges = data.edges.filter(function (e) { return e.export; });
    var domesticVals = domestic.map(function (e) { return e.tj; });
    var domesticMin = domesticVals.length ? Math.min.apply(null, domesticVals) : 1;
    var domesticMax = Math.max(data.domestic_peak_tj || 0, domesticMin, 1);
    var exportMax = Math.max(data.export_peak_tj || 0, 1);

    var sqrtScale = function (value, lo, hi, outLo, outHi) {
      if (hi <= lo) { return (outLo + outHi) / 2; }
      var t = Math.sqrt(Math.max(0, Math.min(1, (value - lo) / (hi - lo))));
      return outLo + t * (outHi - outLo);
    };

    // Target ranges from the brief: ~1-1.5px smallest domestic flow,
    // ~5-7px largest domestic flow; the export lane gets its own, wider
    // and visually distinct band so it still reads as exceptional.
    var domesticWidth = function (tj) { return sqrtScale(tj, domesticMin, domesticMax, 1.3, 6.5); };
    var exportWidth = function (tj) { return sqrtScale(tj, 0, exportMax, 5, 9); };

    var domesticOpacity = function (tj) { return sqrtScale(tj, domesticMin, domesticMax, 0.4, 0.85); };
    // Colour deepens with magnitude too, pale sage through to forest ink,
    // so a strong domestic flow reads as heavier in three ways at once
    // (width, opacity, colour) rather than width carrying the whole load.
    var domesticColour = function (tj) {
      var s = sqrtScale(tj, domesticMin, domesticMax, 0, 1);
      var mix = function (a, b) { return Math.round(a + (b - a) * s); };
      return 'rgb(' + mix(168, 26) + ',' + mix(178, 62) + ',' + mix(158, 34) + ')';
    };

    // Node radius maps to AREA (radius proportional to sqrt of value),
    // referenced against the legend's own "large domestic hub" example
    // rather than the true maximum, so Regional QLD and Curtis Island —
    // both roughly 10x a typical major hub — are capped rather than
    // dwarfing the rest of the diagram.
    var nodeRef = (data.legend_nodes && data.legend_nodes.length)
      ? data.legend_nodes[data.legend_nodes.length - 1] : 100;
    var nodeRadius = function (value) {
      var v = Math.abs(value);
      if (!v) { return 4; }
      return Math.max(4, Math.min(20, 4 + Math.sqrt(v / nodeRef) * 12));
    };

    var svg = svgEl('svg', {
      viewBox: '0 0 ' + width + ' ' + height,
      class: 'gasmon-chart gasmon-network',
      role: 'img',
      tabindex: '0',
      'aria-label': 'How gas moved between locations on ' + data.gas_date + '. ' +
                    data.edges.length + ' flows between ' + data.nodes.length +
                    ' locations, plus the LNG export flow from Regional Queensland to ' +
                    'Curtis Island. The table below carries the same figures; hover or ' +
                    'focus a node for its full detail.'
    });

    var defs = svgEl('defs', {});
    // Small and close to the destination, per the brief's preferred
    // fallback to a full taper — combined here WITH a tapered ribbon, so
    // direction is legible both continuously along the edge and at a
    // glance from the arrowhead alone.
    var marker = svgEl('marker', {
      id: 'gasmon-arrow', viewBox: '0 0 8 8', refX: 6.5, refY: 4,
      markerWidth: 4, markerHeight: 4, orient: 'auto-start-reverse'
    });
    marker.appendChild(svgEl('path', { d: 'M0 0 L8 4 L0 8 z', class: 'gasmon-arrowhead' }));
    defs.appendChild(marker);
    var exportMarker = svgEl('marker', {
      id: 'gasmon-arrow-export', viewBox: '0 0 8 8', refX: 6.5, refY: 4,
      markerWidth: 5, markerHeight: 5, orient: 'auto-start-reverse'
    });
    exportMarker.appendChild(svgEl('path', { d: 'M0 0 L8 4 L0 8 z', class: 'gasmon-arrowhead gasmon-arrowhead--export' }));
    defs.appendChild(exportMarker);
    svg.appendChild(defs);

    var regionLayer = svgEl('g', { class: 'gasmon-layer-regions' });
    var edgeLayer = svgEl('g', { class: 'gasmon-layer-edges' });
    var nodeLayer = svgEl('g', { class: 'gasmon-layer-nodes' });
    var labelLayer = svgEl('g', { class: 'gasmon-layer-labels' });
    var annotationLayer = svgEl('g', { class: 'gasmon-layer-annotations' });
    svg.appendChild(regionLayer);
    svg.appendChild(edgeLayer);
    svg.appendChild(nodeLayer);
    svg.appendChild(labelLayer);
    svg.appendChild(annotationLayer);

    // Soft regions, behind everything: a faint circle behind each state's
    // own cluster of nodes. Pure orientation, not data — the categorical
    // legend and the "not a map" note below both say so.
    (data.regions || []).forEach(function (region) {
      var g = svgEl('g', { 'aria-hidden': 'true' });
      var r = region.r * Math.min(plotW, plotH);
      g.appendChild(svgEl('circle', { cx: px(region.cx), cy: py(region.cy), r: r, class: 'gasmon-region' }));
      var label = svgEl('text', {
        x: px(region.cx), y: py(region.cy) - r + 18,
        'text-anchor': 'middle', class: 'gasmon-region-label'
      });
      label.textContent = region.state;
      g.appendChild(label);
      regionLayer.appendChild(g);
    });

    // Fan outgoing edges from a shared source by the angle to their
    // target, so several flows leaving one hub (Moomba in particular)
    // separate immediately rather than bundling until they near the end.
    var bySource = {};
    data.edges.forEach(function (e) {
      (bySource[e.source] = bySource[e.source] || []).push(e);
    });
    Object.keys(bySource).forEach(function (key) {
      var list = bySource[key];
      list.forEach(function (e) {
        var a = byId[e.source], b = byId[e.target];
        e._angle = (a && b) ? Math.atan2(b._y - a._y, b._x - a._x) : 0;
      });
      list.sort(function (p, q) { return p._angle - q._angle; });
      list.forEach(function (e, i) { e._fan = i - (list.length - 1) / 2; });
    });

    var neighbours = {};   // node id -> Set-like object of connected node ids
    var edgesByNode = {};  // node id -> [edge elements]
    function link(a, b, el) {
      (neighbours[a] = neighbours[a] || {})[b] = true;
      (edgesByNode[a] = edgesByNode[a] || []).push(el);
    }

    data.edges.forEach(function (edge) {
      var a = byId[edge.source];
      var b = byId[edge.target];
      if (!a || !b) { return; }

      var dx = b._x - a._x, dy = b._y - a._y;
      var length = Math.sqrt(dx * dx + dy * dy) || 1;
      var insetA = (edge.export ? 0.55 : 1) * (12 + nodeRadius(Math.max(a.supply_tj, a.demand_tj)));
      var insetB = 14 + nodeRadius(Math.max(b.supply_tj, b.demand_tj));
      var x1 = a._x + (dx / length) * insetA;
      var y1 = a._y + (dy / length) * insetA;
      var x2 = b._x - (dx / length) * insetB;
      var y2 = b._y - (dy / length) * insetB;

      var bow = 0.10 + (edge._fan || 0) * 0.045;
      var cx = (x1 + x2) / 2 - dy * bow;
      var cy = (y1 + y2) / 2 + dx * bow;

      var w1, w2, cls, marker_id;
      if (edge.export) {
        w1 = w2 = exportWidth(edge.tj);
        cls = 'gasmon-flow gasmon-flow--export';
        marker_id = 'gasmon-arrow-export';
      } else {
        var wFull = domesticWidth(edge.tj);
        w1 = wFull;
        w2 = wFull * 0.42;                        // taper toward the destination
        cls = 'gasmon-flow' + (edge.inferred ? ' gasmon-flow--inferred' : '');
        marker_id = 'gasmon-arrow';
      }

      var ribbon = svgEl('path', {
        d: taperedRibbonPath(x1, y1, cx, cy, x2, y2, w1, w2),
        class: cls,
        fill: edge.export ? null : domesticColour(edge.tj),
        'fill-opacity': edge.export ? 0.85 : domesticOpacity(edge.tj).toFixed(2),
        'marker-end': 'url(#' + marker_id + ')'
      });

      var netNote = edge.gross_reverse
        ? ' (net of ' + Math.round(edge.gross_forward).toLocaleString() + ' forward and ' +
          Math.round(edge.gross_reverse).toLocaleString() + ' TJ/d back the other way)'
        : '';
      var title = svgEl('title');
      title.textContent = (edge.export ? 'LNG export — ' : '') +
                          a.label + ' to ' + b.label + ': ' + formatQuantity(edge.tj) + netNote +
                          ' via ' + edge.pipelines.join(', ') +
                          (edge.inferred ? '. Allocated estimate, not a direct measurement.' : '. Measured flow.');
      ribbon.appendChild(title);

      ribbon.__edge = edge;
      ribbon.__a = edge.source;
      ribbon.__b = edge.target;
      edgeLayer.appendChild(ribbon);
      link(edge.source, edge.target, ribbon);
      link(edge.target, edge.source, ribbon);
    });

    // Nodes: visible circle sized by area, plus a larger invisible hit
    // target so touch and mouse interaction do not require pixel-perfect
    // accuracy on a 4px dot.
    var majorPositions = [];
    data.nodes.forEach(function (node) {
      var radius = nodeRadius(Math.max(node.supply_tj, node.demand_tj));
      node._r = radius;

      var group = svgEl('g', {
        class: 'gasmon-node gasmon-node--' + node.role,
        tabindex: '0', role: 'button',
        'aria-label': node.label + ', ' + (node.role === 'transit' ? 'transit only' :
                      (node.role === 'supply' ? 'net supply' : 'net demand') +
                      ' ' + formatQuantity(Math.abs(node.net_tj)))
      });

      group.appendChild(svgEl('circle', {
        cx: node._x, cy: node._y, r: Math.max(radius, 16), class: 'gasmon-node-hit'
      }));
      group.appendChild(svgEl('circle', {
        cx: node._x, cy: node._y, r: radius.toFixed(1), class: 'gasmon-node-dot'
      }));

      var title = svgEl('title');
      title.textContent = node.label + ' — supply ' + formatQuantity(node.supply_tj) +
                          ', end-use demand ' + formatQuantity(node.demand_tj);
      group.appendChild(title);

      group.__node = node;
      nodeLayer.appendChild(group);
      node.__el = group;
      if (node.major) { majorPositions.push(node); }
    });

    // Major hubs are always labelled; everything else appears on hover
    // or focus. Four candidate positions, scored against every other
    // major hub's chosen anchor so labels spread rather than collide —
    // a small, tractable problem at eight hubs.
    var candidateOffsets = function (r) {
      return {
        top: { x: 0, y: -(r + 20), anchor: 'middle', valueDy: -14 },
        bottom: { x: 0, y: r + 16, anchor: 'middle', valueDy: 14 },
        right: { x: r + 10, y: -2, anchor: 'start', valueDy: 14 },
        left: { x: -(r + 10), y: -2, anchor: 'end', valueDy: 14 }
      };
    };
    var chosen = [];
    majorPositions.forEach(function (node) {
      var offsets = candidateOffsets(node._r);
      var best = null, bestScore = -Infinity;
      Object.keys(offsets).forEach(function (key) {
        var o = offsets[key];
        var ax = node._x + o.x, ay = node._y + o.y;
        var score = chosen.reduce(function (min, other) {
          var d = Math.sqrt((ax - other.x) * (ax - other.x) + (ay - other.y) * (ay - other.y));
          return Math.min(min, d);
        }, Infinity);
        // A mild bias toward top/right, which read first on a left-to-right page.
        if (key === 'top') { score += 6; }
        if (key === 'right') { score += 3; }
        if (score > bestScore) { bestScore = score; best = { key: key, o: o, x: ax, y: ay }; }
      });
      chosen.push(best);

      var group = svgEl('g', { class: 'gasmon-label-group' });
      var nameY = node._y + best.o.y;
      var valueY = nameY + best.o.valueDy;
      var haloText = node.label + (node.role !== 'transit' ? ' ' + formatQuantity(Math.abs(node.net_tj)) : '');

      // A soft halo behind the text rather than a card, so a flow line
      // can pass behind a label without cutting through legible glyphs.
      var halo = svgEl('rect', {
        class: 'gasmon-label-halo',
        x: (node._x + best.o.x - (best.o.anchor === 'end' ? haloText.length * 5.6 : best.o.anchor === 'start' ? 0 : haloText.length * 2.8)).toFixed(1),
        y: (nameY - 12).toFixed(1),
        width: (haloText.length * 5.6).toFixed(1), height: 28, rx: 4
      });
      group.appendChild(halo);

      var name = svgEl('text', {
        x: node._x + best.o.x, y: nameY, 'text-anchor': best.o.anchor, class: 'gasmon-node-label'
      });
      name.textContent = node.label;
      group.appendChild(name);

      if (node.role !== 'transit') {
        var value = svgEl('text', {
          x: node._x + best.o.x, y: valueY, 'text-anchor': best.o.anchor, class: 'gasmon-node-value'
        });
        value.textContent = formatQuantity(Math.abs(node.net_tj));
        group.appendChild(value);
      }

      node.__labelGroup = group;
      labelLayer.appendChild(group);
    });

    // Curtis Island earns its own annotation: the point of the chart is
    // that this one flow is categorically different from the rest.
    var curtis = data.nodes.filter(function (n) { return n.label === 'Curtis Island'; })[0];
    if (curtis && exportEdges.length) {
      var totalExport = exportEdges.reduce(function (sum, e) { return sum + e.tj; }, 0);
      var note = svgEl('g', { class: 'gasmon-export-note' });
      var nx = curtis._x + curtis._r + 14, ny = curtis._y - 26;
      var line1 = svgEl('text', { x: nx, y: ny, class: 'gasmon-export-note__title' });
      line1.textContent = 'LNG EXPORT';
      var line2 = svgEl('text', { x: nx, y: ny + 15, class: 'gasmon-export-note__value' });
      line2.textContent = formatQuantity(totalExport) + ' exported';
      note.appendChild(line1);
      note.appendChild(line2);
      annotationLayer.appendChild(note);
    }

    host.appendChild(svg);

    /* ── Interaction: hover, keyboard focus and tap all drive the same
     * highlight — the selected node, its edges and its neighbours stay
     * at full strength; everything else dims. A tap (or Enter/Space on a
     * focused node) pins the state so touch users get the same detail
     * without a hover event. */
    var tip = makeTooltip(host);
    var pinned = null;

    function clearHighlight() {
      svg.querySelectorAll('.gasmon-dim').forEach(function (el) { el.classList.remove('gasmon-dim'); });
      svg.querySelectorAll('.gasmon-focused').forEach(function (el) { el.classList.remove('gasmon-focused'); });
    }

    function highlightNode(node) {
      clearHighlight();
      var keep = {};
      keep[node.id] = true;
      (edgesByNode[node.id] || []).forEach(function (el) {
        el.classList.add('gasmon-focused');
        keep[el.__a] = true;
        keep[el.__b] = true;
      });
      data.nodes.forEach(function (n) {
        if (!keep[n.id]) { n.__el.classList.add('gasmon-dim'); }
      });
      edgeLayer.querySelectorAll('.gasmon-flow').forEach(function (el) {
        if (!el.classList.contains('gasmon-focused')) { el.classList.add('gasmon-dim'); }
      });
    }

    function nodeTooltipHtml(node) {
      var lines = ['<strong>' + node.label.toUpperCase() + '</strong>'];
      lines.push(node.role === 'transit' ? 'Transit only' :
                (node.role === 'supply' ? 'Net supply' : 'Net demand') +
                '<br>' + formatQuantity(Math.abs(node.net_tj)));

      var out = (edgesByNode[node.id] || []).filter(function (el) { return el.__a === node.id; });
      var into = (edgesByNode[node.id] || []).filter(function (el) { return el.__b === node.id; });
      if (out.length) {
        lines.push('<br><em>Outgoing</em>');
        out.forEach(function (el) {
          var b = byId[el.__b];
          lines.push('→ ' + b.label + ' &nbsp; ' + formatQuantity(el.__edge.tj));
        });
      }
      if (into.length) {
        lines.push('<br><em>Incoming</em>');
        into.forEach(function (el) {
          var a = byId[el.__a];
          lines.push('← ' + a.label + ' &nbsp; ' + formatQuantity(el.__edge.tj));
        });
      }
      lines.push('<br>Data: AEMO Gas Bulletin Board · ' + shortDate(data.gas_date));
      return lines.join('<br>');
    }

    function edgeTooltipHtml(edge) {
      var a = byId[edge.source], b = byId[edge.target];
      var lines = [
        '<strong>' + a.label.toUpperCase() + ' → ' + b.label.toUpperCase() + '</strong>',
        'Flow: ' + formatQuantity(edge.tj)
      ];
      if (edge.export) { lines.unshift('<strong>LNG EXPORT</strong>'); }
      lines.push('Type: ' + (edge.inferred ? 'Allocated estimate' : 'Measured flow'));
      if (edge.gross_reverse) {
        lines.push('Net of ' + Math.round(edge.gross_forward).toLocaleString() + ' forward, ' +
                   Math.round(edge.gross_reverse).toLocaleString() + ' TJ/d the other way');
      }
      lines.push('Date: ' + shortDate(data.gas_date));
      return lines.join('<br>');
    }

    function activateNode(node, clientX, clientY) {
      highlightNode(node);
      node.__el.classList.add('gasmon-focused');
      var box = host.getBoundingClientRect();
      tip.show(nodeTooltipHtml(node), (node._x / width) * box.width, (node._y / height) * box.height);
    }

    function deactivate() {
      if (pinned) { return; }
      clearHighlight();
      tip.hide();
    }

    data.nodes.forEach(function (node) {
      var el = node.__el;
      el.addEventListener('mouseenter', function () { if (!pinned) { activateNode(node); } });
      el.addEventListener('mouseleave', deactivate);
      el.addEventListener('focus', function () { activateNode(node); });
      el.addEventListener('blur', function () { if (pinned !== node) { deactivate(); } });
      el.addEventListener('click', function (event) {
        event.stopPropagation();
        pinned = (pinned === node) ? null : node;
        if (pinned) { activateNode(node); } else { deactivate(); }
      });
      el.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          pinned = (pinned === node) ? null : node;
          if (pinned) { activateNode(node); } else { deactivate(); }
        }
      });
    });

    edgeLayer.querySelectorAll('.gasmon-flow').forEach(function (el) {
      el.addEventListener('mouseenter', function () {
        if (pinned) { return; }
        clearHighlight();
        el.classList.add('gasmon-focused');
        svg.querySelectorAll('.gasmon-flow, .gasmon-node').forEach(function (other) {
          if (other !== el) { other.classList.add('gasmon-dim'); }
        });
        var box = host.getBoundingClientRect();
        var a = byId[el.__a], b = byId[el.__b];
        tip.show(edgeTooltipHtml(el.__edge),
                 ((a._x + b._x) / 2 / width) * box.width, ((a._y + b._y) / 2 / height) * box.height);
      });
      el.addEventListener('mouseleave', deactivate);
    });

    host.addEventListener('click', function (event) {
      if (event.target === host || event.target === svg) {
        pinned = null;
        deactivate();
      }
    });

    /* ── Magnitude legend: three widths, three areas, generated with
     * the SAME scale functions the chart itself uses. */
    var legendHost = document.getElementById('gasmon-network-legend');
    if (legendHost && (data.legend_flows || []).length) {
      var flowSvg = svgEl('svg', { viewBox: '0 0 180 20', class: 'gasmon-legend-svg' });
      data.legend_flows.forEach(function (tj, i) {
        var y = 10, x1 = 4 + i * 60, x2 = x1 + 34;
        var line = svgEl('path', {
          d: taperedRibbonPath(x1, y, (x1 + x2) / 2, y, x2, y, domesticWidth(tj), domesticWidth(tj) * 0.42),
          class: 'gasmon-flow', 'fill-opacity': 0.7
        });
        flowSvg.appendChild(line);
        var label = svgEl('text', { x: (x1 + x2) / 2, y: 19, 'text-anchor': 'middle', class: 'gasmon-legend-label' });
        label.textContent = formatQuantity(tj);
        flowSvg.appendChild(label);
      });
      var flowWrap = document.createElement('div');
      flowWrap.className = 'gasmon-legend-block';
      flowWrap.innerHTML = '<span class="gasmon-legend-block__title">Flow width</span>';
      flowWrap.appendChild(flowSvg);
      legendHost.appendChild(flowWrap);
    }
    if (legendHost && (data.legend_nodes || []).length) {
      var nodeSvg = svgEl('svg', { viewBox: '0 0 180 44', class: 'gasmon-legend-svg' });
      data.legend_nodes.forEach(function (v, i) {
        var r = nodeRadius(v);
        var cx = 22 + i * 60;
        nodeSvg.appendChild(svgEl('circle', { cx: cx, cy: 20, r: r.toFixed(1), class: 'gasmon-legend-node' }));
        var label = svgEl('text', { x: cx, y: 40, 'text-anchor': 'middle', class: 'gasmon-legend-label' });
        label.textContent = formatQuantity(v);
        nodeSvg.appendChild(label);
      });
      var nodeWrap = document.createElement('div');
      nodeWrap.className = 'gasmon-legend-block';
      nodeWrap.innerHTML = '<span class="gasmon-legend-block__title">Node area</span>';
      nodeWrap.appendChild(nodeSvg);
      legendHost.appendChild(nodeWrap);
    }
  }

  function init() {
    drawSystemBalance();
    drawFlowNetwork();
    drawDemandComposition();
    drawConstraintStrip();
    drawUtilisation();
    drawStorage();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
