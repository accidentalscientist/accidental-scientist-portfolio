(function () {
  'use strict';

  var root = document.querySelector('[data-world-lens]');
  var dataNode = document.getElementById('world-lens-data');
  if (!root || !dataNode) return;

  var payload = JSON.parse(dataNode.textContent);
  var countries = payload.countries;
  var byCode = Object.fromEntries(countries.map(function (country) { return [country.iso3, country]; }));
  var models = payload.meta.models;
  var pillars = payload.meta.pillars;
  var indicators = payload.meta.indicators;
  var activeModel = 'power';
  var selections = ['USA', 'CHN', 'IND'].filter(function (code) { return byCode[code]; });
  var weights = {};
  Object.keys(models).forEach(function (model) {
    weights[model] = Object.fromEntries(models[model].components.map(function (key) { return [key, 1]; }));
  });

  var palette = ['#b54a2c', '#2f6f69', '#6b5b8e', '#b38a32', '#3f6c9b', '#8b5267', '#527442'];
  var regionPalette = ['#b54a2c', '#2f6f69', '#6b5b8e', '#b38a32', '#3f6c9b', '#8b5267'];
  var regions = Array.from(new Set(countries.map(function (country) { return country.region; }))).sort();
  var regionColour = Object.fromEntries(regions.map(function (region, index) {
    return [region, regionPalette[index % regionPalette.length]];
  }));

  var picker = root.querySelector('#world-lens-country');
  var addButton = root.querySelector('[data-country-add]');
  var chips = root.querySelector('[data-country-chips]');
  var weightControls = root.querySelector('[data-weight-controls]');
  var question = root.querySelector('[data-model-question]');
  var scoreDescription = root.querySelector('[data-score-description]');
  var scoreSvg = root.querySelector('[data-score-chart]');
  var tooltip = root.querySelector('[data-chart-tooltip]');
  var legend = root.querySelector('[data-score-legend]');
  var leaderboard = root.querySelector('[data-leaderboard]');
  var evidenceHead = root.querySelector('[data-evidence-head]');
  var evidenceBody = root.querySelector('[data-evidence-body]');
  var histogramSvg = root.querySelector('[data-histogram]');
  var bubbleSvg = root.querySelector('[data-bubble-chart]');
  var surpriseSvg = root.querySelector('[data-surprise-chart]');
  var tradeSvg = root.querySelector('[data-trade-chart]');
  var bridgeSvg = root.querySelector('[data-bridge-chart]');

  countries.slice().sort(function (a, b) { return a.name.localeCompare(b.name); }).forEach(function (country) {
    var option = document.createElement('option');
    option.value = country.iso3;
    option.textContent = country.name + ' · ' + country.region;
    picker.appendChild(option);
  });

  root.querySelectorAll('[data-model]').forEach(function (button) {
    button.addEventListener('click', function () {
      activeModel = button.dataset.model;
      root.querySelectorAll('[data-model]').forEach(function (other) {
        other.setAttribute('aria-pressed', String(other === button));
      });
      buildWeights();
      render();
    });
  });
  addButton.addEventListener('click', function () {
    if (selections.length < 3 && selections.indexOf(picker.value) === -1) {
      selections.push(picker.value);
      render();
    }
  });
  picker.addEventListener('change', updateAddButton);
  root.querySelector('[data-reset-weights]').addEventListener('click', function () {
    models[activeModel].components.forEach(function (key) { weights[activeModel][key] = 1; });
    buildWeights();
    render();
  });
  window.addEventListener('resize', debounce(renderCharts, 160));

  function components(model) { return models[model].components; }

  function normalisedWeights(model) {
    var total = components(model).reduce(function (sum, key) { return sum + weights[model][key]; }, 0);
    if (!total) return Object.fromEntries(components(model).map(function (key) { return [key, 0]; }));
    return Object.fromEntries(components(model).map(function (key) { return [key, weights[model][key] / total]; }));
  }

  function score(country, model) {
    var adjusted = normalisedWeights(model);
    return components(model).reduce(function (sum, key) {
      return sum + country.models[model].components[key].z * adjusted[key];
    }, 0);
  }

  function ranking(model) {
    var ordered = countries.map(function (country) {
      return { country: country, score: score(country, model) };
    }).sort(function (a, b) { return b.score - a.score; });
    var ranks = {};
    ordered.forEach(function (row, index) { ranks[row.country.iso3] = index + 1; });
    return { ordered: ordered, ranks: ranks };
  }

  function displayedRankingRows(state) {
    var shown = state.ordered.slice(0, 10);
    selections.forEach(function (code) {
      if (!shown.some(function (row) { return row.country.iso3 === code; })) {
        shown.push(state.ordered[state.ranks[code] - 1]);
      }
    });
    return shown;
  }

  function buildWeights() {
    weightControls.innerHTML = '';
    var grid = document.createElement('div');
    grid.className = 'world-lens__weight-grid';
    components(activeModel).forEach(function (key) {
      var wrapper = document.createElement('div');
      wrapper.className = 'world-lens__weight';
      wrapper.innerHTML = '<label><span>' + escapeHtml(pillars[key].label) + '</span><output>' +
        weights[activeModel][key].toFixed(2) + '×</output></label>' +
        '<input aria-label="' + escapeHtml(pillars[key].label) + ' weight" type="range" min="0" max="2" step="0.25" value="' +
        weights[activeModel][key] + '">';
      var input = wrapper.querySelector('input');
      input.addEventListener('input', function () {
        weights[activeModel][key] = Number(input.value);
        wrapper.querySelector('output').textContent = Number(input.value).toFixed(2) + '×';
        render();
      });
      grid.appendChild(wrapper);
    });
    weightControls.appendChild(grid);
  }

  function render() {
    question.textContent = models[activeModel].question;
    scoreDescription.textContent = 'Signed contributions show exactly how each weighted pillar raises or lowers the composite score.';
    renderChips();
    renderLegend();
    renderEvidence();
    renderCharts();
    updateAddButton();
  }

  function renderChips() {
    chips.innerHTML = '';
    selections.forEach(function (code) {
      var country = byCode[code];
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'world-lens__chip';
      button.innerHTML = '<span>' + escapeHtml(country.name) + '</span><small>' + escapeHtml(country.region) + '</small><b aria-hidden="true">×</b>';
      button.setAttribute('aria-label', 'Remove ' + country.name);
      button.addEventListener('click', function () {
        if (selections.length === 1) return;
        selections = selections.filter(function (selected) { return selected !== code; });
        render();
      });
      chips.appendChild(button);
    });
  }

  function updateAddButton() {
    addButton.disabled = selections.length >= 3 || selections.indexOf(picker.value) !== -1;
  }

  function renderLegend() {
    legend.innerHTML = '';
    components(activeModel).forEach(function (key, index) {
      var item = document.createElement('span');
      item.style.setProperty('--legend-colour', palette[index % palette.length]);
      item.textContent = pillars[key].label;
      legend.appendChild(item);
    });
  }

  function renderCharts() {
    drawLeaderboard();
    drawContributionChart();
    drawHistogram();
    drawBubbleChart();
    drawSurpriseChart();
    drawTradeChart();
    drawBridgeChart();
  }

  function drawLeaderboard() {
    var state = ranking(activeModel);
    var shown = displayedRankingRows(state);
    leaderboard.innerHTML = shown.map(function (row) {
      var selected = selections.indexOf(row.country.iso3) !== -1;
      return '<li class="' + (selected ? 'is-selected' : '') + '"><span class="world-lens__rank">' +
        state.ranks[row.country.iso3] + '</span><span><b>' + escapeHtml(row.country.name) + '</b><small>' +
        escapeHtml(row.country.region) + '</small></span><strong>' + signed(row.score) + '</strong></li>';
    }).join('');
  }

  function drawContributionChart() {
    var state = ranking(activeModel);
    var adjusted = normalisedWeights(activeModel);
    var shown = displayedRankingRows(state);
    var displayedCountries = shown.map(function (row) { return row.country; });
    var parts = displayedCountries.map(function (country) {
      return components(activeModel).map(function (key, index) {
        var component = country.models[activeModel].components[key];
        return { key: key, value: component.z * adjusted[key], z: component.z, colour: palette[index % palette.length] };
      });
    });
    var maxima = parts.flatMap(function (row) {
      return [row.filter(function (part) { return part.value > 0; }).reduce(function (sum, part) { return sum + part.value; }, 0),
        Math.abs(row.filter(function (part) { return part.value < 0; }).reduce(function (sum, part) { return sum + part.value; }, 0))];
    });
    var max = Math.max.apply(null, [0.5].concat(maxima));
    var width = chartWidth(scoreSvg, 520);
    var mobile = width < 600;
    var left = mobile ? 64 : 116;
    var right = mobile ? 70 : 92;
    var plotLeft = left, plotRight = width - right, zero = (plotLeft + plotRight) / 2;
    var half = (plotRight - plotLeft) / 2;
    var rowHeight = mobile ? 54 : 46;
    var height = 38 + displayedCountries.length * rowHeight;
    resetSvg(scoreSvg, width, height);
    [-1, -0.5, 0, 0.5, 1].forEach(function (fraction) {
      var x = zero + fraction * half;
      scoreSvg.appendChild(svgEl('line', { x1: x, x2: x, y1: 18, y2: height - 12, 'class': fraction ? 'world-lens__grid' : 'world-lens__zero' }));
      appendText(scoreSvg, x, 12, (fraction * max).toFixed(2), 'world-lens__tick', 'middle');
    });
    displayedCountries.forEach(function (country, rowIndex) {
      var y = 30 + rowIndex * rowHeight;
      if (selections.indexOf(country.iso3) !== -1) {
        scoreSvg.appendChild(svgEl('rect', {
          x: 0, y: y - 7, width: width, height: 40,
          fill: '#b54a2c', opacity: 0.07, 'class': 'world-lens__selected-row'
        }));
      }
      appendText(scoreSvg, 0, y + 18, mobile ? country.iso3 : country.name, 'world-lens__chart-label');
      var negativeX = zero, positiveX = zero;
      parts[rowIndex].filter(function (part) { return part.value < 0; }).reverse().forEach(function (part) {
        var segmentWidth = Math.abs(part.value) / max * half;
        negativeX -= segmentWidth;
        appendSegment(part, country, negativeX, y, segmentWidth);
      });
      parts[rowIndex].filter(function (part) { return part.value >= 0; }).forEach(function (part) {
        var segmentWidth = part.value / max * half;
        appendSegment(part, country, positiveX, y, segmentWidth);
        positiveX += segmentWidth;
      });
      appendText(scoreSvg, width - 2, y + 18, '#' + state.ranks[country.iso3] + ' · ' + signed(score(country, activeModel)), 'world-lens__chart-score', 'end');
    });
  }

  function appendSegment(part, country, x, y, width) {
    if (width < 0.5) return;
    var rect = svgEl('rect', { x: x, y: y, width: Math.max(1, width), height: 28, fill: part.colour, 'class': 'world-lens__segment', tabindex: 0 });
    var text = country.name + ' · ' + pillars[part.key].label + ': ' + signed(part.value) + ' contribution from a ' + signed(part.z) + ' pillar z-score.';
    rect.setAttribute('aria-label', text);
    rect.addEventListener('mouseenter', function () { showTooltip(rect, text); });
    rect.addEventListener('focus', function () { showTooltip(rect, text); });
    rect.addEventListener('mouseleave', hideTooltip);
    rect.addEventListener('blur', hideTooltip);
    scoreSvg.appendChild(rect);
  }

  function drawHistogram() {
    var rows = ranking(activeModel).ordered;
    var values = rows.map(function (row) { return row.score; });
    var min = Math.min.apply(null, values), max = Math.max.apply(null, values);
    var bins = 10, counts = Array(bins).fill(0), binRows = Array.from({length: bins}, function () { return []; });
    rows.forEach(function (row) {
      var index = max === min ? 0 : Math.min(bins - 1, Math.floor((row.score - min) / (max - min) * bins));
      counts[index] += 1; binRows[index].push(row.country.iso3);
    });
    var width = chartWidth(histogramSvg, 430), height = 235, margin = {top: 24, right: 12, bottom: 34, left: 30};
    resetSvg(histogramSvg, width, height);
    var plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
    var barW = plotW / bins, maxCount = Math.max.apply(null, counts);
    counts.forEach(function (count, index) {
      var h = count / maxCount * plotH;
      histogramSvg.appendChild(svgEl('rect', {x: margin.left + index * barW + 1, y: margin.top + plotH - h, width: Math.max(1, barW - 2), height: h, 'class': 'world-lens__hist-bar'}));
      var selectedInBin = binRows[index].filter(function (code) { return selections.indexOf(code) !== -1; });
      selectedInBin.forEach(function (code, markerIndex) {
        var cx = margin.left + (index + 0.5) * barW;
        histogramSvg.appendChild(svgEl('circle', {cx: cx, cy: margin.top + plotH - h - 8 - markerIndex * 9, r: 3.5, fill: '#b54a2c'}));
        appendText(histogramSvg, cx + 6, margin.top + plotH - h - 5 - markerIndex * 9, code, 'world-lens__tiny');
      });
    });
    histogramSvg.appendChild(svgEl('line', {x1: margin.left, x2: width - margin.right, y1: margin.top + plotH, y2: margin.top + plotH, 'class': 'world-lens__axis'}));
    appendText(histogramSvg, margin.left, height - 8, min.toFixed(2), 'world-lens__tick');
    appendText(histogramSvg, width - margin.right, height - 8, max.toFixed(2), 'world-lens__tick', 'end');
    appendText(histogramSvg, width / 2, height - 8, 'composite score', 'world-lens__tick', 'middle');
  }

  function drawBubbleChart() {
    var xRows = ranking('power'), yRows = ranking('potential');
    var points = countries.map(function (country) {
      var gdp = country.models.power.components.domestic_market.inputs.gdp_ppp.raw;
      return {country: country, x: score(country, 'power'), y: score(country, 'potential'), gdp: gdp};
    });
    var xs = points.map(function (point) { return point.x; }), ys = points.map(function (point) { return point.y; });
    var xExtent = extent(xs), yExtent = extent(ys);
    var width = chartWidth(bubbleSvg, 430), height = 300, m = {top: 22, right: 18, bottom: 38, left: 40};
    resetSvg(bubbleSvg, width, height);
    var sx = linear(xExtent[0], xExtent[1], m.left, width - m.right);
    var sy = linear(yExtent[0], yExtent[1], height - m.bottom, m.top);
    var gx = sx(0), gy = sy(0);
    bubbleSvg.appendChild(svgEl('line', {x1: gx, x2: gx, y1: m.top, y2: height - m.bottom, 'class': 'world-lens__grid'}));
    bubbleSvg.appendChild(svgEl('line', {x1: m.left, x2: width - m.right, y1: gy, y2: gy, 'class': 'world-lens__grid'}));
    var logs = points.map(function (point) { return Math.log10(point.gdp); }), logExtent = extent(logs);
    points.sort(function (a, b) { return b.gdp - a.gdp; }).forEach(function (point) {
      var selected = selections.indexOf(point.country.iso3) !== -1;
      var radius = 3 + (Math.log10(point.gdp) - logExtent[0]) / (logExtent[1] - logExtent[0]) * 11;
      var circle = svgEl('circle', {cx: sx(point.x), cy: sy(point.y), r: radius, fill: regionColour[point.country.region], opacity: selected ? 1 : 0.55, 'class': selected ? 'world-lens__bubble is-selected' : 'world-lens__bubble'});
      circle.setAttribute('aria-label', point.country.name + ': Power Now rank ' + xRows.ranks[point.country.iso3] + ', Power Potential rank ' + yRows.ranks[point.country.iso3]);
      bubbleSvg.appendChild(circle);
      if (selected) appendText(bubbleSvg, sx(point.x) + radius + 3, sy(point.y) + 4, point.country.iso3, 'world-lens__tiny is-strong');
    });
    appendText(bubbleSvg, width / 2, height - 7, 'Power Now →', 'world-lens__tick', 'middle');
    var yLabel = appendText(bubbleSvg, 11, height / 2, 'Power Potential →', 'world-lens__tick', 'middle');
    yLabel.setAttribute('transform', 'rotate(-90 11 ' + height / 2 + ')');
  }

  function drawSurpriseChart() {
    var current = ranking(activeModel);
    var gdpOrder = countries.slice().sort(function (a, b) {
      return b.models.power.components.domestic_market.inputs.gdp_ppp.raw - a.models.power.components.domestic_market.inputs.gdp_ppp.raw;
    });
    var gdpRanks = {};
    gdpOrder.forEach(function (country, index) { gdpRanks[country.iso3] = index + 1; });
    var rows = countries.map(function (country) {
      return {country: country, delta: gdpRanks[country.iso3] - current.ranks[country.iso3]};
    }).sort(function (a, b) { return b.delta - a.delta; });
    var shown = rows.slice(0, 5).concat(rows.slice(-5));
    shown.sort(function (a, b) { return b.delta - a.delta; });
    var width = chartWidth(surpriseSvg, 430), rowH = 22, height = 42 + shown.length * rowH, left = width < 480 ? 55 : 100, right = 28;
    resetSvg(surpriseSvg, width, height);
    var maxAbs = Math.max.apply(null, shown.map(function (row) { return Math.abs(row.delta); }).concat([1]));
    var zero = (left + width - right) / 2, half = (width - right - left) / 2;
    appendText(surpriseSvg, left, 10, 'UNDERPERFORMS GDP RANK', 'world-lens__micro');
    appendText(surpriseSvg, width - right, 10, 'OUTPERFORMS GDP RANK', 'world-lens__micro', 'end');
    surpriseSvg.appendChild(svgEl('line', {x1: zero, x2: zero, y1: 17, y2: height - 10, 'class': 'world-lens__zero'}));
    shown.forEach(function (row, index) {
      var y = 30 + index * rowH, end = zero + row.delta / maxAbs * half;
      var selected = selections.indexOf(row.country.iso3) !== -1;
      surpriseSvg.appendChild(svgEl('line', {x1: zero, x2: end, y1: y, y2: y, stroke: row.delta >= 0 ? '#2f6f69' : '#b54a2c', 'stroke-width': selected ? 6 : 3, opacity: selected ? 1 : 0.72}));
      surpriseSvg.appendChild(svgEl('circle', {cx: end, cy: y, r: selected ? 4 : 3, fill: row.delta >= 0 ? '#2f6f69' : '#b54a2c'}));
      appendText(surpriseSvg, 0, y + 4, width < 480 ? row.country.iso3 : row.country.name, selected ? 'world-lens__tiny is-strong' : 'world-lens__tiny');
      appendText(surpriseSvg, end + (row.delta >= 0 ? 6 : -6), y + 4, (row.delta > 0 ? '+' : '') + row.delta, 'world-lens__tiny', row.delta >= 0 ? 'start' : 'end');
    });
  }

  function drawTradeChart() {
    var selectedCountries = selections.map(function (code) { return byCode[code]; });
    var width = chartWidth(tradeSvg, 430), mobile = width < 520;
    var panelHeight = mobile ? 192 : 172;
    var height = 20 + selectedCountries.length * panelHeight;
    resetSvg(tradeSvg, width, height);
    selectedCountries.forEach(function (country, countryIndex) {
      var top = 12 + countryIndex * panelHeight;
      var sourceX = mobile ? 34 : 56;
      var targetX = mobile ? 132 : Math.min(210, width * 0.35);
      var sourceY = top + panelHeight / 2;
      tradeSvg.appendChild(svgEl('rect', {x: 0, y: top - 5, width: width, height: panelHeight - 8, 'class': 'world-lens__trade-panel'}));
      tradeSvg.appendChild(svgEl('circle', {cx: sourceX, cy: sourceY, r: mobile ? 20 : 25, fill: '#b54a2c'}));
      appendText(tradeSvg, sourceX, sourceY + 4, country.iso3, 'world-lens__node-text', 'middle');
      appendText(tradeSvg, 8, top + 10, country.name + ' exports to', 'world-lens__tiny is-strong');
      country.trade_links.forEach(function (link, linkIndex) {
        var y = top + 27 + linkIndex * (mobile ? 25 : 22);
        var lineWidth = Math.max(1, link.share * 26);
        tradeSvg.appendChild(svgEl('path', {
          d: 'M ' + (sourceX + 20) + ' ' + sourceY + ' C ' + (sourceX + 58) + ' ' + sourceY + ', ' + (targetX - 42) + ' ' + y + ', ' + targetX + ' ' + y,
          fill: 'none', stroke: '#2f6f69', 'stroke-width': lineWidth, opacity: 0.5
        }));
        tradeSvg.appendChild(svgEl('circle', {cx: targetX, cy: y, r: 4, fill: '#2f6f69'}));
        var partnerLabel = (mobile ? link.iso3 : link.name) + ' · ' + (link.share * 100).toFixed(1) + '% · ' + compactCurrency(link.value);
        appendText(tradeSvg, targetX + 10, y + 4, partnerLabel, 'world-lens__tiny');
      });
    });
  }

  function drawBridgeChart() {
    var potentialState = ranking('potential'), powerState = ranking('power');
    var width = chartWidth(bridgeSvg, 700), mobile = width < 620, rowH = mobile ? 78 : 60;
    var height = 58 + selections.length * rowH;
    resetSvg(bridgeSvg, width, height);
    var cols = mobile ? [12, width * 0.34, width * 0.61, width - 42] : [16, width * 0.36, width * 0.62, width - 72];
    ['ECONOMY', 'PRESENT ASSETS', 'CONVERSION SYSTEMS', 'RANKING OUTCOME'].forEach(function (label, index) {
      appendText(bridgeSvg, cols[index], 18, label, 'world-lens__tick', index ? 'middle' : 'start');
    });
    selections.forEach(function (code, rowIndex) {
      var country = byCode[code], y = 48 + rowIndex * rowH;
      var groups = {assets: [], conversion: []};
      components('potential').forEach(function (key) {
        groups[pillars[key].bridge_group].push(country.models.potential.components[key].z);
      });
      var asset = mean(groups.assets), conversion = mean(groups.conversion);
      var result = score(country, 'potential');
      bridgeSvg.appendChild(svgEl('rect', {x: 0, y: y - 25, width: width, height: rowH - 8, 'class': 'world-lens__bridge-row'}));
      appendText(bridgeSvg, cols[0], y, mobile ? code : country.name, 'world-lens__chart-label');
      appendText(bridgeSvg, cols[0], y + 15, country.region, 'world-lens__micro');
      var nodes = [asset, conversion, result];
      for (var i = 0; i < nodes.length - 1; i += 1) {
        bridgeSvg.appendChild(svgEl('line', {x1: cols[i + 1], x2: cols[i + 2], y1: y, y2: y, stroke: '#aaa39a', 'stroke-width': 2}));
      }
      nodes.forEach(function (value, index) {
        var radius = 8 + Math.min(10, Math.abs(value) * 5);
        bridgeSvg.appendChild(svgEl('circle', {cx: cols[index + 1], cy: y, r: radius, fill: value >= 0 ? '#2f6f69' : '#b54a2c', opacity: 0.82}));
        appendText(bridgeSvg, cols[index + 1], y + 4, signed(value), 'world-lens__node-text', 'middle');
      });
      appendText(bridgeSvg, cols[1], y + 27, 'asset z-score', 'world-lens__micro', 'middle');
      appendText(bridgeSvg, cols[2], y + 27, 'conversion z-score', 'world-lens__micro', 'middle');
      appendText(bridgeSvg, cols[3], y + 27, 'Potential #' + potentialState.ranks[code] + ' · Now #' + powerState.ranks[code], 'world-lens__tiny is-strong', 'middle');
    });
  }

  function renderEvidence() {
    var selected = selections.map(function (code) { return byCode[code]; });
    evidenceHead.innerHTML = '<tr><th scope="col">Pillar / observation</th>' + selected.map(function (country) {
      return '<th scope="col">' + escapeHtml(country.name) + '<small>' + escapeHtml(country.region) + '</small></th>';
    }).join('') + '</tr>';
    var html = '';
    components(activeModel).forEach(function (pillarKey) {
      var pillar = pillars[pillarKey];
      html += '<tr class="world-lens__pillar-row"><th>' + escapeHtml(pillar.label) + '<small>' + escapeHtml(pillar.description) + '</small><small>Three observations combine into this pillar.</small></th>';
      selected.forEach(function (country) {
        var pillarScore = country.models[activeModel].components[pillarKey].z;
        html += '<td><b>' + signed(pillarScore) + '</b><small>pillar z-score</small></td>';
      });
      html += '</tr>';
      pillar.inputs.forEach(function (key) {
        html += '<tr><th scope="row">' + escapeHtml(indicators[key].label) + '<small>' + escapeHtml(indicators[key].source) + '</small></th>';
        selected.forEach(function (country) {
          var item = country.models[activeModel].components[pillarKey].inputs[key];
          html += '<td>' + formatNumber(item.raw, key) + '<small>' + formatPeriod(item) + ' · z ' + signed(item.z) + '</small></td>';
        });
        html += '</tr>';
      });
    });
    evidenceBody.innerHTML = html;
  }

  function showTooltip(mark, text) {
    tooltip.textContent = text; tooltip.hidden = false;
    var markBox = mark.getBoundingClientRect(), wrapBox = scoreSvg.parentElement.getBoundingClientRect();
    tooltip.style.left = Math.max(8, Math.min(markBox.left - wrapBox.left, wrapBox.width - tooltip.offsetWidth - 8)) + 'px';
    tooltip.style.top = Math.max(4, markBox.bottom - wrapBox.top + 6) + 'px';
  }
  function hideTooltip() { tooltip.hidden = true; }

  function formatPeriod(item) {
    if (item.year) return String(item.year);
    return item.start_year + '–' + item.end_year + ' · ' + item.observations + ' obs.';
  }
  function formatNumber(value, key) {
    var unit = indicators[key].unit;
    if (unit.indexOf('$') !== -1) return new Intl.NumberFormat('en', {style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1}).format(value);
    if (unit === 'people') return new Intl.NumberFormat('en', {notation: 'compact', maximumFractionDigits: 1}).format(value);
    var suffix = unit.indexOf('%') !== -1 ? '%' : '';
    return new Intl.NumberFormat('en', {maximumFractionDigits: 1}).format(value) + suffix;
  }
  function compactCurrency(value) {
    return new Intl.NumberFormat('en', {style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1}).format(value);
  }
  function signed(value) { return (value >= 0 ? '+' : '') + value.toFixed(2); }
  function mean(values) { return values.reduce(function (sum, value) { return sum + value; }, 0) / values.length; }
  function extent(values) {
    var min = Math.min.apply(null, values), max = Math.max.apply(null, values), pad = (max - min || 1) * 0.08;
    return [min - pad, max + pad];
  }
  function linear(domainMin, domainMax, rangeMin, rangeMax) {
    return function (value) { return rangeMin + (value - domainMin) / (domainMax - domainMin) * (rangeMax - rangeMin); };
  }
  function chartWidth(svg, fallback) { return Math.max(300, Math.round(svg.parentElement.clientWidth || fallback)); }
  function resetSvg(svg, width, height) { svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height); svg.setAttribute('height', height); svg.innerHTML = ''; }
  function svgEl(name, attrs) {
    var element = document.createElementNS('http://www.w3.org/2000/svg', name);
    Object.keys(attrs).forEach(function (key) { element.setAttribute(key, attrs[key]); });
    return element;
  }
  function appendText(svg, x, y, value, className, anchor) {
    var text = svgEl('text', {x: x, y: y, 'class': className || '', 'text-anchor': anchor || 'start'});
    text.textContent = value; svg.appendChild(text); return text;
  }
  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, function (character) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[character];
    });
  }
  function debounce(callback, delay) {
    var timeout;
    return function () { clearTimeout(timeout); timeout = setTimeout(callback, delay); };
  }

  buildWeights();
  render();
}());
