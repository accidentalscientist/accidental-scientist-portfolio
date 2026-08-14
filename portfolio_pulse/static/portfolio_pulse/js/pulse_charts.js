document.addEventListener('DOMContentLoaded', function () {
  const get = id => {
    const element = document.getElementById(id);
    return element ? JSON.parse(element.textContent) : null;
  };
  if (typeof Chart === 'undefined') return;

  const COLORS = {
    Critical: '#c0392b',
    Watch: '#d4772a',
    Healthy: '#2d6a2d',
    ink: '#26372c',
    blue: '#3f7da6',
    muted: '#8a9e82',
    green: '#5a9e5a',
    red: '#c0392b',
    amber: '#d4772a',
    neutral: '#66736d',
  };
  const RUNWAY_ORDER = ['0-6 months', '6-18 months', '18-36 months', '36+ months'];
  const RUNWAY_COLORS = {
    '0-6 months': '#c0392b',
    '6-18 months': '#c99518',
    '18-36 months': '#78a66d',
    '36+ months': '#234b32',
  };
  const TENURE_COLORS = ['#e4ca69', '#b8c879', '#84aa6b', '#4f8153', '#214b34'];
  const VALUE_TIER_COLORS = ['#c99518', '#98a18c', '#a8673a'];
  const GROUP_COLORS = ['#2d6a2d', '#b84a1a', '#3f7da6', '#8e7cc3', '#d4772a', '#5a9e5a', '#9a9488'];
  const gridColor = 'rgba(26,46,26,0.07)';
  const money = value => '$' + Math.round(value || 0).toLocaleString();
  const compactMoney = value => {
    const abs = Math.abs(value || 0);
    if (abs >= 1000000) return '$' + (value / 1000000).toFixed(1) + 'M';
    if (abs >= 1000) return '$' + Math.round(value / 1000) + 'k';
    return money(value);
  };
  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        labels: { boxWidth: 11, usePointStyle: true, font: { size: 11 } },
      },
    },
  };

  const concentration = get('pulse-data-concentration');
  const concentrationCanvas = document.getElementById('pulse-chart-concentration');
  if (concentration && concentrationCanvas) {
    const accounts = concentration.accounts;
    new Chart(concentrationCanvas, {
      type: 'bar',
      data: {
        labels: accounts.map(account => account.name),
        datasets: [{
          label: 'Current ARR',
          data: accounts.map(account => account.arr),
          backgroundColor: accounts.map(account => COLORS[account.band]),
          borderRadius: 2,
          maxBarThickness: 28,
        }],
      },
      options: {
        ...baseOptions,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: items => accounts[items[0].dataIndex].name,
              label: context => `${compactMoney(context.raw)} current ARR`,
              afterBody: items => {
                const account = accounts[items[0].dataIndex];
                return [
                  `Health ${account.health}`,
                  `${account.term_months || '?'}-month term`,
                  `${compactMoney(account.contract_value)} secured contract value`,
                ];
              },
            },
          },
        },
        scales: {
          x: { ticks: { display: false }, grid: { display: false }, border: { display: false } },
          y: { beginAtZero: true, ticks: { callback: compactMoney }, grid: { color: gridColor } },
        },
      },
    });
  }

  const distribution = get('pulse-data-arr-distribution');
  const distributionCanvas = document.getElementById('pulse-chart-arr-distribution');
  if (distribution && distributionCanvas) {
    new Chart(distributionCanvas, {
      type: 'bar',
      data: {
        labels: distribution.map(row => row.label),
        datasets: [{
          label: 'Average ARR',
          data: distribution.map(row => row.average_arr),
          backgroundColor: VALUE_TIER_COLORS,
          borderRadius: 3,
        }],
      },
      options: {
        ...baseOptions,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: context => `${compactMoney(context.raw)} average ARR`,
              afterLabel: context => {
                const row = distribution[context.dataIndex];
                return [
                  `${row.count} accounts`,
                  `${compactMoney(row.total_arr)} total ARR`,
                  `${compactMoney(row.lowest_arr)} to ${compactMoney(row.highest_arr)}`,
                ];
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: compactMoney }, title: { display: true, text: 'Average ARR' }, grid: { color: gridColor } },
        },
      },
    });
  }

  const runway = get('pulse-data-contract-runway');
  const runwayCanvas = document.getElementById('pulse-chart-contract-runway');
  if (runway && runwayCanvas) {
    new Chart(runwayCanvas, {
      type: 'bar',
      data: {
        labels: runway.map(row => row.label),
        datasets: [{
          label: 'Current ARR',
          data: runway.map(row => row.arr),
          backgroundColor: runway.map(row => RUNWAY_COLORS[row.label]),
        }],
      },
      options: {
        ...baseOptions,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: context => `${compactMoney(context.raw)} ARR`,
              afterLabel: context => {
                const row = runway[context.dataIndex];
                return [
                  `${row.count} accounts - ${row.action}`,
                  `${compactMoney(row.resign_value)} at a three-year re-sign`,
                  `${compactMoney(row.secured_value)} current secured value`,
                  `${compactMoney(row.one_year_arr)} on one-year terms`,
                ];
              },
            },
          },
        },
        scales: {
          x: { beginAtZero: true, ticks: { callback: compactMoney }, grid: { color: gridColor } },
          y: { grid: { display: false } },
        },
      },
    });
  }

  const tenure = get('pulse-data-tenure');
  const tenureCanvas = document.getElementById('pulse-chart-tenure');
  if (tenure && tenureCanvas) {
    new Chart(tenureCanvas, {
      type: 'bar',
      data: {
        labels: tenure.map(row => row.label),
        datasets: [{
          label: 'Current ARR',
          data: tenure.map(row => row.arr),
          backgroundColor: tenure.map((row, index) => TENURE_COLORS[index]),
          borderRadius: 3,
        }],
      },
      options: {
        ...baseOptions,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: context => `${compactMoney(context.raw)} ARR`,
              afterLabel: context => {
                const row = tenure[context.dataIndex];
                return [`${row.count} accounts`, `${compactMoney(row.contract_value)} secured contract value`];
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: compactMoney }, grid: { color: gridColor } },
        },
      },
    });
  }

  const industry = get('pulse-data-industry');
  const industryCanvas = document.getElementById('pulse-chart-industry');
  if (industry && industryCanvas) {
    new Chart(industryCanvas, {
      type: 'bar',
      data: {
        labels: industry.map(row => row.industry),
        datasets: [
          { label: 'Critical', data: industry.map(row => row.critical_arr), backgroundColor: COLORS.Critical },
          { label: 'Watch', data: industry.map(row => row.watch_arr), backgroundColor: COLORS.Watch },
          { label: 'Healthy', data: industry.map(row => row.healthy_arr), backgroundColor: COLORS.Healthy },
        ],
      },
      options: {
        ...baseOptions,
        indexAxis: 'y',
        plugins: {
          ...baseOptions.plugins,
          tooltip: {
            callbacks: {
              label: context => `${context.dataset.label}: ${compactMoney(context.raw)}`,
              afterBody: items => {
                const row = industry[items[0].dataIndex];
                return [
                  `Average health ${row.avg_health}`,
                  `${row.count} accounts`,
                  `Largest customer ${row.largest_share}% of industry ARR`,
                ];
              },
            },
          },
        },
        scales: {
          x: { stacked: true, beginAtZero: true, ticks: { callback: compactMoney }, grid: { color: gridColor } },
          y: { stacked: true, grid: { display: false }, ticks: { font: { size: 9 } } },
        },
      },
    });
  }

  const healthDistribution = get('pulse-data-health-distribution');
  const healthDistributionCanvas = document.getElementById('pulse-chart-health-distribution');
  if (healthDistribution && healthDistributionCanvas) {
    const healthRevenueLabels = {
      id: 'healthRevenueLabels',
      afterDatasetsDraw(chart) {
        const { ctx } = chart;
        const meta = chart.getDatasetMeta(0);
        ctx.save();
        ctx.fillStyle = '#ffffff';
        ctx.font = '600 11px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        meta.data.forEach((bar, index) => {
          if (!healthDistribution[index].count) return;
          const middle = bar.y + (bar.base - bar.y) / 2;
          ctx.fillText(compactMoney(healthDistribution[index].arr), bar.x, middle);
        });
        ctx.restore();
      },
    };
    new Chart(healthDistributionCanvas, {
      type: 'bar',
      data: {
        labels: healthDistribution.map(row => row.band),
        datasets: [{
          label: 'Accounts',
          data: healthDistribution.map(row => row.count),
          backgroundColor: healthDistribution.map(row => COLORS[row.band]),
        }],
      },
      options: {
        ...baseOptions,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              afterLabel: context => `${compactMoney(healthDistribution[context.dataIndex].arr)} ARR exposure`,
            },
          },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: 'Account count' }, grid: { color: gridColor } },
        },
      },
      plugins: [healthRevenueLabels],
    });
  }

  const qbr = get('pulse-data-qbr');
  const qbrCanvas = document.getElementById('pulse-chart-qbr');
  if (qbr && qbrCanvas) {
    const grouped = {};
    qbr.forEach(account => {
      (grouped[account.runway] = grouped[account.runway] || []).push({
        x: account.days_since_qbr,
        y: account.arr,
        name: account.name,
        owner: account.owner,
        health: account.health,
        inferred: account.qbr_inferred,
        renewalDays: account.renewal_days,
      });
    });
    new Chart(qbrCanvas, {
      type: 'scatter',
      data: {
        datasets: RUNWAY_ORDER.filter(label => grouped[label]).map(label => ({
          label,
          data: grouped[label],
          backgroundColor: `${RUNWAY_COLORS[label] || '#777777'}bf`,
          borderColor: RUNWAY_COLORS[label] || '#777777',
          borderWidth: 1.25,
          pointRadius: 7,
          pointHoverRadius: 9,
        })),
      },
      options: {
        ...baseOptions,
        plugins: {
          ...baseOptions.plugins,
          tooltip: {
            callbacks: {
              label: context => `${context.raw.name}: ${context.raw.x} days, ${compactMoney(context.raw.y)} ARR`,
              afterLabel: context => [
                context.raw.inferred ? 'No QBR recorded - using customer tenure' : 'QBR date recorded',
                `Health ${context.raw.health}`,
                `Owner ${context.raw.owner}`,
              ],
            },
          },
        },
        scales: {
          x: { beginAtZero: true, title: { display: true, text: 'Days since last QBR' }, grid: { color: gridColor } },
          y: { beginAtZero: true, title: { display: true, text: 'Current ARR' }, ticks: { callback: compactMoney }, grid: { color: gridColor } },
        },
      },
    });
  }

  const growers = get('pulse-data-growers');
  const growersCanvas = document.getElementById('pulse-chart-growers');
  if (growers && growersCanvas) {
    const maxGrowerMovement = Math.max(1, ...growers.map(account => Math.abs(account.change)));
    const symmetricLimit = Math.ceil(maxGrowerMovement / 50000) * 50000;
    new Chart(growersCanvas, {
      type: 'bar',
      data: {
        labels: growers.map(account => account.name),
        datasets: [{
          label: '12-month ARR change',
          data: growers.map(account => account.change),
          backgroundColor: growers.map(account => account.change < 0 ? COLORS.red : COLORS.green),
        }],
      },
      options: {
        ...baseOptions,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: context => `${compactMoney(context.raw)} ARR (${growers[context.dataIndex].change_pct}%)`,
              afterLabel: context => `${compactMoney(growers[context.dataIndex].arr)} current ARR`,
            },
          },
        },
        scales: {
          x: { min: -symmetricLimit, max: symmetricLimit, ticks: { callback: compactMoney }, grid: { color: gridColor } },
          y: { grid: { display: false }, ticks: { font: { size: 9 } } },
        },
      },
    });
  }

  const divergence = get('pulse-data-divergence');
  const divergenceCanvas = document.getElementById('pulse-chart-divergence');
  if (divergence && divergenceCanvas) {
    const maxArr = Math.max(1, ...divergence.map(account => account.arr));
    const roundedLimit = values => {
      const observed = Math.max(0, ...values.map(value => Math.abs(value || 0)));
      return Math.max(20, Math.ceil((observed * 1.12) / 10) * 10);
    };
    const detailXLimit = roundedLimit(divergence.map(account => account.arr_trend));
    const detailYLimit = roundedLimit(divergence.map(account => account.usage_trend));
    const quadrantPlugin = {
      id: 'quadrants',
      beforeDraw(chart) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea) return;
        const x0 = scales.x.getPixelForValue(0);
        const y0 = scales.y.getPixelForValue(0);
        const areas = [
          [x0, chartArea.top, chartArea.right - x0, y0 - chartArea.top, 'rgba(76,142,96,0.12)', 'Compounding', 'right'],
          [x0, y0, chartArea.right - x0, chartArea.bottom - y0, 'rgba(215,165,70,0.15)', 'Adoption lag', 'right'],
          [chartArea.left, y0, x0 - chartArea.left, chartArea.bottom - y0, 'rgba(105,119,135,0.12)', 'Active decline', 'left'],
          [chartArea.left, chartArea.top, x0 - chartArea.left, y0 - chartArea.top, 'rgba(126,113,169,0.11)', 'Commercial mismatch', 'left'],
        ];
        ctx.save();
        areas.forEach(([x, y, w, h, fill]) => {
          ctx.fillStyle = fill;
          ctx.fillRect(x, y, w, h);
        });
        ctx.restore();
      },
      afterDatasetsDraw(chart) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea) return;
        const x0 = scales.x.getPixelForValue(0);
        const y0 = scales.y.getPixelForValue(0);
        const labels = [
          [x0, chartArea.top, chartArea.right - x0, 'Compounding', 'right'],
          [x0, y0, chartArea.right - x0, 'Adoption lag', 'right'],
          [chartArea.left, y0, x0 - chartArea.left, 'Active decline', 'left'],
          [chartArea.left, chartArea.top, x0 - chartArea.left, 'Commercial mismatch', 'left'],
        ];
        ctx.save();
        labels.forEach(([x, y, w, label, align]) => {
          ctx.fillStyle = 'rgba(38,55,44,0.72)';
          ctx.font = '600 10px sans-serif';
          ctx.textAlign = align;
          ctx.fillText(label, align === 'right' ? x + w - 10 : x + 10, y + 16);
        });
        ctx.restore();
      },
    };
    const points = accounts => accounts.map(account => ({
      x: account.arr_trend,
      y: account.usage_trend,
      r: 4 + (account.arr / maxArr) * 13,
      id: account.id,
      name: account.name,
      arr: account.arr,
      reason: account.attention_reason,
      eligible: account.eligible,
      windowLabel: account.window_label,
      observations: account.observation_count,
      method: account.method,
      validation: account.validation,
    }));
    const standardAccounts = divergence.filter(account => account.attention_state === 'standard');
    const acceleratingAccounts = divergence.filter(account => account.attention_state === 'acceleration');
    const attentionAccounts = divergence.filter(account => account.attention_state === 'attention');
    const divergenceChart = new Chart(divergenceCanvas, {
      type: 'bubble',
      data: {
        datasets: [
          {
            label: 'Standard portfolio',
            data: points(standardAccounts),
            backgroundColor: 'rgba(66,105,142,0.60)',
            borderColor: '#355a78',
            borderWidth: 1,
          },
          {
            label: 'Acceleration',
            data: points(acceleratingAccounts),
            backgroundColor: 'rgba(45,106,45,0.78)',
            borderColor: '#1f5125',
            borderWidth: 1.4,
          },
          {
            label: 'Needs attention',
            data: points(attentionAccounts),
            backgroundColor: 'rgba(185,62,50,0.82)',
            borderColor: '#983126',
            borderWidth: 1.2,
          },
        ],
      },
      options: {
        ...baseOptions,
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: { usePointStyle: true, boxWidth: 8 },
          },
          tooltip: {
            callbacks: {
              title: items => items[0].raw.name,
              label: context => [
                `ARR ${context.raw.x}%`,
                `Usage ${context.raw.y > 0 ? '+' : ''}${context.raw.y} percentage points`,
                `${compactMoney(context.raw.arr)} current ARR`,
              ],
              afterLabel: context => [
                context.raw.reason,
                context.raw.windowLabel,
                context.raw.method,
                context.raw.validation,
              ],
            },
          },
        },
        onClick: (_event, elements, chart) => {
          if (!elements.length) return;
          const raw = chart.data.datasets[elements[0].datasetIndex].data[elements[0].index];
          const picker = document.getElementById('pulse-journey-account');
          if (!picker || !raw.id) return;
          picker.value = raw.id;
          picker.dispatchEvent(new Event('change'));
          document.getElementById('pulse-chart-account-journey')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        },
        scales: {
          x: { min: -detailXLimit, max: detailXLimit, title: { display: true, text: 'Smoothed ARR change %' }, ticks: { callback: value => value + '%' }, grid: { color: gridColor } },
          y: { min: -detailYLimit, max: detailYLimit, title: { display: true, text: 'Seat-utilisation change (percentage points)' }, ticks: { callback: value => value + 'pp' }, grid: { color: gridColor } },
        },
      },
      plugins: [quadrantPlugin],
    });

    document.querySelectorAll('[data-map-scale]').forEach(button => {
      button.addEventListener('click', () => {
        document.querySelectorAll('[data-map-scale]').forEach(item => item.classList.remove('is-active'));
        button.classList.add('is-active');
        const isFull = button.dataset.mapScale === 'full';
        const xLimit = isFull ? Math.max(100, detailXLimit) : detailXLimit;
        const yLimit = isFull ? Math.max(100, detailYLimit) : detailYLimit;
        divergenceChart.options.scales.x.min = -xLimit;
        divergenceChart.options.scales.x.max = xLimit;
        divergenceChart.options.scales.y.min = -yLimit;
        divergenceChart.options.scales.y.max = yLimit;
        divergenceChart.update();
      });
    });
  }

  const accountJourneys = get('pulse-data-account-journeys');
  const journeyCanvas = document.getElementById('pulse-chart-account-journey');
  const journeyPicker = document.getElementById('pulse-journey-account');
  const journeyEvidence = document.getElementById('pulse-journey-evidence');
  let journeyChart = null;
  if (accountJourneys && journeyCanvas && journeyPicker) {
    accountJourneys.forEach(account => {
      const option = document.createElement('option');
      option.value = account.id;
      option.textContent = `${account.name} · ${account.attention_state === 'attention' ? 'needs attention' : account.attention_state}`;
      journeyPicker.appendChild(option);
    });

    const renderJourney = accountId => {
      const account = accountJourneys.find(candidate => candidate.id === accountId) || accountJourneys[0];
      if (!account) return;
      if (journeyChart) journeyChart.destroy();
      journeyChart = new Chart(journeyCanvas, {
        type: 'line',
        data: {
          labels: account.labels,
          datasets: [
            {
              label: 'ARR',
              data: account.arr,
              yAxisID: 'y',
              borderColor: COLORS.blue,
              backgroundColor: COLORS.blue,
              pointRadius: 1.5,
              pointHoverRadius: 4,
              borderWidth: 2.5,
              tension: 0.2,
            },
            {
              label: 'Seat utilisation',
              data: account.usage,
              yAxisID: 'y1',
              borderColor: account.attention_state === 'attention' ? COLORS.red : COLORS.green,
              backgroundColor: account.attention_state === 'attention' ? COLORS.red : COLORS.green,
              pointRadius: 1.5,
              pointHoverRadius: 4,
              borderWidth: 2.5,
              tension: 0.2,
            },
          ],
        },
        options: {
          ...baseOptions,
          interaction: { mode: 'index', intersect: false },
          scales: {
            x: { ticks: { maxTicksLimit: 12, font: { size: 9 } }, grid: { display: false } },
            y: { position: 'left', title: { display: true, text: 'ARR' }, ticks: { callback: compactMoney }, grid: { color: gridColor } },
            y1: { position: 'right', min: 0, max: 100, title: { display: true, text: 'Seat utilisation' }, ticks: { callback: value => value + '%' }, grid: { drawOnChartArea: false } },
          },
        },
      });
      if (journeyEvidence) {
        journeyEvidence.textContent = `${account.attention_reason} · ${account.window_label || 'timeline available'} · ${compactMoney(account.current_arr)} current ARR`;
      }
    };

    journeyPicker.addEventListener('change', () => renderJourney(journeyPicker.value));
    renderJourney(accountJourneys[0]?.id);
  }

  const arrTrend = get('pulse-data-arr-trend');
  const healthTrend = get('pulse-data-health-trend');
  const portfolioTrendCanvas = document.getElementById('pulse-chart-portfolio-trend');
  if (arrTrend && healthTrend && portfolioTrendCanvas) {
    const portfolioHealthBands = {
      id: 'portfolioHealthBands',
      beforeDraw(chart) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea) return;
        const y100 = scales.y1.getPixelForValue(100);
        const y75 = scales.y1.getPixelForValue(75);
        const y50 = scales.y1.getPixelForValue(50);
        const y0 = scales.y1.getPixelForValue(0);
        ctx.save();
        ctx.fillStyle = 'rgba(45,106,45,0.08)';
        ctx.fillRect(chartArea.left, y100, chartArea.width, y75 - y100);
        ctx.fillStyle = 'rgba(201,149,24,0.08)';
        ctx.fillRect(chartArea.left, y75, chartArea.width, y50 - y75);
        ctx.fillStyle = 'rgba(192,57,43,0.06)';
        ctx.fillRect(chartArea.left, y50, chartArea.width, y0 - y50);
        ctx.restore();
      },
    };
    new Chart(portfolioTrendCanvas, {
      type: 'line',
      data: {
        labels: arrTrend.labels,
        datasets: [
          {
            label: 'Portfolio ARR',
            data: arrTrend.arr,
            borderColor: COLORS.ink,
            backgroundColor: COLORS.ink,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderWidth: 3,
            tension: 0.22,
            yAxisID: 'y',
          },
          {
            label: 'Signal health',
            data: healthTrend.health,
            borderColor: COLORS.blue,
            backgroundColor: COLORS.blue,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderWidth: 2.5,
            tension: 0.2,
            yAxisID: 'y1',
          },
        ],
      },
      options: {
        ...baseOptions,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          ...baseOptions.plugins,
          tooltip: {
            callbacks: {
              label: context => context.dataset.yAxisID === 'y'
                ? `Portfolio ARR: ${compactMoney(context.raw)}`
                : `Signal health: ${context.raw}`,
            },
          },
        },
        scales: {
          x: { ticks: { maxTicksLimit: 9, font: { size: 9 } }, grid: { display: false } },
          y: {
            position: 'left',
            beginAtZero: false,
            title: { display: true, text: 'Portfolio ARR' },
            ticks: { callback: compactMoney },
            grid: { color: gridColor },
          },
          y1: {
            position: 'right',
            min: 0,
            max: 100,
            title: { display: true, text: 'Health score' },
            ticks: { stepSize: 25 },
            grid: { display: false },
          },
        },
      },
      plugins: [portfolioHealthBands],
    });
  }

  const movement = get('pulse-data-arr-movement');
  const movementCanvas = document.getElementById('pulse-chart-arr-movement');
  if (movement && movementCanvas) {
    new Chart(movementCanvas, {
      data: {
        labels: movement.labels,
        datasets: [
          { type: 'bar', label: 'New ARR', data: movement.new, backgroundColor: '#7fb37f', stack: 'movement' },
          { type: 'bar', label: 'Expansion', data: movement.expansion, backgroundColor: COLORS.green, stack: 'movement' },
          { type: 'bar', label: 'Contraction', data: movement.contraction, backgroundColor: COLORS.amber, stack: 'movement' },
          { type: 'bar', label: 'Churn', data: movement.churn, backgroundColor: COLORS.red, stack: 'movement' },
          { type: 'line', label: 'Net change', data: movement.net, borderColor: COLORS.ink, backgroundColor: COLORS.ink, pointRadius: 2, borderWidth: 1.8, tension: 0.1 },
        ],
      },
      options: {
        ...baseOptions,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { stacked: true, ticks: { maxTicksLimit: 12, font: { size: 9 } }, grid: { display: false } },
          y: { stacked: true, ticks: { callback: compactMoney }, grid: { color: gridColor } },
        },
      },
    });
  }

  const arrGroup = get('pulse-data-arr-group');
  const arrGroupCanvas = document.getElementById('pulse-chart-arr-group');
  let arrGroupChart = null;

  function groupedSeries(key) {
    const raw = arrGroup[key];
    if (key !== 'by_industry' || Object.keys(raw).length <= 6) return raw;
    const groups = Object.keys(raw).sort((a, b) => raw[b][raw[b].length - 1] - raw[a][raw[a].length - 1]);
    const top = groups.slice(0, 5);
    const other = groups.slice(5);
    const result = {};
    top.forEach(group => { result[group] = raw[group]; });
    result.Other = arrGroup.labels.map((_, index) => other.reduce((sum, group) => sum + raw[group][index], 0));
    return result;
  }

  function buildArrGroupChart(key) {
    if (!arrGroup || !arrGroupCanvas) return;
    const series = groupedSeries(key);
    const datasets = Object.keys(series).map((group, index) => ({
      label: group,
      data: series[group],
      borderColor: GROUP_COLORS[index % GROUP_COLORS.length],
      backgroundColor: GROUP_COLORS[index % GROUP_COLORS.length],
      fill: false,
      tension: 0.2,
      pointRadius: 0,
      pointHoverRadius: 4,
      borderWidth: 3,
    }));
    if (arrGroupChart) arrGroupChart.destroy();
    arrGroupChart = new Chart(arrGroupCanvas, {
      type: 'line',
      data: { labels: arrGroup.labels, datasets },
      options: {
        ...baseOptions,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { ticks: { maxTicksLimit: 10, font: { size: 9 } }, grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: compactMoney }, grid: { color: gridColor } },
        },
      },
    });
  }

  if (arrGroup) buildArrGroupChart('by_industry');
  document.querySelectorAll('.pulse-group-toggle__btn[data-group]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.pulse-group-toggle__btn[data-group]').forEach(item => item.classList.remove('is-active'));
      button.classList.add('is-active');
      buildArrGroupChart(button.dataset.group);
    });
  });
});
