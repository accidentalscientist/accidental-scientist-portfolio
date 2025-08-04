document.addEventListener('DOMContentLoaded', function () {
  const chartDataElement = document.getElementById('fuel-data');
  if (!chartDataElement) {
    console.warn("⚠️ No #fuel-data element found");
    return;
  }

  const data = JSON.parse(chartDataElement.textContent);

  const roundedData = data.map(d => ({
    ...d,
    total_gen: Math.round(d.total_gen * 100) / 100
  }));

  // 🔁 Sort descending by total_gen, filter out 0 MW
  const sortedData = roundedData
    .filter(d => d.total_gen > 0)
    .sort((a, b) => b.total_gen - a.total_gen);

  const fuelValues = sortedData.map(d => d.total_gen);
  const barColors = sortedData.map(d => d.color || '#999');

  const totalGen = fuelValues.reduce((sum, val) => sum + val, 0);

  // ✅ Graph 1 labels: icon + name + percentage (multiline)
  const fuelLabelsWithIconAndPct = sortedData.map(d => {
    const percent = ((d.total_gen / totalGen) * 100).toFixed(1);
    return `${d.icon} ${d.fuel}\n${percent}%`;
  });

  // ✅ Graph 2 labels: numbered icon+name (left of bar), % right of bar
  const fuelLabelsNumbered = sortedData.map((d, i) => {
    return `${i + 1}. ${d.icon} ${d.fuel}`;
  });

  // ✅ DEBUG
  console.log("🎯 Raw data:", data);
  console.log("✅ Graph 1 labels:", fuelLabelsWithIconAndPct);
  console.log("✅ Graph 2 labels:", fuelLabelsNumbered);
  console.log("✅ Values:", fuelValues);

  // 1️⃣ Main vertical bar chart
  const fuelMixCtx = document.getElementById('fuelMixChart');
  if (fuelMixCtx) {
    new Chart(fuelMixCtx, {
      type: 'bar',
      data: {
        labels: fuelLabelsWithIconAndPct,
        datasets: [{
          label: 'MW Generated',
          data: fuelValues,
          backgroundColor: barColors,
          borderRadius: 4,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.raw.toFixed(2)} MW`
            }
          },
          datalabels: {
            anchor: 'end',
            align: 'end',
            color: '#000',
            formatter: value => value.toFixed(2)
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            title: { display: false }
          },
          x: {
            title: { display: false }
          }
        }
      },
      plugins: [ChartDataLabels]
    });
  }

  // 2️⃣ Secondary horizontal bar chart
  const tableChartCtx = document.getElementById('tableDataChart');
  if (tableChartCtx) {
    new Chart(tableChartCtx, {
      type: 'bar',
      data: {
        labels: fuelLabelsNumbered,
        datasets: [{
          label: 'MW Generated',
          data: fuelValues,
          backgroundColor: barColors
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.raw.toFixed(2)} MW`
            }
          },
          datalabels: {
            align: 'right',
            anchor: 'end',
            color: '#000',
            formatter: (value) => {
              const percent = ((value / totalGen) * 100).toFixed(1);
              return `${percent}%`;
            }
          }
        },
        scales: {
          x: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'MW'
            }
          }
        }
      },
      plugins: [ChartDataLabels]
    });
  }
});
