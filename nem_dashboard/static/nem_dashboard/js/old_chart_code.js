// Wait for the DOM to fully load before running the script
document.addEventListener('DOMContentLoaded', function () {
  
  // Find the <script id="fuel-data"> block which contains JSON
  const chartDataElement = document.getElementById('fuel-data');
  if (!chartDataElement) {
    console.warn("⚠️ No #fuel-data element found");
    return;
  }

  // Parse the text content inside the <script type="application/json"> tag into JS object
  const data = JSON.parse(chartDataElement.textContent);

  // Find the canvas element where the chart will be rendered
  const ctx = document.getElementById('fuelMixChart');
  if (!ctx) {
    console.warn("⚠️ No canvas with id=fuelMixChart found");
    return;
  }

  // Debugging logs
  console.log("✅ Chart data loaded:", data);
  console.log("✅ Canvas found:", ctx);

  // Define color palette for pie chart segments
  const colors = [
    '#3366cc', '#dc3912', '#ff9900', '#109618', '#990099',
    '#0099c6', '#dd4477', '#66aa00', '#b82e2e', '#316395'
  ];

  // Instantiate Chart.js pie chart
  new Chart(ctx, {
    type: 'pie',
    data: {
      labels: data.map(d => d.fuel_type),      // List of fuel types
      datasets: [{
        data: data.map(d => d.total_gen),      // Corresponding generation values
        backgroundColor: colors
      }]
    },
    options: {
      plugins: {
        legend: {
          position: 'right'                    // Legend position to the right
        }
      }
    }
  });
});